"""GeckoTerminal: шапка токена (цена, капа, ликвидность, объём) и свечи для чарта. Read-only, ошибки не фатальны.
На HTTP 429 повторяем с нарастающей паузой. Шапка — один запрос /tokens/{token}:
бесплатный тариф GT быстро отвечает 429, а в этом ответе уже есть всё для шапки.
Тот же ответ (с include=top_pools) даёт возраст пулов и FDV для проверки «too established» до скана.
Чарт (fetch_chart) в скан не входит: его отдаёт отдельный /api/chart.
Удачные ответы GT кэшируются по пути запроса на GT_CACHE_TTL (общий кэш для проверки перед сканом,
шапки и чарта); вердикт «too established» — на ESTABLISHED_TTL (established_get / established_put).
Каждый сбой GT пишется в лог одной строкой: путь, исход попыток (http-код / timeout), время.
Запасной источник рынка — DexScreener (публичный API, без ключа): если GT не ответил (429, ошибка, таймаут),
fetch_market берёт цену, ликвидность, капу, возраст и объём оттуда (поле source: "gt" | "dexscreener").
Свечей у DexScreener нет — чарт только из GT. GT_FORCE_FAIL=1 — каждый запрос к GT ведёт себя как 429."""
import json, os, re, socket, threading, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime

GT_API = "https://api.geckoterminal.com/api/v2"
GT = GT_API + "/networks"
GT_BUDGET = 3.0   # секунд на шапку целиком (все попытки): дольше скан не ждёт
GT_FIRST = 1.5    # секунд на GT в fetch_market до перехода на DexScreener (успевает 2 попытки на 429)
DS = "https://api.dexscreener.com/tokens/v1"
DS_BUDGET = 3.0   # секунд на DexScreener (все попытки)
DS_CHAIN = {"bsc": "bsc", "robinhood": "robinhood", "solana": "solana"}  # сеть GT -> chainId DexScreener
EVM_NETWORKS = {"bsc", "robinhood"}   # адреса EVM регистронезависимы: приводятся к нижнему регистру
CHART_BUDGET = 4.0  # секунд на чарт целиком (пулы + свечи + история кривой)
CHART_LIMIT = 1000  # свечей за запрос (максимум GT)
CURVE_DEX = "pump-fun"  # пул бондинг-кривой pump.fun: после миграции его свечи — начало истории
# таймфрейм по возрасту токена: (возраст до, часов; GT timeframe; aggregate; подпись)
TIMEFRAMES = ((2, "minute", 1, "1m"), (6, "minute", 5, "5m"), (48, "minute", 15, "15m"),
              (240, "hour", 1, "1h"), (None, "hour", 4, "4h"))
GT_CACHE_TTL = 15 * 60       # секунд: удачный ответ GT по пути запроса
GT_CACHE_MAX = 2000          # путей в кэше; старые вытесняются
ESTABLISHED_TTL = 24 * 3600  # секунд: вердикт «too established» по токену — повторный скан не идёт в GT

_CACHE, _EST, _lock = {}, {}, threading.Lock()


_TREND = {}          # network -> (ts, items): топ пулов GT, отдельно от кэша шапки
TREND_TTL = 120        # секунд
_AVATARS = {}          # (network, address) -> (ts, https image or ""): аватар токена для ленты
AVATAR_TTL = 600
_NEW = {}              # network -> (ts, items): новые токены (four.meme + Flap + пулы GT)
NEW_TTL = 15
WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
_SEARCH = {}           # query -> (ts, items): поиск BNB по адресу, имени или символу
SEARCH_TTL = 60
DS_SEARCH = "https://api.dexscreener.com/latest/dex/search"


def clear_cache():
    with _lock:
        _CACHE.clear()
        _EST.clear()
        _TREND.clear()
        _SEARCH.clear()
        _AVATARS.clear()
        _NEW.clear()


def _key(token, network):
    return network, token.lower() if network in EVM_NETWORKS else token


def established_get(token, network="robinhood"):
    """Данные GT, по которым токен признан too established, если вердикт моложе ESTABLISHED_TTL, иначе None."""
    with _lock:
        hit = _EST.get(_key(token, network))
    return dict(hit[1]) if hit and time.time() - hit[0] < ESTABLISHED_TTL else None


def established_put(token, network, market):
    with _lock:
        _EST[_key(token, network)] = (time.time(), dict(market))
        if len(_EST) > GT_CACHE_MAX:
            for k, _ in sorted(_EST.items(), key=lambda kv: kv[1][0])[:len(_EST) - GT_CACHE_MAX]:
                del _EST[k]


def _why(e):
    """Исход неудачной попытки для лога: http-код, timeout или тип ошибки."""
    if isinstance(e, urllib.error.HTTPError):
        return f"http {e.code}"
    if isinstance(e, (TimeoutError, socket.timeout)) or isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)):
        return "timeout"
    return type(e).__name__


def gt_force_fail():
    """GT_FORCE_FAIL=1: все запросы к GT ведут себя как 429 (проверка запасного пути на staging)."""
    return os.environ.get("GT_FORCE_FAIL", "").strip() == "1"


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": "foxscanner/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _post(url, payload, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"accept": "application/json", "content-type": "application/json",
                                          "user-agent": "foxscanner/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _cache_put(key, data):
    with _lock:
        _CACHE[key] = (time.time(), data)
        if len(_CACHE) > GT_CACHE_MAX:
            for k, _ in sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:len(_CACHE) - GT_CACHE_MAX]:
                del _CACHE[k]


def _cache_get(key):
    with _lock:
        hit = _CACHE.get(key)
    return hit[1] if hit and time.time() - hit[0] < GT_CACHE_TTL else None


def _gt(path, budget=GT_BUDGET, base=GT):
    """GET к GeckoTerminal. На все попытки (включая паузы после 429) не больше budget секунд:
    шапка не должна задерживать скан. Удачный ответ кэшируется на GT_CACHE_TTL. Неудачные попытки
    пишутся в лог одной строкой (и при итоговом сбое, и при успехе после повторов)."""
    forced = gt_force_fail()
    if not forced and (hit := _cache_get(path)) is not None:
        return hit
    t0 = time.time()
    end = t0 + budget
    last, fails = None, []

    def log(outcome):
        print(f"gt: {outcome} {path} [{', '.join(fails)}] {time.time() - t0:.1f}s"
              + (" (GT_FORCE_FAIL)" if forced else ""), flush=True)

    while True:
        left = end - time.time()
        if left <= 0.2:
            fails.append("no time left")
            log("fail")
            raise last or TimeoutError("geckoterminal: no time left")
        try:
            if forced:
                raise urllib.error.HTTPError(base + path, 429, "GT_FORCE_FAIL", {}, None)
            data = _get(base + path, left)
            if fails:
                log("ok after")
            _cache_put(path, data)
            return data
        except urllib.error.HTTPError as e:
            last = e
            fails.append(_why(e))
            if e.code != 429:
                log("fail")
                raise
        except Exception as e:
            last = e
            fails.append(_why(e))
        # пауза растёт: 0.5, 1, 2, 4 с — на 429 не добиваем GT частыми повторами
        time.sleep(min(0.5 * 2 ** (len(fails) - 1), 4.0, max(0.0, end - time.time() - 0.2)))


def fetch_market(token, network="robinhood", now=None, budget=GT_BUDGET):
    """{"name", "ticker", "price_usd", "mcap_usd", "fdv_usd", "liquidity_usd", "vol24h_usd", "age_days", "pool",
    "source"}
    или {} при ошибке. Сначала GT (один запрос /tokens/{token}?include=top_pools, до GT_FIRST секунд),
    не ответил (429, ошибка, таймаут) — DexScreener (_ds_market); нет и его — GT ещё раз на остаток бюджета.
    mcap — market cap, иначе fdv; liquidity — сумма пулов; age_days — от самого раннего пула (None без дат).
    pool — адрес самого ликвидного пула (GT) / пары (DexScreener; у Solana и Robinhood это тот же адрес пула,
    что у GT) — для виджета чарта на фронте. source — "gt" | "dexscreener". Удачный итог кэшируется по токену на GT_CACHE_TTL (общий для обоих источников).
    network — сеть GT: "robinhood" | "solana" (адреса Solana регистрозависимы, их не приводим к нижнему регистру).
    budget — секунд на все попытки (движок ждёт ответ в фоне дольше, чем шапку)."""
    tok = token.lower() if network in EVM_NETWORKS else token
    key = ("market", network, tok)
    hit = _cache_get(key)
    if hit is not None and not (hit["source"] == "gt" and gt_force_fail()):
        return dict(hit)
    end = time.time() + budget
    path = f"/{network}/tokens/{tok}?include=top_pools"
    out, why = {}, None
    try:
        out = _gt_market(_gt(path, budget=min(budget, GT_FIRST)), now)
        print(f"market: {tok} gt", flush=True)
    except Exception as e:
        why = _why(e)
    if not out and DS_CHAIN.get(network):
        try:
            out = _ds_market(tok, network, now, min(DS_BUDGET, end - time.time()))
            print(f"market: {tok} gt {why} -> dexscreener", flush=True)
        except Exception as e:
            print(f"market: {tok} gt {why} -> dexscreener failed ({_why(e)})", flush=True)
    if not out and end - time.time() > 0.5:   # оба не ответили — GT ещё раз на остаток (прежнее поведение)
        try:
            out = _gt_market(_gt(path, budget=end - time.time()), now)
            print(f"market: {tok} gt ok on retry", flush=True)
        except Exception as e:
            print(f"market: {tok} no market data (gt {_why(e)})", flush=True)
    if out:
        _cache_put(key, dict(out))
    return out


NATIVE_WRAPPED = {"robinhood": "0x0bd7d308f8e1639fab988df18a8011f41eacad73",   # WETH: цена нативной монеты сети
                  "bsc": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"}         # WBNB


def native_usd(network="robinhood", budget=GT_BUDGET):
    """Цена ETH в USD (WETH сети) или None: GT /simple/.../token_price (кэш GT_CACHE_TTL), не ответил —
    самая ликвидная пара WETH на DexScreener. Для цены токенов Flap на кривой (Portal знает цену в ETH,
    GeckoTerminal кривую не знает)."""
    weth = NATIVE_WRAPPED.get(network)
    if not weth:
        return None
    end = time.time() + budget
    try:
        d = _gt(f"/simple/networks/{network}/token_price/{weth}", budget=min(budget, GT_FIRST), base=GT_API)
        v = (((d.get("data") or {}).get("attributes") or {}).get("token_prices") or {}).get(weth)
        if v not in (None, "") and float(v) > 0:
            return float(v)
    except Exception:
        pass
    try:
        key = ("native", network)
        if (hit := _cache_get(key)) is not None:
            return hit
        out = _ds_market(weth, network, budget=max(0.3, min(DS_BUDGET, end - time.time())))
        if out.get("price_usd"):
            _cache_put(key, out["price_usd"])
        return out.get("price_usd")
    except Exception:
        return None


def _gt_market(d, now=None):
    a = (d.get("data") or {}).get("attributes") or {}
    f = lambda v: float(v) if v not in (None, "") else None
    born = [_ts((p.get("attributes") or {}).get("pool_created_at")) for p in d.get("included") or []
            if p.get("type") == "pool"]
    born = [b for b in born if b]
    pools = [(f((p.get("attributes") or {}).get("reserve_in_usd")) or 0.0, (p.get("attributes") or {}).get("address"))
             for p in d.get("included") or [] if p.get("type") == "pool"]
    pools = [p for p in pools if p[1]]
    # ликвидность — сумма reserve_in_usd пулов из ответа (top_pools), как у DexScreener (сумма пар); поле токена
    # total_reserve_in_usd бывает сильно меньше суммы его же пулов ($FSCAN 2026-10-08: $7.8K при пуле $43.8K).
    # Нет резервов у пулов — запасной путь: total_reserve_in_usd
    reserves = [f((p.get("attributes") or {}).get("reserve_in_usd")) for p in d.get("included") or []
                if p.get("type") == "pool"]
    reserves = [r for r in reserves if r is not None]
    return {"name": a.get("name"), "ticker": a.get("symbol"), "price_usd": f(a.get("price_usd")),
            "mcap_usd": f(a.get("market_cap_usd")) or f(a.get("fdv_usd")), "fdv_usd": f(a.get("fdv_usd")),
            "liquidity_usd": sum(reserves) if reserves else f(a.get("total_reserve_in_usd")),
            "vol24h_usd": f((a.get("volume_usd") or {}).get("h24")),
            "age_days": round(((now or time.time()) - min(born)) / 86400, 1) if born else None,
            "pool": max(pools)[1] if pools else None, "source": "gt"}


def _ds(url, budget):
    """GET к DexScreener: повтор на 429 и сетевые ошибки в пределах budget секунд, паузы 0.5 → 1 с."""
    end, last, n = time.time() + budget, None, 0
    while True:
        left = end - time.time()
        if left <= 0.2:
            raise last or TimeoutError("dexscreener: no time left")
        try:
            return _get(url, left)
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429:
                raise
        except Exception as e:
            last = e
        n += 1
        time.sleep(min(0.5 * n, max(0.0, end - time.time() - 0.2)))


def _ds_market(tok, network, now=None, budget=DS_BUDGET):
    """Рынок токена по DexScreener /tokens/v1/{chain}/{token} (до 30 пар): та же форма, что у GT.
    liquidity и объём 24h — сумма по всем парам; цена и капа (marketCap, иначе fdv) — из самой ликвидной пары,
    где токен — base (цена пары — цена base); возраст — от самой ранней pairCreatedAt. Нет пар — LookupError."""
    chain = DS_CHAIN[network]
    pairs = [p for p in _ds(f"{DS}/{chain}/{tok}", budget) or [] if p.get("chainId") == chain]
    if not pairs:
        raise LookupError("no pairs")
    same = (lambda x: (x or "").lower() == tok.lower()) if network in EVM_NETWORKS else (lambda x: x == tok)
    f = lambda v: float(v) if v not in (None, "") else None
    liq = lambda p: f((p.get("liquidity") or {}).get("usd")) or 0.0
    base = [p for p in pairs if same((p.get("baseToken") or {}).get("address"))]
    best = max(base, key=liq) if base else None
    me = (best or pairs[0]).get("baseToken" if best else "quoteToken") or {}
    if not best and not same(me.get("address")):
        me = {}
    born = [p["pairCreatedAt"] / 1000 for p in pairs if isinstance(p.get("pairCreatedAt"), (int, float))]
    vols = [f((p.get("volume") or {}).get("h24")) for p in pairs]
    txt = lambda v: (v or "").strip() or None
    return {"name": txt(me.get("name")), "ticker": txt(me.get("symbol")),
            "price_usd": f(best.get("priceUsd")) if best else None,
            "mcap_usd": (f(best.get("marketCap")) or f(best.get("fdv"))) if best else None,
            "fdv_usd": f(best.get("fdv")) if best else None,
            "liquidity_usd": sum(liq(p) for p in pairs) or None,
            "vol24h_usd": sum(v for v in vols if v) if any(v is not None for v in vols) else None,
            "age_days": round(((now or time.time()) - min(born)) / 86400, 1) if born else None,
            "pool": max(pairs, key=liq).get("pairAddress"), "source": "dexscreener"}


def _ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _pool(p, tok, network):
    """Пул из ответа /tokens/{tok}/pools: адрес, dex, ликвидность, время создания, цена токена в USD."""
    a, rel = p.get("attributes") or {}, p.get("relationships") or {}
    base = ((rel.get("base_token") or {}).get("data") or {}).get("id", "")
    same = (lambda x, y: x.lower() == y.lower()) if network in EVM_NETWORKS else (lambda x, y: x == y)
    side = "base" if same(base.split("_", 1)[-1], tok) else "quote"
    price = a.get(f"{side}_token_price_usd")
    return {"address": a.get("address"), "dex": ((rel.get("dex") or {}).get("data") or {}).get("id"),
            "liquidity": float(a.get("reserve_in_usd") or 0), "created": _ts(a.get("pool_created_at")),
            "price_usd": float(price) if price not in (None, "") else None}


def timeframe(age_h):
    """(GT timeframe, aggregate, подпись) по возрасту токена в часах; неизвестный возраст — 15m."""
    if age_h is None:
        return TIMEFRAMES[2][1:]
    return next(t[1:] for t in TIMEFRAMES if t[0] is None or age_h < t[0])


def _candles(network, pool, tf, tok, end):
    """[[ts, o, h, l, c, v]] от старых к новым (GT отдаёт новые первыми)."""
    left = end - time.time()
    path = (f"/{network}/pools/{pool}/ohlcv/{tf[0]}?aggregate={tf[1]}&limit={CHART_LIMIT}"
            f"&currency=usd&token={tok}")
    rows = ((_gt(path, budget=min(GT_BUDGET, left)).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    return sorted([int(r[0])] + [float(x) for x in r[1:6]] for r in rows if len(r) >= 5)


def fetch_chart(token, network="robinhood", now=None):
    """Свечи цены токена (USD) для чарта: {"pool", "dex", "timeframe", "candles", "price_usd",
    "age_h", "stitched", "failed"}, {} (GT не знает токен) или {"failed": True} (GT не ответил). Не дольше CHART_BUDGET секунд.
    Пул — самый ликвидный из пулов токена. Таймфрейм — по возрасту (TIMEFRAMES), возраст — от
    создания самого раннего из использованных пулов. Solana: если основной пул не кривая pump.fun,
    а пул кривой есть (токен мигрировал), его свечи до первой свечи основного пула идут в начало
    (stitched). Свечи не получены — candles = [] и failed = True, пул и цена всё равно отдаются."""
    end = time.time() + CHART_BUDGET
    tok = token.lower() if network in EVM_NETWORKS else token
    try:
        data = _gt(f"/{network}/tokens/{tok}/pools", budget=min(GT_BUDGET, end - time.time())).get("data") or []
        pools = sorted((_pool(p, tok, network) for p in data), key=lambda p: -p["liquidity"])
    except Exception:
        return {"failed": True}
    pools = [p for p in pools if p["address"]]
    if not pools:
        return {}
    main = pools[0]
    curve = None
    if network == "solana" and main["dex"] != CURVE_DEX:
        curve = next((p for p in pools if p["dex"] == CURVE_DEX), None)
    born = [p["created"] for p in (main, curve) if p and p["created"]]
    age_h = ((now or time.time()) - min(born)) / 3600 if born else None
    tf = timeframe(age_h)
    failed = False
    try:
        candles = _candles(network, main["address"], tf, tok, end)
    except Exception:
        candles, failed = [], True
    stitched = False
    if curve and end - time.time() > 0.3:
        try:
            first = candles[0][0] if candles else float("inf")
            early = [c for c in _candles(network, curve["address"], tf, tok, end) if c[0] < first]
            stitched = bool(early)
            candles = early + candles
        except Exception:
            pass
    return {"pool": main["address"], "dex": main["dex"], "timeframe": tf[2], "candles": candles,
            "price_usd": main["price_usd"], "age_h": None if age_h is None else round(age_h, 1),
            "stitched": stitched, "failed": failed}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_trending(data, limit=20):
    """Ответ GT /trending_pools?include=base_token → уникальные базовые токены в порядке пулов.
    {"token", "symbol", "name", "image", "mcap_usd", "price_usd"}. image — только https."""
    included = {}
    for item in (data or {}).get("included") or []:
        if item.get("type") == "token" and item.get("id"):
            included[item["id"]] = item.get("attributes") or {}
    out, seen = [], set()
    for pool in (data or {}).get("data") or []:
        rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
        tid = rel.get("id") or ""
        attrs = included.get(tid) or {}
        addr = (attrs.get("address") or "").strip()
        if not addr and "_" in tid:
            addr = tid.split("_", 1)[1]
        key = addr.lower()
        if not addr or key in seen:
            continue
        seen.add(key)
        pa = pool.get("attributes") or {}
        img = attrs.get("image_url") or ""
        out.append({
            "token": addr,
            "symbol": attrs.get("symbol") or "",
            "name": attrs.get("name") or "",
            "image": img if isinstance(img, str) and img.startswith("https://") else "",
            "mcap_usd": _num(pa.get("market_cap_usd")) or _num(pa.get("fdv_usd")),
            "price_usd": _num(pa.get("base_token_price_usd")),
        })
        if len(out) >= limit:
            break
    return out


def token_images(addresses, network="bsc"):
    """https-аватар GeckoTerminal по адресу (нижний регистр) или "". Сбой и токен без картинки — ""."""
    need, out, now = [], {}, time.time()
    for raw in addresses or []:
        addr = (raw or "").strip().lower()
        if not addr.startswith("0x") or len(addr) != 42 or addr in out or addr in need:
            continue
        with _lock:
            hit = _AVATARS.get((network, addr))
        if hit and now - hit[0] < AVATAR_TTL:
            out[addr] = hit[1]
        else:
            need.append(addr)
    found, asked = {}, []
    for i in range(0, len(need), 30):
        chunk = need[i:i + 30]
        try:
            data = _get(f"{GT}/{network}/tokens/multi/{','.join(chunk)}", 2)
        except Exception as e:
            print(f"gt: avatars {network} failed: {_why(e)}", flush=True)
            continue
        asked.extend(chunk)
        for item in (data or {}).get("data") or []:
            attrs = item.get("attributes") or {}
            addr = (attrs.get("address") or "").strip().lower()
            img = attrs.get("image_url") or ""
            if addr in chunk and isinstance(img, str) and img.startswith("https://"):
                found[addr] = img
    with _lock:
        for addr in asked:
            url = found.get(addr, "")
            _AVATARS[(network, addr)] = (now, url)
            out[addr] = url
    return out


_FLAP_IMG = re.compile(r'image\\?":\\?"(https://[^"\\]+)')


def flap_image(address):
    """Картинка токена Flap со страницы flap.sh, если GeckoTerminal её не знает. Только https. Кэш 10 минут."""
    addr = (address or "").strip().lower()
    if not addr.startswith("0x") or len(addr) != 42:
        return ""
    now = time.time()
    with _lock:
        hit = _AVATARS.get(("flap", addr))
    if hit and now - hit[0] < (AVATAR_TTL if hit[1] else 60):
        return hit[1]
    url = ""
    try:
        req = urllib.request.Request("https://flap.sh/bnb/" + addr,
                                     headers={"user-agent": "foxscanner/0.1", "accept": "text/html"})
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read(250000).decode("utf-8", "replace")
        m = _FLAP_IMG.search(html)
        if m:
            url = m.group(1)
    except Exception as e:
        print(f"flap: avatar {addr} failed: {_why(e)}", flush=True)
    with _lock:
        _AVATARS[("flap", addr)] = (now, url)
    return url


def _unix(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def parse_new_pools(data, limit=7):
    """Ответ GT /new_pools?include=base_token → новые базовые токены, самые свежие сверху.
    {"token", "symbol", "name", "image", "created"}. WBNB пропускается. image — только https."""
    included = {}
    for item in (data or {}).get("included") or []:
        if item.get("type") == "token" and item.get("id"):
            included[item["id"]] = item.get("attributes") or {}
    by = {}
    for pool in (data or {}).get("data") or []:
        rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
        tid = rel.get("id") or ""
        attrs = included.get(tid) or {}
        addr = (attrs.get("address") or "").strip()
        if not addr and "_" in tid:
            addr = tid.split("_", 1)[1]
        key = addr.lower()
        if not addr or key == WBNB:
            continue
        pa = pool.get("attributes") or {}
        created = _unix(pa.get("pool_created_at") or pa.get("created_at"))
        prev = by.get(key)
        if prev and (prev["created"] or 0) >= (created or 0):
            continue
        img = attrs.get("image_url") or ""
        by[key] = {
            "token": addr,
            "symbol": attrs.get("symbol") or "",
            "name": attrs.get("name") or "",
            "image": img if isinstance(img, str) and img.startswith("https://") else "",
            "created": created,
        }
    limit = max(1, int(limit))
    return sorted(by.values(), key=lambda x: x["created"] or 0, reverse=True)[:limit]


FOUR_SEARCH = "https://four.meme/meme-api/v1/public/token/search"
FOUR_IMG = "https://static.four.meme"


def four_image(img):
    """Картинка four.meme: путь /market/... или уже https. Иное — ""."""
    if not isinstance(img, str) or not img:
        return ""
    if img.startswith("https://"):
        return img
    if img.startswith("/"):
        return FOUR_IMG + img
    if img.startswith("market/"):
        return FOUR_IMG + "/" + img
    return ""


def _seconds(n):
    """Unix-секунды из числа или цифровой строки. Значение больше 10^12 — миллисекунды."""
    if isinstance(n, str):
        n = n.strip()
        if not n.isdigit():
            return None
        n = int(n)
    if not isinstance(n, (int, float)) or n <= 0:
        return None
    return int(n / 1000) if n > 10 ** 12 else int(n)


def parse_four_new(data, limit=30):
    """Ответ four.meme /public/token/search → новые токены, самые свежие сверху.
    {"token", "symbol", "name", "image", "created"}. Повторы адреса схлопываются. image — только https."""
    rows = data.get("data") if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = next((v for v in rows.values() if isinstance(v, list)), [])
    if not isinstance(rows, list):
        return []
    by = {}
    for x in rows:
        if not isinstance(x, dict):
            continue
        addr = (x.get("tokenAddress") or x.get("address") or "").strip()
        key = addr.lower()
        if not key.startswith("0x") or len(key) != 42 or key == WBNB:
            continue
        created = _seconds(x.get("createDate") or x.get("launchTime"))
        row = {"token": addr, "symbol": x.get("shortName") or "", "name": x.get("name") or "",
               "image": four_image(x.get("img") or x.get("image") or ""), "created": created}
        prev = by.get(key)
        if prev is None or (created or 0) > (prev["created"] or 0):
            if prev and not row["image"]:
                row["image"] = prev["image"]
            if prev and not row["symbol"]:
                row["symbol"] = prev["symbol"]
            if prev and not row["name"]:
                row["name"] = prev["name"]
            by[key] = row
        elif not prev["image"] and row["image"]:
            prev["image"] = row["image"]
    limit = max(1, int(limit))
    return sorted(by.values(), key=lambda x: x["created"] or 0, reverse=True)[:limit]


def merge_new(rows, limit=20):
    """Несколько лент в одну. created — самый ранний, пустые symbol, name и image добираются из другой ленты."""
    by = {}
    for x in rows or []:
        if not isinstance(x, dict):
            continue
        addr = (x.get("token") or "").strip()
        key = addr.lower()
        if not key.startswith("0x") or len(key) != 42 or key == WBNB:
            continue
        created = x.get("created") if isinstance(x.get("created"), (int, float)) and x["created"] > 0 else None
        image = x.get("image") if isinstance(x.get("image"), str) and x["image"].startswith("https://") else ""
        prev = by.get(key)
        if prev is None:
            by[key] = {"token": addr, "symbol": x.get("symbol") or "", "name": x.get("name") or "",
                       "image": image, "created": int(created) if created else None}
            continue
        if created and (not prev["created"] or created < prev["created"]):
            prev["created"] = int(created)
        if not prev["image"] and image:
            prev["image"] = image
        if not prev["symbol"] and x.get("symbol"):
            prev["symbol"] = x["symbol"]
        if not prev["name"] and x.get("name"):
            prev["name"] = x["name"]
    limit = max(1, int(limit))
    return sorted(by.values(), key=lambda x: x["created"] or 0, reverse=True)[:limit]


def new_tokens(network="bsc", limit=7):
    """Новые токены BNB в момент создания (four.meme и Flap) плюс свежие пулы GeckoTerminal.
    Сбой одного источника не стирает остальные. Сбой всех — прошлый кэш или []."""
    limit = min(20, max(1, int(limit)))
    now = time.time()
    with _lock:
        hit = _NEW.get(network)
    if hit and now - hit[0] < NEW_TTL:
        return hit[1][:limit]
    from concurrent.futures import ThreadPoolExecutor

    def safe(fn, label):
        try:
            return fn()
        except Exception as e:
            print(f"new tokens: {label} failed: {_why(e)}", flush=True)
            return []

    def four_rows():
        if network not in ("bsc", "bnb"):
            return []
        data = _post(FOUR_SEARCH, {"type": "NEW", "pageIndex": 1, "pageSize": 30, "status": "ALL", "sort": "DESC"}, 8)
        return parse_four_new(data, 30)

    def gt_rows():
        data = _get(f"{GT}/{network}/new_pools?include=base_token&page=1", 8)
        return parse_new_pools(data, 20)

    def flap_rows():
        if network not in ("bsc", "bnb"):
            return []
        from foxscanner.chains import bnb_flap
        return bnb_flap.recent_created(12)

    with ThreadPoolExecutor(max_workers=3) as pool:
        parts = list(pool.map(lambda job: safe(job[0], job[1]),
                              ((four_rows, "four.meme"), (gt_rows, "gt"), (flap_rows, "flap"))))
    items = merge_new([row for part in parts for row in part], 20)
    if not items and hit:
        return hit[1][:limit]
    with _lock:
        _NEW[network] = (now, items)
    return items[:limit]


def trending(network="bsc", limit=20):
    """Топ токенов сети по трендовым пулам GeckoTerminal. Сбой — прошлый кэш или []."""
    limit = min(20, max(1, int(limit)))
    now = time.time()
    with _lock:
        hit = _TREND.get(network)
    if hit and now - hit[0] < TREND_TTL:
        return hit[1][:limit]
    items, seen = [], set()
    try:
        for page in (1, 2):
            data = _get(f"{GT}/{network}/trending_pools?include=base_token&page={page}", 8)
            for row in parse_trending(data, 20):
                key = row["token"].lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(row)
                if len(items) >= 20:
                    break
            if len(items) >= 20:
                break
    except Exception as e:
        print(f"gt: trending {network} failed: {_why(e)}", flush=True)
        return (hit[1] if hit else [])[:limit]
    with _lock:
        _TREND[network] = (now, items)
    return items[:limit]


def parse_search(data, limit=20):
    """Ответ DexScreener /search → уникальные базовые токены BNB, ликвидные пары первыми.
    {"token", "symbol", "name", "image", "mcap_usd", "price_usd"}."""
    def liq(pair):
        return _num(((pair or {}).get("liquidity") or {}).get("usd")) or 0

    out, seen = [], set()
    for pair in sorted((data or {}).get("pairs") or [], key=liq, reverse=True):
        if (pair.get("chainId") or "") != "bsc":
            continue
        base = pair.get("baseToken") or {}
        addr = (base.get("address") or "").strip()
        key = addr.lower()
        if not addr or key in seen:
            continue
        seen.add(key)
        img = ((pair.get("info") or {}).get("imageUrl") or "")
        out.append({
            "token": addr,
            "symbol": base.get("symbol") or "",
            "name": base.get("name") or "",
            "image": img if isinstance(img, str) and img.startswith("https://") else "",
            "mcap_usd": _num(pair.get("marketCap")) or _num(pair.get("fdv")),
            "price_usd": _num(pair.get("priceUsd")),
        })
        if len(out) >= limit:
            break
    return out


def search_tokens(query, limit=20):
    """Поиск токенов BNB по адресу, имени или символу. Короткий запрос и сбой — [] или прошлый кэш."""
    q = " ".join((query or "").split())
    limit = min(20, max(1, int(limit)))
    if len(q) < 2 or len(q) > 80:
        return []
    key = q.lower()
    now = time.time()
    with _lock:
        hit = _SEARCH.get(key)
    if hit and now - hit[0] < SEARCH_TTL:
        return hit[1][:limit]
    try:
        data = _get(DS_SEARCH + "?q=" + urllib.parse.quote(q), 8)
        items = parse_search(data, 20)
    except Exception as e:
        print(f"search: {q!r} failed: {_why(e)}", flush=True)
        return (hit[1] if hit else [])[:limit]
    with _lock:
        _SEARCH[key] = (now, items)
        if len(_SEARCH) > 200:
            for k, _ in sorted(_SEARCH.items(), key=lambda kv: kv[1][0])[:len(_SEARCH) - 200]:
                del _SEARCH[k]
    return items[:limit]

"""Адаптер BNB Smart Chain (chain id 56): лаунчпад four.meme (TokenManager2 + TokenManagerHelper3).

Токен four.meme живёт на бондинг-кривой TokenManager (V2, старые — V1); по достижении цели сбора (maxFunds)
ликвидность уходит в пару PancakeSwap V2 (liquidityAdded). Всё о токене — один eth_call
TokenManagerHelper3.getTokenInfo(token): версия, менеджер, котировочный токен (0x0 = BNB), цена, время запуска,
остаток предложения на кривой и собранные средства. У чужого токена менеджер — нулевой адрес.

Запуск: блок первого минта токена (Transfer с 0x0) рядом с блоком launchTime (поиск блока по времени).
Сделки: на кривой — событие TokenPurchase менеджера в чеке (цена в BNB точная), после выпуска — Swap пары.
Падение цены при продаже на кривой — по котировкам Helper3.trySell (как V4Quoter у Bankr), в паре — x*y=k.
История кошелька до входа — число его транзакций к блоку входа (eth_getTransactionCount на архивном RPC):
у новых кошельков 0, у кошелька с историей — больше. Один запрос на кошелёк вместо чтения всей истории BSC.
Read-only: ни ключей, ни подписи.
"""
import os, threading, time
from collections import defaultdict

from foxscanner.chains import evm
from foxscanner.env import load_dotenv
from foxscanner.scan import detect as d

load_dotenv()

CHAIN = "bnb"
RPS = int(os.environ.get("BNB_RPS", "10") or 10)
CLIENT = evm.Client(lambda: os.environ.get("BNB_RPC", "").strip(), rps=RPS)
REQUESTS = CLIENT.requests
RATE_LIMITED = CLIENT.rate_limited
PACK_WINDOW = 1           # блоки BSC ~0.75 с: стая — соседние блоки
BUNDLE_WINDOW = 1         # бандл запуска — блок запуска и следующий
RUG_SNIPERS = True

MANAGER_V2 = "0x5c952063c7fc8610ffdb798152d69f0b9550762b"
MANAGER_V1 = "0xec4549cadce5da21df6e6422d448034b5233bfbc"
HELPER3 = "0xf251f83e40a78868fcfa3fa4599dad6494e46034"
PANCAKE_V2_FACTORY = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"
WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
MANAGERS = {MANAGER_V1, MANAGER_V2}
ROUTERS = {   # получил токен от роутера — купил, отдал роутеру — продал
    "0x10ed43c718714eb63d5aa57b78b54704e256024e",   # PancakeSwap V2 Router
    "0x13f4ea83d0bd40e75c8222255bc855a974568dd4",   # PancakeSwap Smart Router (V3)
    "0x1a0a18ac4becddbd6389559687d1a73d8927e416",   # PancakeSwap Universal Router
}
INFRA = MANAGERS | {HELPER3, PANCAKE_V2_FACTORY, WBNB, evm.DEAD, evm.ZERO,
                    "0x000000000022d473030f116ddee9f6b43ac78ba3"}   # Permit2
BURN_ADDRS = {evm.DEAD, evm.ZERO}

SEL_TOKEN_INFO = evm.selector("getTokenInfo(address)")
SEL_TRY_SELL = evm.selector("trySell(address,uint256)")
SEL_GET_PAIR = evm.selector("getPair(address,address)")
SEL_TOKEN0 = "0x0dfe1681"
TOKEN_PURCHASE = evm.topic("TokenPurchase(address,address,uint256,uint256,uint256,uint256,uint256,uint256)")
TOKEN_SALE = evm.topic("TokenSale(address,address,uint256,uint256,uint256,uint256,uint256,uint256)")
V2_SWAP = evm.topic("Swap(address,uint256,uint256,uint256,uint256,address)")
INFO_FIELDS = ("version", "manager", "quote", "last_price", "fee_rate", "min_fee", "launch_time", "offers",
               "max_offers", "funds", "max_funds", "liquidity_added")

SCAN_MAX_LOGS = 150_000   # переводов в скане; больше — "token history too large"
try:
    SCAN_MAX_LOGS = max(0, int(os.environ.get("SCAN_MAX_LOGS", "").strip() or SCAN_MAX_LOGS))
except ValueError:
    pass
STATE_TTL = 20            # секунд: состояние кривой (offers, funds) меняется с каждой сделкой
LAUNCH_SPANS = (4_000, 400_000)   # блоков вокруг launchTime для поиска минта; не нашли — вся история
ENTRY_TOL = 0.06          # допуск сверки количества покупки (комиссии)
QUOTE_REF = 0.001         # котировки trySell: опорная (цена до продажи) и сетка долей оборота
QUOTE_GRID = (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8)
QUOTE_STEP = 101          # вторая точка для маржинальной цены: q × 1.01
FRESH_CAP = 4
EARLY_WINDOW = 4000       # блоков после запуска в первом окне early buyers (удваивается)
EARLY_CANDIDATES = 25
EARLY_OUT_CAP = 20
SCAN_TTL = 600            # секунд: история скана для early buyers

_STATE, _LAUNCH, _PAIR, _TOKEN0, _SCAN = {}, {}, {}, {}, {}
_lock = threading.Lock()


def enabled():
    return os.environ.get("BNB_ENABLED", "true").strip().lower() in ("1", "true", "yes")


SUFFIX = "4444"          # с марта 2025 каждый новый токен four.meme кончается на 4444
X_PREFIX = "0x4444"       # X Mode: адрес начинается с 0x4444


def candidate(token):
    """Адрес EVM (без RPC). У старых токенов суффикса нет — их подтверждает Helper3."""
    return isinstance(token, str) and token.startswith("0x") and len(token) == 42


def by_address(token):
    """Токен four.meme узнаётся по адресу, без RPC: суффикс 4444 или префикс X Mode 0x4444.
    Токены до стандартизации адреса сюда не попадают."""
    if not isinstance(token, str):
        return False
    t = token.lower()
    return t.endswith(SUFFIX) or t.startswith(X_PREFIX)


# --------------------------------------------------------------------------- состояние токена
def _decode_info(h):
    w = evm.words(h)
    if len(w) < len(INFO_FIELDS):
        return None
    st = dict(zip(INFO_FIELDS, w))
    st["manager"], st["quote"] = evm.word_addr(st["manager"]), evm.word_addr(st["quote"])
    st["liquidity_added"] = bool(st["liquidity_added"])
    return st if st["manager"] != evm.ZERO else None


def detect(token, fresh=False):
    """Состояние токена four.meme (getTokenInfo) или None — не four.meme. Кэш STATE_TTL секунд."""
    token = token.lower()
    with _lock:
        hit = _STATE.get(token)
    if hit and not fresh and time.time() - hit[0] < STATE_TTL:
        return hit[1]
    try:
        st = _decode_info(CLIENT.call(HELPER3, SEL_TOKEN_INFO + evm.arg_addr(token)))
    except RuntimeError:   # revert: не токен four.meme
        st = None
    with _lock:
        _STATE[token] = (time.time(), st)
        if len(_STATE) > 5000:
            _STATE.clear()
    return st


def quote_info(st):
    q = (st or {}).get("quote") or evm.ZERO
    if q in (evm.ZERO, WBNB):
        return {"kind": "bnb", "address": WBNB, "symbol": "BNB"}
    return {"kind": "token", "address": q, "symbol": CLIENT.token_meta(q).get("symbol") or None}


def pair_of(token, st):
    """Пара PancakeSwap V2 выпущенного токена (с котировочным токеном кривой) или None."""
    token = token.lower()
    if not st or not st["liquidity_added"]:
        return None
    if token in _PAIR:
        return _PAIR[token]
    quote = st["quote"] if st["quote"] != evm.ZERO else WBNB
    try:
        w = evm.words(CLIENT.call(PANCAKE_V2_FACTORY, SEL_GET_PAIR + evm.arg_addr(token) + evm.arg_addr(quote)))
    except RuntimeError:
        return None
    pair = evm.word_addr(w[0]) if w and w[0] else None
    if pair:
        _PAIR[token] = pair
    return pair


def market_addresses(st, pair=None):
    return {(st or {}).get("manager") or MANAGER_V2} | ROUTERS | ({pair} if pair else set())


def excluded_addresses(st, pair=None):
    return INFRA | market_addresses(st, pair)


# --------------------------------------------------------------------------- запуск
def get_launch(token, st=None):
    """{"block", "curve" (менеджер), "deployer", "tx", "ts"} или None (не four.meme / минт не найден).
    deployer — кто получил токены с кривой в транзакции запуска (дев-бай), иначе отправитель транзакции."""
    token = token.lower()
    if token in _LAUNCH:
        return dict(_LAUNCH[token])
    st = st or detect(token)
    if st is None:
        return None
    # Alchemy free tier режет eth_getLogs до 10 блоков. Листать ±4000 (и тем более 0..head) по таким
    # страницам — минуты на стадии «Finding the launch». Минт одним alchemy_getAssetTransfers;
    # иначе короткое окно вокруг launchTime, без обхода всей цепи.
    found = CLIENT.earliest_erc20_mint(token)
    if found:
        tx, block = found["tx"], found["block"]
    else:
        mint_topics = [evm.TRANSFER_TOPIC, evm.topic_for(evm.ZERO)]
        head = CLIENT.block_number()
        logs = []
        if st["launch_time"]:
            center = CLIENT.block_at_time(st["launch_time"])
            for span in LAUNCH_SPANS:
                logs = CLIENT.nearest_logs(center, head, address=token, topics=mint_topics, radius=span)
                if logs:
                    break
        if not logs:
            return None
        mint = min(logs, key=lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16)))
        tx, block = mint["transactionHash"], int(mint["blockNumber"], 16)
    deployer = None
    for lg in CLIENT.receipt_logs([tx]).get(tx, []):
        p = evm.parse_transfer(lg)
        if p and p["token"] == token and p["frm"] == st["manager"] and p["to"] not in INFRA:
            deployer = p["to"]
            break
    deployer = deployer or CLIENT.tx_sender(tx)
    res = {"block": block, "curve": st["manager"], "deployer": deployer, "tx": tx}
    _LAUNCH[token] = res
    return dict(res)


# --------------------------------------------------------------------------- факты для движка
def _quote_calls(token, manager, circulating):
    qs = []
    for f in (QUOTE_REF,) + QUOTE_GRID:
        q = max(1, int(circulating * f))
        qs += [q, q * QUOTE_STEP // 100]
    return [(HELPER3, SEL_TRY_SELL + evm.arg_addr(token) + evm.arg_uint(q)) for q in qs], qs


def impact_curve(qs, raw):
    """Котировки trySell -> [(q, падение цены после продажи q)] по возрастанию q; [] — котировок нет.
    trySell -> (tokenManager, quote, funds, fee): funds — сколько выручит продажа q. Маржинальная цена
    p(q) = Δfunds / Δq; падение — 1 − p(q) / p0 (монотонно, не больше 1)."""
    vals = []
    for r in raw:
        w = evm.words(r) if r else []
        vals.append(w[2] if len(w) >= 3 else None)
    pr = []
    for i in range(0, len(qs) - 1, 2):
        a, b = vals[i], vals[i + 1]
        pr.append((qs[i], (b - a) / (qs[i + 1] - qs[i]) if a is not None and b is not None and b > a else None))
    p0 = pr[0][1] if pr else None
    if not p0:
        return []
    out, worst = [], 0.0
    for q, p in pr[1:]:
        if p is None:
            continue
        worst = max(worst, min(1.0, max(0.0, 1 - p / p0)))
        out.append((q, worst))
    return out


def remember_scan(token, launch, transfers, supply):
    now = time.time()
    with _lock:
        for k in [k for k, v in _SCAN.items() if now - v[0] >= SCAN_TTL]:
            del _SCAN[k]
        _SCAN[token] = (now, dict(launch), transfers, supply)
        while sum(len(v[2]) for v in _SCAN.values()) > 100_000 and len(_SCAN) > 1:
            del _SCAN[next(iter(_SCAN))]


def scan_history(token):
    with _lock:
        hit = _SCAN.get(token.lower())
    if not hit or time.time() - hit[0] >= SCAN_TTL:
        return None
    return hit[1], hit[2], hit[3]


def drop_caches():
    with _lock:
        _SCAN.clear()
    CLIENT.drop_caches()


def token_facts(token, launch, deadline=None):
    """Факты для движка (общий контракт сетей) + "impact_curve" (на кривой) и "fourmeme" (данные лаунчпада).
    На кривой резерв — токены на менеджере (в т.ч. отложенные под ликвидность), падение цены — по trySell;
    после выпуска резерв — баланс пары PancakeSwap, падение — x*y=k."""
    token = token.lower()
    st = detect(token, fresh=True) or {}
    supply = CLIENT.token_supply(token)
    transfers = CLIENT.token_transfers(token, launch["block"], cap=SCAN_MAX_LOGS)
    remember_scan(token, launch, transfers, supply)
    pair = pair_of(token, st)
    market, excluded = market_addresses(st, pair), excluded_addresses(st, pair)
    held = defaultdict(int)
    for t in transfers:
        held[t["to"]] += t["amount"]
        held[t["frm"]] -= t["amount"]
    manager = st.get("manager") or launch["curve"]
    quote = quote_info(st)
    curve = []
    if pair:
        reserve = max(0, held.get(pair, 0))
    else:
        reserve = max(0, held.get(manager, 0))
        circ = d.supply_base(transfers, supply, excluded)["circulating"]
        if circ > 0:
            calls, qs = _quote_calls(token, manager, circ)
            try:
                curve = impact_curve(qs, CLIENT.call_batch(calls))
            except RuntimeError:
                curve = []
    max_funds, funds = st.get("max_funds") or 0, st.get("funds") or 0
    progress = 1.0 if pair or st.get("liquidity_added") else (min(1.0, funds / max_funds) if max_funds else None)
    is_bnb = quote["kind"] == "bnb"
    info = {"phase": "pancakeswap" if pair else "bonding_curve", "version": st.get("version"),
            "manager": manager, "pool": pair, "graduated": bool(pair), "progress": progress, "quote": quote,
            "price_native": st["last_price"] / 1e18 if is_bnb and st.get("last_price") and not pair else None,
            "reserve_native": funds / 1e18 if is_bnb and not pair else None,
            "impact_source": "try_sell" if curve else ("pair" if pair else None)}
    out = {"supply": supply, "transfers": transfers, "excluded": excluded, "market": market,
           "reserve": reserve, "reserve_ok": bool(curve) or reserve > 0, "base": None, "fourmeme": info}
    if curve:
        out["impact_curve"] = curve
    return out


# --------------------------------------------------------------------------- входы и история кошельков
def _token0(pair):
    if pair not in _TOKEN0:
        w = evm.words(CLIENT.call(pair, SEL_TOKEN0))
        _TOKEN0[pair] = evm.word_addr(w[0]) if w else None
    return _TOKEN0[pair]


def _buys_in(token, logs):
    """[(токенов куплено, BNB потрачено | None)] из логов транзакции: TokenPurchase менеджера и Swap пары."""
    out = []
    moves = [(p, int(l["data"][:66], 16)) for l in logs if (p := evm.parse_transfer(l)) and p["token"] == token
             and len(l["data"]) > 2]
    for l in logs:
        tp = l.get("topics") or []
        if not tp:
            continue
        t0, addr = tp[0].lower(), l["address"].lower()
        if t0 == TOKEN_PURCHASE and addr in MANAGERS:
            if evm.word_addr(evm.u256(l["data"], 0)) == token:
                out.append((evm.u256(l["data"], 3), evm.u256(l["data"], 4)))
        elif t0 == V2_SWAP:
            outs = [a for p, a in moves if p["frm"] == addr]
            if not outs:
                continue
            try:
                is0 = _token0(addr) == token
            except RuntimeError:
                continue
            a0in, a1in = evm.u256(l["data"], 0), evm.u256(l["data"], 1)
            out.append((sum(outs), a1in if is0 else a0in))
    return out


def classify_entries(token, transfers, wallets, chunk=50):
    """Первое получение токена каждым кошельком: {wallet: {"kind": "buy"|"transfer", "tx", "block", "via",
    "eth_in"}}. buy — в чеке есть TokenPurchase этого токена или Swap пары, из которой ушёл токен (так покупка
    через сторонний бот-роутер — тоже buy). eth_in — BNB на покупку (wei), сверенный с полученным (±6%);
    котировка не BNB или сверить не удалось — None."""
    token = token.lower()
    want = {w.lower() for w in wallets}
    first = {}
    for t in transfers:
        if t["to"] in want and t["to"] not in first:
            first[t["to"]] = t
    receipts = CLIENT.receipt_logs(sorted({t["tx"] for t in first.values()}), chunk)
    is_bnb = (detect(token) or {}).get("quote", evm.ZERO) in (evm.ZERO, WBNB)
    out = {}
    for w, t in first.items():
        buys = _buys_in(token, receipts.get(t["tx"], []))
        eth_in = None
        if buys and is_bnb:
            tok, quote = min(buys, key=lambda b: abs(b[0] - t["amount"]))
            if t["amount"] and abs(tok - t["amount"]) <= ENTRY_TOL * t["amount"]:
                eth_in = quote
        kind = "buy" if buys or t["frm"] in ROUTERS or t["frm"] in MANAGERS else "transfer"
        out[w] = {"kind": kind, "tx": t["tx"], "block": t["block"], "via": t["frm"], "eth_in": eth_in}
    return out


def wallet_distinct_tokens(wallet, before_block, skip_token, window=None, cap=FRESH_CAP):
    """История кошелька до входа: число его транзакций к блоку входа, не больше cap (0 — новый кошелёк).
    Нет ответа архивного RPC — None (кошелёк unread)."""
    n = CLIENT.nonces_at([(wallet.lower(), before_block)]).get((wallet.lower(), before_block))
    return None if n is None else min(n, cap)


def block_timestamps(blocks):
    return CLIENT.block_timestamps(blocks)


def is_contract(addresses):
    return CLIENT.is_contract(addresses)


def token_meta(token):
    return CLIENT.token_meta(token)


# --------------------------------------------------------------------------- early buyers
def early_buyers(token, n=20, deadline=None):
    """Первые n покупателей: {"launch": {"block", "ts", "deployer", "curve"}, "buyers": [{"wallet", "block", "ts",
    "tx", "bought"}], "txs_read"} или None (не four.meme). История скана моложе SCAN_TTL — без запросов логов."""
    token = token.lower()
    hist = scan_history(token)
    st = detect(token)
    if st is None:
        return None
    launch = hist[0] if hist else get_launch(token, st)
    if launch is None:
        return None
    pair = pair_of(token, st)
    excluded, market = excluded_addresses(st, pair), market_addresses(st, pair)
    head = None if hist else CLIENT.block_number()
    lo, span, trs = launch["block"], EARLY_WINDOW, list(hist[1]) if hist else []
    buyers, checked, order = [], set(), []
    while True:
        if hist:
            hi = head = 0
        else:
            hi = min(head, launch["block"] + span)
            trs += CLIENT.token_transfers(token, lo, hi)
            lo = hi + 1
        order = list(dict.fromkeys(t["to"] for t in trs if t["to"] not in excluded))
        fresh = [a for a in order if a not in checked]
        while fresh and len(buyers) < n and not (deadline and time.time() > deadline):
            k = min(EARLY_CANDIDATES, n - len(buyers) + 3)
            part, fresh = fresh[:k], fresh[k:]
            checked |= set(part)
            code = CLIENT.is_contract(part)
            wallets = [a for a in part if not code.get(a)]
            src = {}
            for t in trs:
                if t["to"] in wallets and t["to"] not in src:
                    src[t["to"]] = t["frm"]
            unsure = [a for a in wallets if src.get(a) not in market]
            ent = classify_entries(token, trs, unsure) if unsure else {}
            buyers += [a for a in wallets if a not in ent or ent[a]["kind"] == "buy"]
        if len(buyers) >= n or hi >= head or (deadline and time.time() > deadline):
            break
        span *= 2
    rank = {a: i for i, a in enumerate(order)}
    buyers = sorted(buyers, key=rank.get)[:n]
    first = {}
    for t in trs:
        if t["to"] in buyers and t["to"] not in first:
            first[t["to"]] = t
    ts = CLIENT.block_timestamps({launch["block"]} | {t["block"] for t in first.values() if "ts" not in t})
    out = [{"wallet": a, "block": first[a]["block"], "ts": first[a].get("ts", ts.get(first[a]["block"])),
            "tx": first[a]["tx"], "bought": sum(x["amount"] for x in trs if x["to"] == a and x["tx"] == first[a]["tx"])}
           for a in buyers]
    return {"launch": {"block": launch["block"], "ts": ts.get(launch["block"]), "deployer": launch["deployer"],
                       "curve": launch["curve"]}, "buyers": out, "txs_read": len(trs)}


def _is_sell(token, logs, market):
    return any((l.get("topics") or [""])[0].lower() == TOKEN_SALE and l["address"].lower() in MANAGERS for l in logs) \
        or any((p := evm.parse_transfer(l)) and p["token"] == token and p["to"] in market for l in logs)


def early_status(token, buyers, deadline=None, launch=None, out_cap=EARLY_OUT_CAP):
    """Что покупатели сделали с токеном: {"supply", "wallets": {wallet: {"now", "sold", "moved", "burned", "locked",
    "locked_in", "partial"}}}. Выход на рынок (менеджер, роутеры, пара) — продажа; на другой адрес — по чеку
    (TokenSale или токен ушёл на рынок в той же транзакции), иначе перевод; на burn / 0x0 — сожжено."""
    token = token.lower()
    hist = scan_history(token)
    st = detect(token) or {}
    market = market_addresses(st, pair_of(token, st))
    supply = hist[2] if hist else CLIENT.token_supply(token)
    ws = [b["wallet"] for b in buyers]
    out = {w: {"now": 0, "sold": 0, "moved": {}, "burned": 0, "locked": 0, "locked_in": [], "partial": False}
           for w in ws}
    if not ws:
        return {"supply": supply, "wallets": out}
    want = set(ws)
    if hist:
        trs = hist[1]
        last = max((t["block"] for t in trs), default=0)
        seen = {(t["tx"], t["log_index"]) for t in trs if t["block"] == last}
        trs = trs + [t for t in CLIENT.token_transfers(token, last) if (t["tx"], t["log_index"]) not in seen]
        ins = [t for t in trs if t["to"] in want]
        outs = [t for t in trs if t["frm"] in want]
    else:
        start = min(b["block"] for b in buyers)
        ins = CLIENT.token_transfers(token, start, to=ws)
        outs = CLIENT.token_transfers(token, start, frm=ws)
    for t in ins:
        out[t["to"]]["now"] += t["amount"]
    check = defaultdict(list)
    for t in outs:
        o = out[t["frm"]]
        o["now"] -= t["amount"]
        if t["to"] in market:
            o["sold"] += t["amount"]
        elif t["to"] in BURN_ADDRS:
            o["burned"] += t["amount"]
        else:
            check[t["frm"]].append(t)
    pick = []
    for w, ts_ in check.items():
        if len(ts_) > out_cap:
            out[w]["partial"] = True
        pick += ts_[-out_cap:]
    txs = sorted({t["tx"] for t in pick})
    sells, checked = set(), set()
    for i in range(0, len(txs), 50):
        if deadline and time.time() > deadline:
            break
        part = txs[i:i + 50]
        for h, logs in CLIENT.receipt_logs(part).items():
            if _is_sell(token, logs, market):
                sells.add(h)
        checked |= set(part)
    for t in pick:
        o = out[t["frm"]]
        if t["tx"] not in checked:
            o["partial"] = True
        elif t["tx"] in sells:
            o["sold"] += t["amount"]
        else:
            o["moved"][t["to"]] = o["moved"].get(t["to"], 0) + t["amount"]
    return {"supply": supply, "wallets": out}

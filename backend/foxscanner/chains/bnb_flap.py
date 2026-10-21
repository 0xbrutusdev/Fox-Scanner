"""Лаунчпад Flap на BNB Chain (по умолчанию включён, FLAP_BNB_ENABLED=false выключает).

Тот же протокол, что у Flap на Robinhood (chains/flap.py): адрес на 8888 или 7777, затем один
HTTP-батч Portal.getTokenV8Safe. Адреса — docs.flap.sh, BNB Chain, Portal v5.23.1.
Кривая: резерв для dump impact — h + 1e9 − circulating. После выпуска (status DEX) резерв —
getReserves mainPool, если это пара V2; V3/Infinity без getReserves даёт reserve 0
(«liquidity not measured»), а не выдуманную глубину.
История — как у four.meme: все переводы с запуска до SCAN_MAX_LOGS, общий RPC-клиент BNB.
"""
import os, threading, time
from collections import defaultdict

from foxscanner.chains import evm, fourmeme

CLIENT = fourmeme.CLIENT
REQUESTS = CLIENT.requests
CHAIN = "bnb"
PACK_WINDOW = fourmeme.PACK_WINDOW
BUNDLE_WINDOW = fourmeme.BUNDLE_WINDOW
RUG_SNIPERS = True
RPS = fourmeme.RPS
SCAN_MAX_LOGS = fourmeme.SCAN_MAX_LOGS

PORTAL = "0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0"
VAULT_PORTAL = "0x90497450f2a706f1951b5bdda52b4e5d16f34c06"
TAX_HELPER = "0x53841c73217735f37bc1775538b03b23fefd8346"
TRIGGER = "0xcf4ee25035cf883895110f367f5ba8172416a7f9"
LOCKER = "0x0000a8b6741441bb4ba0dfe313a2bc7b2cf10000"
SUFFIXES = ("8888", "7777")
SUPPLY_TOKENS = 10 ** 27          # 1e9 × 18; виртуальный резерв кривой считается от него
STATUS_CURVE, STATUS_DEX = 1, 4
ZERO = evm.ZERO
TRADE = "https://flap.sh/bnb/{address}"

SEL_STATE = "0x62fafcca"          # getTokenV8Safe(address)
SEL_TAX_PROCESSOR = "0xf3635019"
SEL_MAIN_POOL = "0xa5a302d3"
SEL_TAX_INFO = "0x6c06b371"
SEL_TOKEN0 = "0x0dfe1681"
SEL_RESERVES = "0x0902f1ac"
TOKEN_CREATED = "0x504e7f360b2e5fe33cbaaae4c593bc55305328341bf79009e43e0e3b7f699603"
TOKEN_BOUGHT = "0xa800a2038683844fac66747f771bfdfae862eb28b16bcfa387afa9fbacce8ff7"
V2_SWAP = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
STATE_FIELDS = ("status", "reserve", "circulating", "price", "version", "r", "h", "k", "dex_thresh", "quote",
                "native_swap", "extension", "buy_tax", "sell_tax", "pool", "progress", "lp_fee", "dex_id")
ENTRY_TOL = 0.06
STATE_TTL = 20
SCAN_TTL = fourmeme.SCAN_TTL
FRESH_CAP = fourmeme.FRESH_CAP
EARLY_WINDOW = fourmeme.EARLY_WINDOW
EARLY_CANDIDATES = fourmeme.EARLY_CANDIDATES
EARLY_OUT_CAP = fourmeme.EARLY_OUT_CAP

ROUTERS = set(fourmeme.ROUTERS)
LOCKERS = {LOCKER}
INFRA = LOCKERS | ROUTERS | {
    PORTAL, VAULT_PORTAL, TAX_HELPER, TRIGGER, fourmeme.PANCAKE_V2_FACTORY, fourmeme.WBNB,
    fourmeme.HELPER3, evm.DEAD, evm.ZERO, "0x000000000022d473030f116ddee9f6b43ac78ba3",
}

_STATE, _LAUNCH, _SCAN = {}, {}, {}
_lock = threading.Lock()


def enabled():
    return os.environ.get("FLAP_BNB_ENABLED", "true").strip().lower() in ("1", "true", "yes")


def candidate(token):
    """Похож на Flap без RPC: флаг включён и суффикс 8888 / 7777."""
    return enabled() and isinstance(token, str) and token.lower().endswith(SUFFIXES)


def _call(to, data):
    return (to, data)


def detect(token, fresh=False):
    """Состояние Portal или None. Без суффикса — None и ни одного запроса."""
    if not candidate(token):
        return None
    token = token.lower()
    with _lock:
        hit = _STATE.get(token)
    if hit and not fresh and time.time() - hit[0] < STATE_TTL:
        return hit[1]
    arg = evm.arg_addr(token)
    try:
        st_raw, tp_raw, pool_raw, tax_raw = CLIENT.call_batch([
            _call(PORTAL, SEL_STATE + arg), _call(token, SEL_TAX_PROCESSOR), _call(token, SEL_MAIN_POOL),
            _call(TAX_HELPER, SEL_TAX_INFO + arg)])
    except RuntimeError:
        st_raw = tp_raw = pool_raw = tax_raw = None
    w = evm.words(st_raw)
    st = None
    if len(w) >= len(STATE_FIELDS) and w[0]:
        st = dict(zip(STATE_FIELDS, w))
        st["quote"], st["pool"] = evm.word_addr(st["quote"]), evm.word_addr(st["pool"])
        tp, mp, tax = evm.words(tp_raw), evm.words(pool_raw), evm.words(tax_raw)
        st["tax_processor"] = evm.word_addr(tp[0]) if tp and tp[0] else None
        st["main_pool"] = evm.word_addr(mp[0]) if mp and mp[0] else (st["pool"] if st["pool"] != ZERO else None)
        st["tax_recipient"] = evm.word_addr(tax[14]) if len(tax) >= 19 and tax[14] else None
        st["tax_recipient_vault"] = len(tax) >= 19 and tax[18] == 1
    with _lock:
        _STATE[token] = (time.time(), st)
        if len(_STATE) > 5000:
            _STATE.clear()
    return st


def _sets(token, st, launch):
    own = {token} | {x for x in (st.get("tax_processor"), st.get("main_pool"), (launch or {}).get("shadow_pair")) if x}
    if st.get("tax_recipient") and st.get("tax_recipient_vault"):
        own.add(st["tax_recipient"])
    pool = st.get("main_pool")
    market = {PORTAL} | ROUTERS | ({pool} if pool else set())
    return own, market, INFRA | market | own


def get_launch(token, st=None):
    """{"block", "tx", "curve", "deployer", "creator", "dev_buy"} или None."""
    token = token.lower()
    if token in _LAUNCH:
        return dict(_LAUNCH[token])
    st = st or detect(token)
    if st is None:
        return None
    # Минт с блока 0 через getLogs на узле с окном в 10 блоков не заканчивается. Сначала один
    # alchemy_getAssetTransfers; широкий getLogs — только если узел принимает диапазон целиком.
    found = CLIENT.earliest_erc20_mint(token)
    if found:
        tx, block = found["tx"], found["block"]
    else:
        minted = CLIENT.get_logs_once(0, "latest", address=token,
                                     topics=[evm.TRANSFER_TOPIC, evm.topic_for(evm.ZERO)])
        if not minted:
            return None
        mint = min(minted, key=lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16)))
        tx, block = mint["transactionHash"], int(mint["blockNumber"], 16)
    rc = CLIENT.receipt_logs([tx]).get(tx, [])
    creator, bought = None, []
    for l in rc:
        tp, addr = l.get("topics") or [], l["address"].lower()
        t0 = tp[0].lower() if tp else ""
        if addr == PORTAL and t0 == TOKEN_CREATED:
            w = evm.words(l.get("data"))
            if len(w) >= 4 and evm.word_addr(w[3]) == token:
                creator = evm.word_addr(w[1])
        elif (p := evm.parse_transfer(l)) and p["token"] == token and p["frm"] == PORTAL and len(l.get("data") or "") > 2:
            bought.append((p["to"], int(l["data"][:66], 16)))
    buyers = [(w, a) for w, a in bought if w not in INFRA]
    deployer = creator if creator and creator not in INFRA else (buyers[0][0] if buyers else creator)
    dev_buy = sum(a for w, a in buyers if w == deployer)
    res = {"block": block, "tx": tx, "curve": PORTAL, "deployer": deployer or CLIENT.tx_sender(tx),
           "creator": creator, "dev_buy": dev_buy}
    _LAUNCH[token] = res
    return dict(res)


def _pair_reserve(token, pool):
    t0, res = CLIENT.call_batch([(pool, SEL_TOKEN0), (pool, SEL_RESERVES)])
    w0, r = evm.words(t0), evm.words(res)
    if not w0 or len(r) < 2:
        return 0, None
    is0 = evm.word_addr(w0[0]) == token
    return (r[0] if is0 else r[1]), is0


def remember_scan(token, launch, transfers, supply):
    now = time.time()
    with _lock:
        for k in [k for k, v in _SCAN.items() if now - v[0] >= SCAN_TTL]:
            del _SCAN[k]
        _SCAN[token] = (now, dict(launch), transfers, supply)


def scan_history(token):
    with _lock:
        hit = _SCAN.get(token.lower())
    if not hit or time.time() - hit[0] >= SCAN_TTL:
        return None
    return hit[1], hit[2], hit[3]


def drop_caches():
    with _lock:
        _STATE.clear()
        _LAUNCH.clear()
        _SCAN.clear()


def token_facts(token, launch, deadline=None):
    """Факты для движка + "flap" (те же поля, что у Robinhood Flap, чтобы шапка и q_factor совпали)."""
    token = token.lower()
    st = detect(token, fresh=True) or {}
    supply = CLIENT.token_supply(token) or SUPPLY_TOKENS
    transfers = CLIENT.token_transfers(token, launch["block"], cap=SCAN_MAX_LOGS)
    remember_scan(token, launch, transfers, supply)
    dex = st.get("status") == STATUS_DEX
    pool = st.get("main_pool")
    own, market, excluded = _sets(token, st, launch)
    if dex and pool:
        reserve, is0 = _pair_reserve(token, pool)
        st["token_is0"] = is0
        source = "pair_reserves" if reserve else "unmeasured"
    else:
        reserve = st.get("h", 0) + SUPPLY_TOKENS - st.get("circulating", 0)
        source = "curve_state"
    q_factor = 1.0 - st.get("sell_tax", 0) / 10_000 if dex else 1.0
    locked = defaultdict(int)
    for t in transfers:
        for a, sign in ((t["to"], 1), (t["frm"], -1)):
            if a in LOCKERS:
                locked[a] += sign * t["amount"]
    locked = {a: v for a, v in locked.items() if v > 0}
    native = st.get("quote") in (ZERO, fourmeme.WBNB)
    rcp = st.get("tax_recipient")
    taxed = bool(st.get("buy_tax") or st.get("sell_tax"))
    is_dev = bool(rcp) and rcp in {launch.get("deployer"), launch.get("creator")}
    progress = (st.get("progress") or 0) / 1e18
    info = {"phase": "dex" if dex else "bonding_curve",
            "phase_text": "dex" if dex else f"bonding curve {progress * 100:.0f}%",
            "progress": progress, "version": st.get("version"),
            "price_eth": st["price"] / 1e18 if not dex and native and st.get("price") else None,
            "reserve_eth": st["reserve"] / 1e18 if not dex and native else None,
            "tax": {"buy": st.get("buy_tax", 0) / 10_000, "sell": st.get("sell_tax", 0) / 10_000},
            "tax_recipient": rcp if taxed else None,
            "tax_recipient_is_dev": is_dev and taxed,
            "tax_processor": st.get("tax_processor"), "pool": pool,
            "reserve_source": source, "q_factor": q_factor, "dev_buy": launch.get("dev_buy", 0),
            "locked": locked, "locked_share_supply": sum(locked.values()) / supply if supply else 0.0}
    return {"supply": supply, "transfers": transfers, "excluded": excluded, "market": market,
            "reserve": max(0, reserve), "reserve_ok": reserve > 0, "base": None, "q_factor": q_factor,
            "flap": info}


def classify_entries(token, transfers, wallets, chunk=50):
    """buy — TokenBought на Portal или Swap пары V2 в том же чеке; получение с Portal, пары или роутера тоже buy."""
    token = token.lower()
    st = (_STATE.get(token) or (None, None))[1] or {}
    pool, buy_tax = st.get("main_pool"), st.get("buy_tax", 0) / 10_000
    want = {w.lower() for w in wallets}
    first = {}
    for t in transfers:
        if t["to"] in want and t["to"] not in first:
            first[t["to"]] = t
    receipts = CLIENT.receipt_logs(sorted({t["tx"] for t in first.values()}), chunk)
    out = {}
    for w, t in first.items():
        buys = []
        for l in receipts.get(t["tx"], []):
            tp, addr = l.get("topics") or [], l["address"].lower()
            t0 = tp[0].lower() if tp else ""
            if addr == PORTAL and t0 == TOKEN_BOUGHT:
                d = evm.words(l.get("data"))
                if len(d) >= 5 and evm.word_addr(d[1]) == token:
                    buys.append((d[3], d[4]))
            elif pool and addr == pool and t0 == V2_SWAP:
                nums = evm.words(l.get("data")) + [0] * 4
                a0in, a1in, a0out, a1out = nums[:4]
                is0 = st.get("token_is0")
                sides = [(a0out, a1in), (a1out, a0in)] if is0 is None else [(a0out, a1in) if is0 else (a1out, a0in)]
                buys += [(o, q) for o, q in sides if o > 0]
        eth_in = None
        if buys and t["amount"]:
            got, quote = min(buys, key=lambda b: abs(b[0] - t["amount"]))
            if abs(got - t["amount"]) <= (ENTRY_TOL + buy_tax) * max(got, t["amount"]):
                eth_in = quote
        direct = t["frm"] in ROUTERS or t["frm"] == PORTAL or (pool and t["frm"] == pool)
        out[w] = {"kind": "buy" if buys or direct else "transfer", "tx": t["tx"], "block": t["block"],
                  "via": t["frm"], "eth_in": eth_in}
    return out


def wallet_distinct_tokens(wallet, before_block, skip_token, window=None, cap=FRESH_CAP):
    n = CLIENT.nonces_at([(wallet.lower(), before_block)]).get((wallet.lower(), before_block))
    return None if n is None else min(n, cap)


def block_timestamps(blocks):
    return CLIENT.block_timestamps(blocks)


def is_contract(addresses):
    return CLIENT.is_contract(addresses)


def token_meta(token):
    return CLIENT.token_meta(token)


def _market(token, launch=None):
    st = (_STATE.get(token) or (None, None))[1] or detect(token) or {}
    _, market, excluded = _sets(token, st, launch or {})
    return st, market, excluded


def early_buyers(token, n=20, deadline=None):
    token = token.lower()
    hist = scan_history(token)
    st = detect(token)
    if st is None:
        return None
    launch = hist[0] if hist else get_launch(token, st)
    if launch is None:
        return None
    _, market, excluded = _sets(token, st, launch)
    head = None if hist else CLIENT.block_number()
    lo, span, trs = launch["block"], EARLY_WINDOW, list(hist[1]) if hist else []
    buyers, checked = [], set()
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
    ts = CLIENT.block_timestamps({launch["block"]} | {t["block"] for t in first.values()})
    out = [{"wallet": a, "block": first[a]["block"], "ts": ts.get(first[a]["block"]), "tx": first[a]["tx"],
            "bought": sum(x["amount"] for x in trs if x["to"] == a and x["tx"] == first[a]["tx"])} for a in buyers]
    return {"launch": {"block": launch["block"], "ts": ts.get(launch["block"]), "deployer": launch.get("deployer"),
                       "curve": PORTAL}, "buyers": out, "txs_read": len(trs)}


def early_status(token, buyers, deadline=None, launch=None, out_cap=EARLY_OUT_CAP):
    token = token.lower()
    hist = scan_history(token)
    _, market, _ = _market(token, launch)
    supply = hist[2] if hist else (CLIENT.token_supply(token) or SUPPLY_TOKENS)
    ws = [b["wallet"] for b in buyers]
    out = {w: {"now": 0, "sold": 0, "moved": {}, "burned": 0, "locked": 0, "locked_in": [], "partial": False}
           for w in ws}
    if not ws:
        return {"supply": supply, "wallets": out}
    want = set(ws)
    if hist:
        trs = list(hist[1])
        last = max((t["block"] for t in trs), default=0)
        seen = {(t["tx"], t["log_index"]) for t in trs if t["block"] == last}
        trs += [t for t in CLIENT.token_transfers(token, last) if (t["tx"], t["log_index"]) not in seen]
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
        elif t["to"] in fourmeme.BURN_ADDRS:
            o["burned"] += t["amount"]
        elif t["to"] in LOCKERS:
            o["locked"] += t["amount"]
            if t["to"] not in o["locked_in"]:
                o["locked_in"].append(t["to"])
        else:
            check[t["frm"]].append(t)
    pick = []
    for w, rows in check.items():
        if len(rows) > out_cap:
            out[w]["partial"] = True
        pick += rows[-out_cap:]
    txs = sorted({t["tx"] for t in pick})
    sells, checked = set(), set()
    for i in range(0, len(txs), 50):
        if deadline and time.time() > deadline:
            break
        part = txs[i:i + 50]
        for h, logs in CLIENT.receipt_logs(part).items():
            if any((p := evm.parse_transfer(l)) and p["token"] == token and p["to"] in market for l in logs):
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

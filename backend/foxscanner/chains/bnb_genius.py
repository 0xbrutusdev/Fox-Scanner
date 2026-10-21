"""Лаунчпад Genius.fun на BNB Chain (по умолчанию включён, GENIUS_BNB_ENABLED=false выключает).

Адреса — https://genius.fun/contracts/manifest.json (стек bnb-mainnet-m4.2 и прежний m4.1).
Токен без суффикса, поэтому detect идёт только после промаха four.meme: один батч
getLaunchedToken на обе фабрики (селектор 0x3cf28b5a, плоский LaunchedToken без динамических полей).
Кривая: getReserves() → (quoteReserve, tokenReserve). Резерв для dump impact — tokenReserve
(токены целиком попадают в x*y=k, комиссия снимается с quote на выходе). После выпуска
пул — PancakeSwap Infinity: глубину CL не выдумываем, reserve_ok ложный.
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

# m4.2 (активный) и m4.1 (старые токены живут только там). startBlock — из манифеста.
FACTORIES = (
    ("0x37ee8aee29c5efd3c1a7eda6df3f510779928a37", 122_874_828, "m4.2"),
    ("0x78eae9537c0ef90dfe9b7ae964682fe8138afe31", 122_266_383, "m4.1"),
)
LAUNCH_ROUTERS = {
    "0xd8b71b46498a36a4607eab5c735bee1dab7f263d",   # m4.2 LaunchAndBuy
    "0x2ef00378984e84f2daa08dfb5fb03bbde2038ae6",   # m4.1 router
    "0xe0d1764c6eb7b1371a891a9d8af9994ac058c108",   # m4.2 swap-and-buy
    "0x17fa0cbae593240dbe6df256c3bf6e391685254f",   # m4.1 swap-and-buy
}
POOL_MANAGER = "0xa0ffb9c1ce1fe56963b0321b32e7a0302114058b"
UNIVERSAL_ROUTER = "0xd9c500dff816a1da21a48a732d3498bf09dc9aeb"
POSITION_MANAGER = "0x55f4c8aba71a1e923edc303eb4feff14608cc226"
VAULT = "0x238a358808379702088667322f80ac48bad5e6c4"
QUOTER = "0xd0737c9762912dd34c3271197e362aa736df0926"
CONTROLLER = "0xe7c7b7ee71db0f1b4f0ff25d7cec191268e7fd98"
LOCKERS = {
    "0x9109522ff8125394edb44b8eeb87ad946d893194",   # m4.2
    "0x60c68b2c6ce7d2268f25a816f326843017d00384",   # m4.1
}
HOOKS = {
    "0x8e6f8ebbd62b60085b703c40b460dae802edc51b",
    "0xff17f41c5efd6cce944af0912f300097d62df5c9",
}
FEE_ESCROWS = {
    "0xc2f95799285109d076275a1ee298849a6fbd611a",
    "0xff8a2ae655e5851cb414ac5ab41b311da4287281",
}
DEPLOYERS = {
    "0xdbcfbeb2849c0a7dfac8b302ff9cf1471f7859a3",
    "0xab3ead42ec2587d16bae8f2c9fb133c533c7faaf",
}
GRADUATION = {
    "0x0048079cde5a0670502600dc7270952687f5f037",
    "0xc41be12e827d38223e1dc95093a9159a3e0b1a92",
    "0xc0690f5ea0c0e0218650af10f7d37780468e09f3",
    "0xee466c74ecb94133365c4020efe0898ac31aa73e",
}
VAULTS = {
    "0xd275e7eebef0a6946130a535a106b2ca8cb922ca",   # m4.2 buyback
    "0x3b7b991ce5ea00389cba440c2ccd4adcb1ee28ef",   # m4.2 foundation
    "0x6ecbe74e6cf896c610c34a3be59bd54c5a5b784e",   # m4.1 buyback
    "0xf1200f24c38ddce80a3f0cf26606f047c8ebe49b",   # m4.1 foundation
}
ROUTERS = set(fourmeme.ROUTERS) | LAUNCH_ROUTERS | {UNIVERSAL_ROUTER}
INFRA = (ROUTERS | LOCKERS | HOOKS | FEE_ESCROWS | DEPLOYERS | GRADUATION | VAULTS
         | {f[0] for f in FACTORIES} | {
             POOL_MANAGER, POSITION_MANAGER, VAULT, QUOTER, CONTROLLER,
             fourmeme.WBNB, fourmeme.PANCAKE_V2_FACTORY, evm.DEAD, evm.ZERO,
             "0x000000000022d473030f116ddee9f6b43ac78ba3",
         })

PHASE_CURVE, PHASE_SWEPT, PHASE_POOL, PHASE_RESCUED = 0, 1, 2, 3
PHASE_NAME = {PHASE_CURVE: "bonding_curve", PHASE_SWEPT: "swept", PHASE_POOL: "graduated",
              PHASE_RESCUED: "rescued"}
SUPPLY_TOKENS = 10 ** 27
TRADE = "https://genius.fun/token/{address}"
SEL_LAUNCHED = evm.selector("getLaunchedToken(address)")
SEL_RESERVES = evm.selector("getReserves()")
SEL_REAL_QUOTE = evm.selector("realQuoteReserve()")
TOKEN_LAUNCHED = "0x8d4aad4953d0ca700d468f3753aa14432d1b35b43ec6409f051fb6aa43a89607"
CURVE_BUY = evm.topic("CurveBuy(address,address,uint256,uint256,uint256,uint256)")
ENTRY_TOL = 0.06
STATE_TTL = 20
SCAN_TTL = fourmeme.SCAN_TTL
FRESH_CAP = fourmeme.FRESH_CAP
EARLY_WINDOW = fourmeme.EARLY_WINDOW
EARLY_CANDIDATES = fourmeme.EARLY_CANDIDATES
EARLY_OUT_CAP = fourmeme.EARLY_OUT_CAP
LAUNCHED_WORDS = 15

_STATE, _LAUNCH, _SCAN = {}, {}, {}
_lock = threading.Lock()


def enabled():
    return os.environ.get("GENIUS_BNB_ENABLED", "true").strip().lower() in ("1", "true", "yes")


def _decode(raw, token, factory, start, stack):
    """Плоский LaunchedToken или None (revert, exists=false, чужой токен)."""
    w = evm.words(raw)
    if len(w) < LAUNCHED_WORDS or not w[14]:
        return None
    got = evm.word_addr(w[0])
    if got != token:
        return None
    return {"token": got, "curve": evm.word_addr(w[1]), "deployer": evm.word_addr(w[2]),
            "creator_fee": evm.word_addr(w[3]), "pair": evm.word_addr(w[4]), "threshold": w[5],
            "pool_fee": w[6], "creator_tax_bps": w[8], "buyback": w[9] == 1, "phase": w[10],
            "factory": factory, "start": start, "stack": stack}


def detect(token, fresh=False):
    """Запись фабрики или None. Флаг выключен — None и ни одного запроса. Сначала m4.2, затем m4.1."""
    if not enabled() or not isinstance(token, str):
        return None
    token = token.lower()
    with _lock:
        hit = _STATE.get(token)
    if hit and not fresh and time.time() - hit[0] < STATE_TTL:
        return hit[1]
    arg = evm.arg_addr(token)
    try:
        raws = CLIENT.call_batch([(f, SEL_LAUNCHED + arg) for f, _, _ in FACTORIES])
    except (RuntimeError, OSError):
        raws = []
    st = None
    for (factory, start, stack), raw in zip(FACTORIES, raws or []):
        st = _decode(raw, token, factory, start, stack)
        if st:
            break
    with _lock:
        _STATE[token] = (time.time(), st)
        if len(_STATE) > 5000:
            _STATE.clear()
    return st


def _sets(token, st, launch):
    curve = (st or {}).get("curve") or (launch or {}).get("curve")
    factory = (st or {}).get("factory")
    own = {token} | {x for x in (curve, factory) if x}
    market = ({curve} if curve else set()) | ROUTERS | {POOL_MANAGER}
    return own, market, INFRA | market | own


def _block_of(lg):
    b = lg.get("blockNumber")
    return int(b, 16) if isinstance(b, str) else b


def get_launch(token, st=None):
    """{"block", "tx", "curve", "deployer", "creator", "dev_buy", "factory"} или None."""
    token = token.lower()
    if token in _LAUNCH:
        return dict(_LAUNCH[token])
    st = st or detect(token)
    if not st:
        return None
    curve, deployer = st["curve"], st["deployer"]
    # get_logs(start, head) на узле с окном в 10 блоков листает миллионы страниц и держит стадию
    # «Finding the launch». Минт — один alchemy_getAssetTransfers; широкий getLogs без нарезки.
    found = CLIENT.earliest_erc20_mint(token)
    block = tx = None
    if found:
        block, tx = found["block"], found["tx"]
    else:
        try:
            logs = CLIENT.get_logs_once(st["start"], "latest", address=st["factory"],
                                        topics=[TOKEN_LAUNCHED, evm.topic_for(token)])
        except (RuntimeError, OSError):
            logs = None
        if logs:
            lg = logs[0]
            block, tx = _block_of(lg), lg.get("transactionHash")
            tp = lg.get("topics") or []
            if len(tp) >= 4:
                deployer = evm.addr_from_topic(tp[3])
    if block is None:
        return None
    dev_buy = 0
    if tx:
        try:
            rc = CLIENT.receipt_logs([tx]).get(tx, [])
        except (RuntimeError, OSError):
            rc = []
        for lg in rc:
            p = evm.parse_transfer(lg)
            if p and p["token"] == token and p["frm"] == curve and p["to"] == deployer:
                dev_buy += int((lg.get("data") or "0x0")[:66], 16)
    res = {"block": block, "tx": tx, "curve": curve, "deployer": deployer or st["deployer"],
           "creator": st["deployer"], "dev_buy": dev_buy, "factory": st["factory"]}
    _LAUNCH[token] = res
    return dict(res)


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
    """Факты для движка + "genius". На кривой цена = quoteReserve/tokenReserve (BNB за токен).
    Выпущенный токен торгуется в Infinity: резерв 0, ликвидность не измерена."""
    token = token.lower()
    st = detect(token, fresh=True) or {}
    supply = CLIENT.token_supply(token) or SUPPLY_TOKENS
    transfers = CLIENT.token_transfers(token, launch["block"], cap=SCAN_MAX_LOGS)
    remember_scan(token, launch, transfers, supply)
    phase = st.get("phase", PHASE_CURVE)
    curve = st.get("curve") or launch.get("curve")
    own, market, excluded = _sets(token, st, launch)
    reserve, reserve_ok, price, reserve_eth, progress = 0, False, None, None, None
    source = "unmeasured"
    if phase == PHASE_CURVE and curve:
        try:
            raw_res, raw_real = CLIENT.call_batch([(curve, SEL_RESERVES), (curve, SEL_REAL_QUOTE)])
        except (RuntimeError, OSError):
            raw_res = raw_real = None
        rw, rq = evm.words(raw_res), evm.words(raw_real)
        if len(rw) >= 2 and rw[1] > 0:
            quote, tokens = rw[0], rw[1]
            reserve, reserve_ok, source = tokens, True, "curve_reserves"
            native = st.get("pair") in (None, evm.ZERO, fourmeme.WBNB)
            if native:
                price = quote / tokens
                reserve_eth = quote / 1e18
            thr = st.get("threshold") or 0
            if rq and thr:
                progress = rq[0] / thr
    name = PHASE_NAME.get(phase, "bonding_curve")
    text = name
    if name == "bonding_curve":
        text = "bonding curve" if progress is None else f"bonding curve {progress * 100:.0f}%"
    elif name == "graduated":
        text = "PancakeSwap Infinity"
    info = {"phase": name, "phase_text": text, "progress": progress, "price_eth": price,
            "reserve_eth": reserve_eth, "curve": curve, "factory": st.get("factory"),
            "stack": st.get("stack"), "reserve_source": source, "dev_buy": launch.get("dev_buy", 0)}
    return {"supply": supply, "transfers": transfers, "excluded": excluded, "market": market,
            "reserve": max(0, reserve), "reserve_ok": reserve_ok, "base": None, "q_factor": 1.0,
            "genius": info}


def classify_entries(token, transfers, wallets, chunk=50):
    """buy — CurveBuy кривой или получение с кривой, роутера или PoolManager. Остальное — transfer."""
    token = token.lower()
    st = (_STATE.get(token) or (None, None))[1] or {}
    curve = st.get("curve")
    want = {w.lower() for w in wallets}
    first = {}
    for t in transfers:
        if t["to"] in want and t["to"] not in first:
            first[t["to"]] = t
    receipts = CLIENT.receipt_logs(sorted({t["tx"] for t in first.values()}), chunk)
    out = {}
    for w, t in first.items():
        eth_in = None
        bought = False
        for lg in receipts.get(t["tx"], []):
            tp, addr = lg.get("topics") or [], lg["address"].lower()
            t0 = tp[0].lower() if tp else ""
            if curve and addr == curve and t0 == CURVE_BUY:
                d = evm.words(lg.get("data"))
                if len(d) >= 2 and t["amount"] and abs(d[1] - t["amount"]) <= ENTRY_TOL * max(d[1], t["amount"]):
                    eth_in = d[0]
                bought = True
        direct = t["frm"] in ROUTERS or t["frm"] == POOL_MANAGER or (curve and t["frm"] == curve)
        out[w] = {"kind": "buy" if bought or direct else "transfer", "tx": t["tx"], "block": t["block"],
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
    """Первые n покупателей или None (не Genius.fun)."""
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
                       "curve": st["curve"]}, "buyers": out, "txs_read": len(trs)}


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

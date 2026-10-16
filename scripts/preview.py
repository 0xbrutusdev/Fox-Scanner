"""Превью сайта без RPC: настоящий server.H, но скан, чарт, early buyers и лента — подставные данные.
Для проверки вёрстки (десктоп / мобильный): python scripts/preview.py [порт], затем http://localhost:8765/?ca=0x...

Токен с адресом на ...0001 — DANGER с проекцией rug, ...0002 — CLEAN, ...0003 — TOO_ESTABLISHED, остальное — ошибка.
"""
import math, os, sys, tempfile, time
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update({"DRAW_DB_PATH": os.path.join(tempfile.mkdtemp(), "preview.db"), "BNB_ENABLED": "true",
                   "ROBINHOOD_ENABLED": "false", "SOLANA_ENABLED": "false", "DEFAULT_EVM_CHAIN": "bnb",
                   "ALERTS_ENABLED": "false", "DRAW_ENABLED": "false", "REWARDS_ENABLED": "false"})

import early, engine, server  # noqa: E402

NOW = int(time.time())
W = ["0x" + f"{i:02x}" * 20 for i in range(1, 21)]


def _sig(i, **kw):
    s = {"kind": "buy", "virgin": False, "short_history": False, "unread": False, "one_shot_funded": False,
         "sniper": False, "launch_bundle": False, "eth_in": 10 ** 17, "is_deployer": False, "sold": False,
         "block": 100 + i, "tx": "0x" + "ab" * 32, "via": W[0]}
    return s | kw


def result(token, kind):
    hdr = {"name": "Fox Coin", "ticker": "FOX", "price_usd": 0.0000412, "mcap_usd": 41_200, "fdv_usd": 41_200,
           "liquidity_usd": 9_800, "vol24h_usd": 72_000, "age_h": 5.2}
    base = {"token": token, "chain": "bnb", "launchpad": "fourmeme", "header": hdr, "elapsed_s": 14.2,
            "fourmeme": {"phase": "bonding_curve", "progress": 0.63, "pool": None},
            "launch": {"block": 100, "ts": NOW - 18_000, "deployer": W[0]}, "holders_total": 412,
            "market_pool": None, "notes": [], "limited": False, "partial_scan": None}
    if kind == "est":
        return base | {"band": "TOO_ESTABLISHED", "score": None, "headline": "This token is too established for FoxScanner.",
                       "reason": "FoxScanner is built for fresh memecoins.", "parts": {}, "metrics": {}, "gates": [],
                       "holders": [], "operators": [], "rug": None, "fourmeme": None, "launchpad": None,
                       "market_pool": "0x" + "cd" * 20}
    danger = kind == "danger"
    hs = [{"wallet": w, "share": 0.09 - i * 0.004, "share_supply": 0.07 - i * 0.003,
           "signals": _sig(i, virgin=danger and i % 3 == 0, sniper=danger and i < 3, launch_bundle=danger and i < 2,
                           kind="transfer" if danger and i in (4, 7) else "buy", is_deployer=i == 0,
                           short_history=i % 5 == 1, unread=i == 15, sold=i == 9)} for i, w in enumerate(W[:16])]
    ops = [{"wallets": W[1:5], "share": 0.31, "share_supply": 0.24, "level": "proven"},
           {"wallets": W[6:9], "share": 0.12, "share_supply": 0.09, "level": "pack"}] if danger else []
    rug = {"drop": 0.78, "level_factor": 0.22, "share": 0.41, "share_supply": 0.32, "level_usd": 0.0000412 * 0.22,
           "parts": [{"kind": "linked", "share": 0.24, "wallets": W[1:5]}, {"kind": "virgin", "share": 0.1, "wallets": W[9:12]},
                     {"kind": "bundle", "share": 0.07, "wallets": W[0:2]}]} if danger else None
    return base | {
        "band": "DANGER" if danger else "CLEAN", "score": 18 if danger else 86,
        "headline": "Likely one operator behind the top holders" if danger else "No clear signs of a single operator",
        "reason": "biggest operator could move price −64% if sold (31.0% of float)" if danger else "no clear signs of a single operator",
        "parts": {"operator": 4, "virgin": 9, "transfer": 6, "sniper": 3, "concentration": 5} if danger else
                 {"operator": 33, "virgin": 22, "transfer": 20, "sniper": 9, "concentration": 6},
        "metrics": {"operator": 0.31 if danger else 0.04, "impact": 0.64 if danger else 0.06, "virgin": 0.42 if danger else 0.08,
                    "transfer": 0.07 if danger else 0.0, "sniper": 0.11 if danger else 0.01, "concentration": 0.58 if danger else 0.44},
        "gates": ["biggest operator (4 linked wallets) could move price −64% if sold", "soft: liquidity under $10,000"] if danger else [],
        "holders": hs, "operators": ops, "rug": rug}


def fake_scan(token, emit=lambda e: None, chain=None):
    chain, token = engine.chain_of(token, chain)
    kind = {"1": "danger", "2": "clean", "3": "est"}.get(token[-1])
    t0, i = time.time(), [0]

    def ev(type_, detail="", **kw):
        emit({"i": i[0], "t": int((time.time() - t0) * 1000), "type": type_, "detail": detail, "chain": chain,
              "wallet": kw.pop("wallet", None)} | kw)
        i[0] += 1
        time.sleep(0.25)
    for st in ("launch", "transfers", "entries", "wallets"):
        ev("stage", st)
    if kind is None:
        raise engine.ScanError("not a four.meme token")
    r = result(token, kind)
    for h in r["holders"][:10]:
        s = h["signals"]
        fl = [f for f, on in (("virgin", s["virgin"]), ("sniper", s["sniper"]), ("deployer", s["is_deployer"])) if on]
        ev("wallet_flag", f"{s['kind']} 0.1000 BNB, +{12 + h['signals']['block']}s" + (", " + ", ".join(fl) if fl else ""),
           wallet=h["wallet"], flags=fl)
    ev("stage", "links")
    for o in r["operators"]:
        ev("cluster", f"{len(o['wallets'])} wallets, {o['share'] * 100:.1f}% of float", wallet=o["wallets"][0])
    ev("done", r["reason"], headline=r["headline"])
    return r


def fake_chart(token, chain=None):
    chain, token = engine.chain_of(token, chain)
    if token.endswith("3"):
        return {"token": token, "chain": chain, "candles": [], "pool": "0x" + "cd" * 20}
    cs, p = [], 0.000012
    for k in range(80):
        p *= 1 + 0.05 * math.sin(k / 6) + 0.018
        cs.append([NOW - (80 - k) * 300, p, p * 1.03, p * 0.97, p, 1000])
    return {"token": token, "chain": chain, "timeframe": "5m", "candles": cs, "price_usd": 0.0000412, "pool": None}


def fake_early(token, flags=None, chain=None):
    chain, token = engine.chain_of(token, chain)
    sts = ["sold_all", "holding_all", "sold_part", "moved", "holding_all", "added", "sold_all", "burned"]
    rows = [{"rank": i + 1, "wallet": W[(i + 3) % 20], "dev": i == 0, "dt_s": 3 * i + 1, "block_offset": i,
             "bought_share_supply": 0.012 - i * 0.0004, "now_share_supply": 0.0 if sts[i % 8] == "sold_all" else 0.008,
             "status": sts[i % 8], "locked_in": [], "scan_flags": ["operator"] if i in (1, 2) else None, "partial": False}
            for i in range(20)]
    return {"token": token, "chain": chain, "available": True, "launch_ts": NOW - 18_000, "buyers": rows,
            "summary": {"buyers": 20, "exited": 9, "holding": 11, "held_share_supply": 0.094,
                        "same_destination": [{"to": W[19], "wallets": W[3:5]}], "partial": False}}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    engine.scan = fake_scan
    server.get_chart = fake_chart
    early.get = fake_early
    store = server.recent_store()
    for k, (tk, band, sc) in enumerate((("FOX", "DANGER", 18), ("PUP", "CLEAN", 86), ("MOON", "RISKY", 47),
                                        ("BNBCAT", "OK", 66), ("GEM", "DANGER", 9))):
        store.record({"token": "0x" + f"{k + 10:02x}" * 20, "chain": "bnb", "launchpad": "fourmeme", "band": band,
                      "score": sc, "header": {"ticker": tk}, "rug": band == "DANGER"}, ts=NOW - k * 400)
    srv = ThreadingHTTPServer(("127.0.0.1", port), server.H)
    print(f"preview on http://127.0.0.1:{port}/  (?ca=0x...01 danger, ...02 clean, ...03 established)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

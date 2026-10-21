"""BNB Chain: лаунчпад Genius.fun (chains/bnb_genius.py) после промаха four.meme. Без сети."""
import os, time, unittest
from contextlib import ExitStack
from unittest import mock

import fakes
from foxscanner.bot import text as T
from foxscanner.chains import bnb_genius as gn
from foxscanner.chains import evm, fourmeme as fm
from foxscanner.scan import early, engine, market
from foxscanner import trade

TOKEN = "0x" + "4b" * 18 + "45ab"   # без суффикса 4444/8888/7777: лаунчпад по адресу не виден
CURVE = "0x" + "cc" * 20
DEV = "0x" + "de" * 20
E18 = 10 ** 18
QUOTE = 6 * E18
TOKENS = 800_000_000 * E18
REAL = E18
THRESHOLD = 15 * E18
SUPPLY = gn.SUPPLY_TOKENS
LAUNCH_BLOCK, LAUNCH_TS = 50_000_000, int(time.time()) - 1800
W = ["0x" + f"{i + 1:02x}" * 20 for i in range(6)]
FACTORY, _, STACK = gn.FACTORIES[0]
LEGACY = gn.FACTORIES[1][0]


def word(x):
    return f"{int(x, 16) if isinstance(x, str) else x:064x}"


def data(*xs):
    return "0x" + "".join(word(x) for x in xs)


def launched(phase=gn.PHASE_CURVE, factory_ok=True):
    row = [TOKEN, CURVE, DEV, DEV, 0, THRESHOLD, 3000, 200, 125, 1, phase, 0, 0, 0, 1 if factory_ok else 0]
    return data(*row)


class TestBnbGenius(unittest.TestCase):
    def setUp(self):
        gn.drop_caches()
        early.clear_cache()

    def test_selector_and_flag(self):
        self.assertEqual(gn.SEL_LAUNCHED, "0x3cf28b5a")
        with mock.patch.dict(os.environ, {"GENIUS_BNB_ENABLED": "false"}):
            called = mock.Mock()
            with mock.patch.object(gn.CLIENT, "call_batch", called):
                self.assertIsNone(gn.detect(TOKEN))
            called.assert_not_called()
        with mock.patch.dict(os.environ, {"GENIUS_BNB_ENABLED": "false"}):
            self.assertEqual(engine.not_launchpad("bnb"), "not a four.meme or Flap token")

    def test_legacy_factory_and_curve_reserve(self):
        empty = data(*([0] * gn.LAUNCHED_WORDS))
        batches = [[empty, launched()], [empty, launched()], [data(QUOTE, TOKENS), data(REAL)]]
        trs = [{"frm": evm.ZERO, "to": CURVE, "amount": SUPPLY, "tx": "0xlaunch", "block": LAUNCH_BLOCK, "log_index": 0},
               {"frm": CURVE, "to": DEV, "amount": 10 ** 24, "tx": "0xlaunch", "block": LAUNCH_BLOCK, "log_index": 1}]
        with mock.patch.object(gn.CLIENT, "call_batch", side_effect=batches), \
                mock.patch.object(gn.CLIENT, "token_supply", return_value=SUPPLY), \
                mock.patch.object(gn.CLIENT, "token_transfers", return_value=trs):
            st = gn.detect(TOKEN)
            self.assertEqual(st["stack"], "m4.1")
            self.assertEqual(st["factory"], LEGACY)
            self.assertEqual(st["curve"], CURVE)
            facts = gn.token_facts(TOKEN, {"block": LAUNCH_BLOCK, "curve": CURVE, "deployer": DEV,
                                           "creator": DEV, "dev_buy": 10 ** 24, "tx": "0xlaunch", "factory": LEGACY})
        self.assertEqual(facts["genius"]["phase"], "bonding_curve")
        self.assertEqual(facts["genius"]["phase_text"], "bonding curve 7%")
        self.assertAlmostEqual(facts["genius"]["progress"], REAL / THRESHOLD)
        self.assertEqual(facts["reserve"], TOKENS)
        self.assertTrue(facts["reserve_ok"])
        self.assertEqual(facts["q_factor"], 1.0)
        self.assertAlmostEqual(facts["genius"]["price_eth"], QUOTE / TOKENS)
        self.assertAlmostEqual(facts["genius"]["reserve_eth"], 6.0)
        self.assertIn(CURVE, facts["excluded"])
        self.assertIn(LEGACY, facts["excluded"])
        self.assertIsNotNone(gn.scan_history(TOKEN))

    def test_graduated_infinity_is_unmeasured(self):
        def batch(reqs):
            self.assertTrue(reqs[0][1].startswith(gn.SEL_LAUNCHED))
            return [launched(gn.PHASE_POOL), data(*([0] * gn.LAUNCHED_WORDS))]

        with mock.patch.object(gn.CLIENT, "call_batch", side_effect=batch), \
                mock.patch.object(gn.CLIENT, "token_supply", return_value=SUPPLY), \
                mock.patch.object(gn.CLIENT, "token_transfers", return_value=[]):
            facts = gn.token_facts(TOKEN, {"block": LAUNCH_BLOCK, "curve": CURVE, "deployer": DEV,
                                           "dev_buy": 0, "tx": "0xlaunch", "factory": FACTORY})
        self.assertEqual(facts["genius"]["phase"], "graduated")
        self.assertEqual(facts["genius"]["reserve_source"], "unmeasured")
        self.assertEqual(facts["reserve"], 0)
        self.assertFalse(facts["reserve_ok"])
        self.assertIsNone(facts["genius"]["price_eth"])

    def test_launch_uses_one_mint_lookup(self):
        minted = {"block": LAUNCH_BLOCK, "tx": "0xlaunch"}
        receipt = {"address": TOKEN, "topics": [evm.TRANSFER_TOPIC, evm.topic_for(evm.ZERO), evm.topic_for(DEV)],
                   "data": data(10 ** 24), "transactionHash": "0xlaunch", "blockNumber": hex(LAUNCH_BLOCK),
                   "logIndex": "0x1"}
        # dev buy is from the curve, not the zero address
        dev = {"address": TOKEN, "topics": [evm.TRANSFER_TOPIC, evm.topic_for(CURVE), evm.topic_for(DEV)],
               "data": data(10 ** 24), "transactionHash": "0xlaunch", "blockNumber": hex(LAUNCH_BLOCK),
               "logIndex": "0x2"}
        gn._STATE[TOKEN] = (time.time(), {"phase": gn.PHASE_CURVE, "curve": CURVE, "deployer": DEV,
                                          "factory": FACTORY, "start": 122_874_828, "stack": STACK})
        wide = mock.Mock(side_effect=AssertionError("must not page getLogs"))
        with mock.patch.object(gn.CLIENT, "earliest_erc20_mint", return_value=minted), \
                mock.patch.object(gn.CLIENT, "get_logs", wide), \
                mock.patch.object(gn.CLIENT, "get_logs_once", wide), \
                mock.patch.object(gn.CLIENT, "receipt_logs", return_value={"0xlaunch": [receipt, dev]}):
            launch = gn.get_launch(TOKEN)
        wide.assert_not_called()
        self.assertEqual(launch["block"], LAUNCH_BLOCK)
        self.assertEqual(launch["tx"], "0xlaunch")
        self.assertEqual(launch["deployer"], DEV)
        self.assertEqual(launch["dev_buy"], 10 ** 24)

    def test_buy_versus_transfer(self):
        gn._STATE[TOKEN] = (time.time(), {"phase": gn.PHASE_CURVE, "curve": CURVE, "pair": evm.ZERO})
        bought = {"address": CURVE, "topics": [gn.CURVE_BUY, evm.topic_for(W[0]), evm.topic_for(W[0])],
                  "data": data(5 * 10 ** 17, 10 ** 24, 0, 0),
                  "transactionHash": "0xbuy", "blockNumber": hex(5), "logIndex": "0x1"}
        trs = [{"frm": CURVE, "to": W[0], "amount": 10 ** 24, "tx": "0xbuy", "block": 5, "log_index": 1},
               {"frm": W[0], "to": W[1], "amount": 10 ** 23, "tx": "0xgift", "block": 6, "log_index": 1}]
        with mock.patch.object(gn.CLIENT, "receipt_logs", return_value={"0xbuy": [bought], "0xgift": []}):
            out = gn.classify_entries(TOKEN, trs, [W[0], W[1]])
        self.assertEqual(out[W[0]]["kind"], "buy")
        self.assertEqual(out[W[0]]["eth_in"], 5 * 10 ** 17)
        self.assertEqual(out[W[1]]["kind"], "transfer")

    def test_engine_scan_skips_genius_rpc_until_fourmeme_misses(self):
        trs = [{"frm": CURVE, "to": w, "amount": SUPPLY // 50, "tx": f"0x{i:02x}", "block": LAUNCH_BLOCK + i,
                "log_index": 1} for i, w in enumerate(W)]
        facts = {"supply": SUPPLY, "transfers": trs, "excluded": gn.INFRA | {CURVE}, "market": {CURVE},
                 "reserve": TOKENS, "reserve_ok": True, "base": None, "q_factor": 1.0,
                 "genius": {"phase": "bonding_curve", "phase_text": "bonding curve 7%", "progress": REAL / THRESHOLD,
                            "price_eth": QUOTE / TOKENS, "reserve_eth": 6.0, "curve": CURVE}}
        launch = {"block": LAUNCH_BLOCK, "curve": CURVE, "deployer": DEV, "creator": DEV, "dev_buy": 0,
                  "tx": "0xlaunch", "factory": FACTORY}
        four = mock.Mock(return_value=None)
        with ExitStack() as st:
            st.enter_context(mock.patch.object(fm, "get_launch", four))
            st.enter_context(mock.patch.object(gn, "detect", return_value={"phase": gn.PHASE_CURVE, "curve": CURVE,
                                                                           "factory": FACTORY, "stack": STACK}))
            st.enter_context(mock.patch.object(gn, "get_launch", return_value=launch))
            st.enter_context(mock.patch.object(gn, "token_facts", return_value=facts))
            st.enter_context(mock.patch.object(gn, "classify_entries",
                                               side_effect=lambda t, tr, ws, chunk=50: {
                                                   w: {"kind": "buy", "tx": "0x", "block": LAUNCH_BLOCK, "via": CURVE,
                                                       "eth_in": E18 // 10} for w in ws}))
            st.enter_context(mock.patch.object(gn, "block_timestamps",
                                               side_effect=lambda bl: {b: LAUNCH_TS + (b - LAUNCH_BLOCK) for b in bl}))
            st.enter_context(mock.patch.object(gn, "wallet_distinct_tokens", return_value=0))
            st.enter_context(mock.patch.object(gn, "is_contract", side_effect=lambda a: {x: False for x in a}))
            st.enter_context(mock.patch.object(gn, "token_meta", return_value={"name": "Genius Coin", "symbol": "GEN"}))
            st.enter_context(mock.patch.object(gn.CLIENT, "post", side_effect=fakes._no_network))
            st.enter_context(mock.patch.object(market, "fetch_market", return_value={}))
            st.enter_context(mock.patch.object(market, "native_usd", return_value=600.0))
            st.enter_context(mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "GENIUS_BNB_ENABLED": "true"}))
            res = engine.scan(TOKEN, chain="bnb")
        four.assert_called_once()
        self.assertEqual(res["launchpad"], "genius")
        self.assertEqual(res["chain"], "bnb")
        self.assertEqual(res["genius"]["phase"], "bonding_curve")
        self.assertAlmostEqual(res["header"]["price_usd"], QUOTE / TOKENS * 600)
        self.assertAlmostEqual(res["header"]["liquidity_usd"], 6 * 600)
        self.assertEqual(trade.url("bnb", TOKEN, launchpad="genius"), "https://genius.fun/token/" + TOKEN)
        self.assertTrue(trade.url("bnb", TOKEN).startswith("https://four.meme/"))
        row = T.report_button(TOKEN, trade.url("bnb", TOKEN, launchpad="genius"))["inline_keyboard"][0]
        self.assertEqual(row[1]["text"], "Trade on Genius.fun")
        self.assertIn("Genius.fun · bonding curve 7%", T.verdict(res))

    def test_early_asks_genius_only_after_fourmeme(self):
        order = []

        def four_buyers(*_a, **_k):
            order.append("four")
            return None

        def detect(token, fresh=False):
            order.append("genius")
            return {"phase": gn.PHASE_CURVE, "curve": CURVE, "factory": FACTORY}

        buyers = {"launch": {"block": LAUNCH_BLOCK, "ts": LAUNCH_TS, "deployer": DEV, "curve": CURVE}, "buyers": []}
        with mock.patch.object(fm, "early_buyers", side_effect=four_buyers), \
                mock.patch.object(gn, "detect", side_effect=detect), \
                mock.patch.object(gn, "early_buyers", return_value=buyers), \
                mock.patch.object(gn, "early_status", return_value={"supply": SUPPLY, "wallets": {}}), \
                mock.patch.object(market, "established_get", return_value=None), \
                mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "GENIUS_BNB_ENABLED": "true"}):
            out = early.get(TOKEN, chain="bnb")
        self.assertEqual(order, ["four", "genius"])
        self.assertTrue(out["available"])
        self.assertEqual(out["block"], LAUNCH_BLOCK)

"""BNB Chain: лаунчпад Flap (chains/bnb_flap.py) рядом с four.meme. Без сети."""
import os, time, unittest
from contextlib import ExitStack
from unittest import mock

import fakes
from foxscanner.bot import text as T
from foxscanner.chains import bnb_flap as flap
from foxscanner.chains import evm, fourmeme as fm
from foxscanner.scan import engine, market
from foxscanner import trade

TOKEN = "0x" + "ab" * 18 + "8888"
OTHER = "0x" + "4b" * 18 + "4444"
DEV = "0x" + "de" * 20
E18 = 10 ** 18
H = 107_036_752 * E18
CIRC = 450_000_000 * E18
SUPPLY = flap.SUPPLY_TOKENS
LAUNCH_BLOCK, LAUNCH_TS = 50_000_000, int(time.time()) - 1800
W = ["0x" + f"{i + 1:02x}" * 20 for i in range(6)]


def word(x):
    return f"{int(x, 16) if isinstance(x, str) else x:064x}"


def data(*xs):
    return "0x" + "".join(word(x) for x in xs)


def state_words():
    return [flap.STATUS_CURVE, 3 * E18, CIRC, 5 * 10 ** 10, 6, 1, H, 2, 800_000_000 * E18,
            0, 0, 0, 400, 400, 0, int(0.26 * 1e18), 0, 0]


class TestBnbFlap(unittest.TestCase):
    def setUp(self):
        flap.drop_caches()

    def test_suffix_only_when_enabled(self):
        with mock.patch.dict(os.environ, {"FLAP_BNB_ENABLED": "true"}):
            self.assertTrue(flap.candidate(TOKEN))
            self.assertFalse(flap.candidate(OTHER))
        with mock.patch.dict(os.environ, {"FLAP_BNB_ENABLED": "false"}):
            self.assertFalse(flap.candidate(TOKEN))
            called = mock.Mock()
            with mock.patch.object(flap.CLIENT, "call_batch", called):
                self.assertIsNone(flap.detect(TOKEN))
            called.assert_not_called()

    def test_detect_and_curve_reserve(self):
        batch = [data(*state_words()), data(0), data(0), data(*([0] * 19))]
        trs = [{"frm": evm.ZERO, "to": flap.PORTAL, "amount": SUPPLY, "tx": "0xlaunch", "block": LAUNCH_BLOCK,
                "log_index": 0},
               {"frm": flap.PORTAL, "to": DEV, "amount": 10 ** 24, "tx": "0xlaunch", "block": LAUNCH_BLOCK,
                "log_index": 1},
               {"frm": flap.PORTAL, "to": W[0], "amount": 10 ** 24, "tx": "0xbuy", "block": LAUNCH_BLOCK + 2,
                "log_index": 1}]
        with mock.patch.object(flap.CLIENT, "call_batch", return_value=batch), \
                mock.patch.object(flap.CLIENT, "token_supply", return_value=SUPPLY), \
                mock.patch.object(flap.CLIENT, "token_transfers", return_value=trs):
            st = flap.detect(TOKEN)
            self.assertEqual(st["status"], flap.STATUS_CURVE)
            facts = flap.token_facts(TOKEN, {"block": LAUNCH_BLOCK, "curve": flap.PORTAL, "deployer": DEV,
                                             "creator": DEV, "dev_buy": 10 ** 24, "tx": "0xlaunch"})
        self.assertEqual(facts["flap"]["phase"], "bonding_curve")
        self.assertEqual(facts["flap"]["phase_text"], "bonding curve 26%")
        self.assertEqual(facts["reserve"], H + SUPPLY - CIRC)
        self.assertTrue(facts["reserve_ok"])
        self.assertEqual(facts["q_factor"], 1.0)
        self.assertAlmostEqual(facts["flap"]["price_eth"], 5e-8)
        self.assertAlmostEqual(facts["flap"]["reserve_eth"], 3.0)
        self.assertIn(flap.PORTAL, facts["excluded"])
        self.assertIsNotNone(flap.scan_history(TOKEN))

    def test_buy_versus_transfer(self):
        flap._STATE[TOKEN] = (time.time(), {"status": flap.STATUS_CURVE, "main_pool": None, "buy_tax": 0, "quote": evm.ZERO})
        bought = {"address": flap.PORTAL, "topics": [flap.TOKEN_BOUGHT],
                  "data": data(1, TOKEN, W[0], 10 ** 24, 5 * 10 ** 17, 0, 1),
                  "transactionHash": "0xbuy", "blockNumber": hex(5), "logIndex": "0x1"}
        trs = [{"frm": flap.PORTAL, "to": W[0], "amount": 10 ** 24, "tx": "0xbuy", "block": 5, "log_index": 1},
               {"frm": W[0], "to": W[1], "amount": 10 ** 23, "tx": "0xgift", "block": 6, "log_index": 1}]
        rc = {"0xbuy": [bought], "0xgift": []}
        with mock.patch.object(flap.CLIENT, "receipt_logs", return_value=rc):
            out = flap.classify_entries(TOKEN, trs, [W[0], W[1]])
        self.assertEqual(out[W[0]]["kind"], "buy")
        self.assertEqual(out[W[0]]["eth_in"], 5 * 10 ** 17)
        self.assertEqual(out[W[1]]["kind"], "transfer")

    def test_engine_scan_and_trade_link(self):
        trs = [{"frm": flap.PORTAL, "to": w, "amount": SUPPLY // 50, "tx": f"0x{i:02x}", "block": LAUNCH_BLOCK + i,
                "log_index": 1} for i, w in enumerate(W)]
        facts = {"supply": SUPPLY, "transfers": trs, "excluded": flap.INFRA, "market": {flap.PORTAL},
                 "reserve": H, "reserve_ok": True, "base": None, "q_factor": 1.0,
                 "flap": {"phase": "bonding_curve", "phase_text": "bonding curve 26%", "progress": 0.26,
                          "price_eth": 5e-8, "reserve_eth": 3.0, "pool": None}}
        launch = {"block": LAUNCH_BLOCK, "curve": flap.PORTAL, "deployer": DEV, "creator": DEV, "dev_buy": 0,
                  "tx": "0xlaunch"}
        four = mock.Mock(side_effect=AssertionError("four.meme must not run for a Flap token"))
        with ExitStack() as st:
            st.enter_context(mock.patch.object(fm, "get_launch", four))
            st.enter_context(mock.patch.object(flap, "detect", return_value={"status": flap.STATUS_CURVE}))
            st.enter_context(mock.patch.object(flap, "get_launch", return_value=launch))
            st.enter_context(mock.patch.object(flap, "token_facts", return_value=facts))
            st.enter_context(mock.patch.object(flap, "classify_entries",
                                               side_effect=lambda t, tr, ws, chunk=50: {
                                                   w: {"kind": "buy", "tx": "0x", "block": LAUNCH_BLOCK, "via": flap.PORTAL,
                                                       "eth_in": E18 // 10} for w in ws}))
            st.enter_context(mock.patch.object(flap, "block_timestamps",
                                               side_effect=lambda bl: {b: LAUNCH_TS + (b - LAUNCH_BLOCK) for b in bl}))
            st.enter_context(mock.patch.object(flap, "wallet_distinct_tokens", return_value=0))
            st.enter_context(mock.patch.object(flap, "is_contract", side_effect=lambda a: {x: False for x in a}))
            st.enter_context(mock.patch.object(flap, "token_meta", return_value={"name": "Flap Coin", "symbol": "FLP"}))
            st.enter_context(mock.patch.object(flap.CLIENT, "post", side_effect=fakes._no_network))
            st.enter_context(mock.patch.object(market, "fetch_market", return_value={}))
            st.enter_context(mock.patch.object(market, "native_usd", return_value=600.0))
            st.enter_context(mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "FLAP_BNB_ENABLED": "true"}))
            res = engine.scan(TOKEN, chain="bnb")
        four.assert_not_called()
        self.assertEqual(res["launchpad"], "flap")
        self.assertEqual(res["chain"], "bnb")
        self.assertEqual(res["flap"]["phase"], "bonding_curve")
        self.assertAlmostEqual(res["header"]["price_usd"], 5e-8 * 600)
        self.assertAlmostEqual(res["header"]["liquidity_usd"], 3 * 600)
        self.assertEqual(trade.url("bnb", TOKEN, launchpad="flap"), "https://flap.sh/bnb/" + TOKEN)
        self.assertTrue(trade.url("bnb", TOKEN).startswith("https://four.meme/"))
        row = T.report_button(TOKEN, trade.url("bnb", TOKEN, launchpad="flap"))["inline_keyboard"][0]
        self.assertEqual(row[1]["text"], "Trade on Flap")

    def test_flap_suffix_does_not_try_other_pads(self):
        batch = [data(*([0] * 18)), None, None, None]
        four = mock.Mock(return_value=None)
        genius = mock.Mock(return_value=None)
        with mock.patch.object(flap.CLIENT, "call_batch", return_value=batch), \
                mock.patch.object(fm, "get_launch", four), \
                mock.patch.object(engine.bnb_genius, "detect", genius), \
                mock.patch.object(market, "fetch_market", return_value={}), \
                mock.patch.object(market, "native_usd", return_value=600.0), \
                mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "FLAP_BNB_ENABLED": "true"}):
            with self.assertRaisesRegex(engine.ScanError, "not a four.meme, Flap or Genius.fun token"):
                engine.scan(TOKEN, chain="bnb")
        four.assert_not_called()
        genius.assert_not_called()

    def test_disabled_keeps_fourmeme_only_message(self):
        with mock.patch.object(fm, "get_launch", return_value=None), \
                mock.patch.object(market, "fetch_market", return_value={}), \
                mock.patch.object(market, "native_usd", return_value=600.0), \
                mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "FLAP_BNB_ENABLED": "false",
                                            "GENIUS_BNB_ENABLED": "false"}):
            with self.assertRaisesRegex(engine.ScanError, "not a four.meme token"):
                engine.scan(OTHER, chain="bnb")

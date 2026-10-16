"""BNB Chain: выбор сети для 0x-адреса, адаптер four.meme (chains/fourmeme.py) на подставном RPC, скан движка."""
import os, time, unittest
from contextlib import ExitStack
from unittest import mock

import fakes  # noqa: F401  (ставит env до импорта engine)
import engine, market, server, trade
from chains import evm, fourmeme as fm

TOKEN = "0x" + "4b" * 18 + "4444"
DEV = "0x" + "de" * 20
ZERO = evm.ZERO
SUPPLY = 10 ** 27
LAUNCH_BLOCK, LAUNCH_TS = 50_000_000, int(time.time()) - 1800
WALLETS = ["0x" + f"{i + 1:02x}" * 20 for i in range(15)]


def word(x):
    return f"{int(x, 16) if isinstance(x, str) else x:064x}"


def data(*ws):
    return "0x" + "".join(word(w) for w in ws)


def transfer_log(token, frm, to, amount, tx, block, idx):
    return {"address": token, "topics": [evm.TRANSFER_TOPIC, evm.topic_for(frm), evm.topic_for(to)],
            "data": data(amount), "transactionHash": tx, "blockNumber": hex(block), "logIndex": hex(idx)}


def state(**kw):
    st = {"version": 2, "manager": fm.MANAGER_V2, "quote": ZERO, "last_price": 2 * 10 ** 10, "fee_rate": 100,
          "min_fee": 0, "launch_time": LAUNCH_TS, "offers": 6 * 10 ** 26, "max_offers": 8 * 10 ** 26,
          "funds": 6 * 10 ** 18, "max_funds": 24 * 10 ** 18, "liquidity_added": False}
    return st | kw


def transfers():
    out = [{"frm": ZERO, "to": fm.MANAGER_V2, "amount": SUPPLY, "tx": "0xmint", "block": LAUNCH_BLOCK, "log_index": 0}]
    for i, w in enumerate(WALLETS):
        tx = "0xbundle" if i < 3 else f"0xtx{i:02d}"
        out.append({"frm": fm.MANAGER_V2, "to": w, "amount": SUPPLY // 100 * (20 - i) // 10, "tx": tx,
                    "block": LAUNCH_BLOCK + (1 if i < 3 else 10 * (i + 1)), "log_index": i + 1})
    return out


class TestChainOf(unittest.TestCase):
    def test_default_and_explicit(self):
        with mock.patch.dict(os.environ, {"DEFAULT_EVM_CHAIN": "bnb", "BNB_ENABLED": "true",
                                          "ROBINHOOD_ENABLED": "true"}):
            self.assertEqual(engine.chain_of(TOKEN.upper().replace("0X", "0x")), ("bnb", TOKEN))
            self.assertEqual(engine.chain_of(TOKEN, "robinhood"), ("robinhood", TOKEN))
            self.assertEqual(engine.chain_of(TOKEN, "BSC"), ("bnb", TOKEN))
            self.assertEqual(engine.default_evm_chain(), "bnb")
        with mock.patch.dict(os.environ, {"DEFAULT_EVM_CHAIN": "nonsense"}):
            self.assertEqual(engine.default_evm_chain(), "bnb")

    def test_disabled_and_wrong_chain(self):
        with mock.patch.dict(os.environ, {"DEFAULT_EVM_CHAIN": "bnb", "ROBINHOOD_ENABLED": "false",
                                          "BNB_ENABLED": "true"}):
            with self.assertRaisesRegex(engine.ScanError, "Robinhood Chain support is coming soon"):
                engine.chain_of(TOKEN, "robinhood")
            with self.assertRaisesRegex(engine.ScanError, "unknown chain"):
                engine.chain_of(TOKEN, "base")
            with self.assertRaisesRegex(engine.ScanError, "not a token address"):
                engine.chain_of(TOKEN, "solana")
        with mock.patch.dict(os.environ, {"DEFAULT_EVM_CHAIN": "bnb", "BNB_ENABLED": "false"}):
            with self.assertRaisesRegex(engine.ScanError, "BNB Chain support is coming soon"):
                engine.chain_of(TOKEN)

    def test_config_lists_chains(self):
        with mock.patch.dict(os.environ, {"BNB_ENABLED": "true", "ROBINHOOD_ENABLED": "false",
                                          "SOLANA_ENABLED": "false", "DEFAULT_EVM_CHAIN": "bnb"}):
            body = server.config_body()
        self.assertEqual(body["chains"], {"bnb": True, "robinhood": False, "solana": False})
        self.assertEqual(body["default_chain"], "bnb")
        self.assertEqual(body["explorers"]["bnb"], "https://bscscan.com")
        self.assertEqual(body["trade"]["bnb"], trade.DEFAULTS["bnb"])


class TestEvm(unittest.TestCase):
    def test_keccak_vectors(self):
        self.assertEqual(evm.keccak256(b"").hex(),
                         "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(evm.topic("Transfer(address,address,uint256)"), evm.TRANSFER_TOPIC)
        self.assertEqual(fm.TOKEN_PURCHASE, "0x7db52723a3b2cdd6164364b3b766e65e540d7be48ffa89582956d8eaebe62942")
        self.assertEqual(evm.selector("totalSupply()"), "0x18160ddd")
        for n in (135, 136, 137, 272):   # граница блока: паддинг 0x81 и лишний блок
            self.assertEqual(len(evm.keccak256(b"a" * n)), 32)

    def test_iter_logs_halves_window(self):
        c = evm.Client(lambda: "http://x.invalid")

        def rpc(method, params):
            lo, hi = int(params[0]["fromBlock"], 16), int(params[0]["toBlock"], 16)
            if hi - lo > 10:
                raise RuntimeError("block range too large")
            return [{"lo": lo, "hi": hi}]
        with mock.patch.object(c, "rpc", side_effect=rpc):
            spans = [(p[0]["lo"], p[0]["hi"]) for p in c.iter_logs(0, 40)]
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], 40)
        self.assertTrue(all(b - a <= 10 for a, b in spans))
        self.assertTrue(all(spans[i][1] + 1 == spans[i + 1][0] for i in range(len(spans) - 1)))
        with mock.patch.object(c, "rpc", side_effect=RuntimeError("execution reverted")):
            with self.assertRaises(RuntimeError):
                list(c.iter_logs(0, 40))

    def test_block_at_time(self):
        c = evm.Client(lambda: "http://x.invalid")
        head = 1_000_000
        info = lambda b: {"number": head if b == "latest" else b, "timestamp": 1_000 + (head if b == "latest" else b) * 3 // 4}
        with mock.patch.object(c, "block_info", side_effect=info):
            b = c.block_at_time(1_000 + 600_000)
        self.assertEqual(b, 800_000)


class TestFourMeme(unittest.TestCase):
    def setUp(self):
        for cache in (fm._STATE, fm._LAUNCH, fm._PAIR, fm._TOKEN0, fm._SCAN):
            cache.clear()

    def test_detect_decodes_and_rejects(self):
        st = state()
        raw = data(st["version"], st["manager"], st["quote"], st["last_price"], st["fee_rate"], st["min_fee"],
                   st["launch_time"], st["offers"], st["max_offers"], st["funds"], st["max_funds"], 0)
        with mock.patch.object(fm.CLIENT, "call", return_value=raw):
            self.assertEqual(fm.detect(TOKEN), st)
        fm._STATE.clear()
        with mock.patch.object(fm.CLIENT, "call", return_value=data(*([0] * 12))):
            self.assertIsNone(fm.detect(TOKEN))
        fm._STATE.clear()
        with mock.patch.object(fm.CLIENT, "call", side_effect=RuntimeError("execution reverted")):
            self.assertIsNone(fm.detect(TOKEN))

    def test_impact_curve_monotonic(self):
        qs = [10, 11, 100, 101, 1000, 1010]
        # выручка: цена падает с объёмом (кривая), третья точка — revert (None)
        raw = [data(fm.MANAGER_V2, ZERO, f, 0) for f in (1000, 1100, 9000, 9080)] + [None, None]
        curve = fm.impact_curve(qs, raw)
        self.assertEqual(len(curve), 1)
        self.assertAlmostEqual(curve[0][1], 0.2)
        self.assertEqual(fm.impact_curve(qs, [None] * 6), [])

    def test_get_launch_dev_buy(self):
        mint = transfer_log(TOKEN, ZERO, fm.MANAGER_V2, SUPPLY, "0xcreate", LAUNCH_BLOCK, 0)
        dev_buy = transfer_log(TOKEN, fm.MANAGER_V2, DEV, 10 ** 24, "0xcreate", LAUNCH_BLOCK, 1)
        with ExitStack() as st:
            p = lambda name, **kw: st.enter_context(mock.patch.object(fm.CLIENT, name, **kw))
            p("block_number", return_value=LAUNCH_BLOCK + 5000)
            p("block_at_time", return_value=LAUNCH_BLOCK + 3)
            p("get_logs", return_value=[mint])
            p("receipt_logs", return_value={"0xcreate": [mint, dev_buy]})
            sender = p("tx_sender", return_value="0x" + "99" * 20)
            launch = fm.get_launch(TOKEN, state())
        self.assertEqual(launch, {"block": LAUNCH_BLOCK, "curve": fm.MANAGER_V2, "deployer": DEV, "tx": "0xcreate"})
        sender.assert_not_called()

    def test_classify_purchase_and_transfer(self):
        buyer, friend = WALLETS[0], WALLETS[1]
        trs = [{"frm": fm.MANAGER_V2, "to": buyer, "amount": 10 ** 24, "tx": "0xbuy", "block": 5, "log_index": 1},
               {"frm": buyer, "to": friend, "amount": 10 ** 23, "tx": "0xgift", "block": 6, "log_index": 1}]
        purchase = {"address": fm.MANAGER_V2, "topics": [fm.TOKEN_PURCHASE],
                    "data": data(TOKEN, buyer, 1, 10 ** 24, 5 * 10 ** 17, 10 ** 15, 0, 0),
                    "transactionHash": "0xbuy", "blockNumber": hex(5), "logIndex": hex(2)}
        rc = {"0xbuy": [transfer_log(TOKEN, fm.MANAGER_V2, buyer, 10 ** 24, "0xbuy", 5, 1), purchase],
              "0xgift": [transfer_log(TOKEN, buyer, friend, 10 ** 23, "0xgift", 6, 1)]}
        with mock.patch.object(fm.CLIENT, "receipt_logs", return_value=rc), \
                mock.patch.object(fm, "detect", return_value=state()):
            out = fm.classify_entries(TOKEN, trs, [buyer, friend])
        self.assertEqual(out[buyer]["kind"], "buy")
        self.assertEqual(out[buyer]["eth_in"], 5 * 10 ** 17)
        self.assertEqual(out[friend], {"kind": "transfer", "tx": "0xgift", "block": 6, "via": buyer, "eth_in": None})

    def test_wallet_history_is_nonce(self):
        with mock.patch.object(fm.CLIENT, "nonces_at", return_value={(WALLETS[0], 100): 7}):
            self.assertEqual(fm.wallet_distinct_tokens(WALLETS[0], 100, TOKEN), fm.FRESH_CAP)
        with mock.patch.object(fm.CLIENT, "nonces_at", return_value={(WALLETS[0], 100): None}):
            self.assertIsNone(fm.wallet_distinct_tokens(WALLETS[0], 100, TOKEN))

    def test_token_facts_curve_and_pair(self):
        quotes = [data(fm.MANAGER_V2, ZERO, 10 ** 15 * (i + 1), 0) for i in range(2 * (1 + len(fm.QUOTE_GRID)))]
        with ExitStack() as st:
            st.enter_context(mock.patch.object(fm, "detect", return_value=state()))
            st.enter_context(mock.patch.object(fm.CLIENT, "token_supply", return_value=SUPPLY))
            st.enter_context(mock.patch.object(fm.CLIENT, "token_transfers", return_value=transfers()))
            st.enter_context(mock.patch.object(fm.CLIENT, "call_batch", return_value=quotes))
            f = fm.token_facts(TOKEN, {"block": LAUNCH_BLOCK, "curve": fm.MANAGER_V2, "deployer": DEV, "tx": "0x"})
        self.assertEqual(f["fourmeme"]["phase"], "bonding_curve")
        self.assertAlmostEqual(f["fourmeme"]["progress"], 0.25)
        self.assertAlmostEqual(f["fourmeme"]["price_native"], 2e-8)
        self.assertIn(fm.MANAGER_V2, f["market"])
        self.assertTrue(f["reserve_ok"])
        self.assertIsNotNone(fm.scan_history(TOKEN))

        pair = "0x" + "aa" * 20
        trs = transfers() + [{"frm": fm.MANAGER_V2, "to": pair, "amount": 2 * 10 ** 26, "tx": "0xlp",
                              "block": LAUNCH_BLOCK + 900, "log_index": 0}]
        with ExitStack() as st:
            st.enter_context(mock.patch.object(fm, "detect", return_value=state(liquidity_added=True)))
            st.enter_context(mock.patch.object(fm.CLIENT, "token_supply", return_value=SUPPLY))
            st.enter_context(mock.patch.object(fm.CLIENT, "token_transfers", return_value=trs))
            st.enter_context(mock.patch.object(fm.CLIENT, "call", return_value=data(pair)))
            f = fm.token_facts(TOKEN, {"block": LAUNCH_BLOCK, "curve": fm.MANAGER_V2, "deployer": DEV, "tx": "0x"})
        self.assertEqual(f["fourmeme"]["phase"], "pancakeswap")
        self.assertEqual(f["fourmeme"]["pool"], pair)
        self.assertEqual(f["reserve"], 2 * 10 ** 26)
        self.assertNotIn("impact_curve", f)
        self.assertIn(pair, f["excluded"])


class TestEngineBnb(unittest.TestCase):
    def scan(self, gt=None):
        facts = {"supply": SUPPLY, "transfers": transfers(), "excluded": fm.INFRA | {fm.MANAGER_V2},
                 "market": {fm.MANAGER_V2}, "reserve": 6 * 10 ** 26, "reserve_ok": True, "base": None,
                 "fourmeme": {"phase": "bonding_curve", "progress": 0.25, "price_native": 2e-8,
                              "reserve_native": 6.0, "pool": None, "graduated": False}}
        launch = {"block": LAUNCH_BLOCK, "curve": fm.MANAGER_V2, "deployer": DEV, "tx": "0xmint"}
        events = []
        engine._HIST.clear()
        market.clear_cache()
        with ExitStack() as st:
            p = lambda name, **kw: st.enter_context(mock.patch.object(fm, name, **kw))
            p("get_launch", return_value=launch)
            p("token_facts", return_value=facts)
            p("classify_entries", side_effect=fakes.classify_entries)
            p("block_timestamps", side_effect=lambda bl: {b: LAUNCH_TS + (b - LAUNCH_BLOCK) for b in bl})
            p("wallet_distinct_tokens", side_effect=lambda w, b, t, window=None, cap=4: 0 if WALLETS.index(w) % 3 == 0 else cap)
            p("is_contract", side_effect=lambda addrs: {a: False for a in addrs})
            p("token_meta", return_value={"name": "Fox Coin", "symbol": "FOX"})
            st.enter_context(mock.patch.object(fm.CLIENT, "post", side_effect=fakes._no_network))
            st.enter_context(mock.patch.object(market, "fetch_market", return_value=gt or {}))
            st.enter_context(mock.patch.object(market, "native_usd", return_value=600.0))
            st.enter_context(mock.patch.dict(os.environ, {"BNB_ENABLED": "true"}))
            res = engine.scan(TOKEN, events.append, chain="bnb")
        return res, events

    def test_scan_on_curve(self):
        res, events = self.scan()
        self.assertEqual(res["chain"], "bnb")
        self.assertEqual(res["launchpad"], "fourmeme")
        self.assertEqual(res["fourmeme"]["phase"], "bonding_curve")
        self.assertEqual(res["header"]["ticker"], "FOX")
        self.assertAlmostEqual(res["header"]["price_usd"], 2e-8 * 600)
        self.assertAlmostEqual(res["header"]["liquidity_usd"], 6.0 * 600)
        self.assertTrue(all(e["chain"] == "bnb" for e in events))
        self.assertEqual(events[-1]["type"], "done")
        self.assertIsNotNone(res["score"])

    def test_gt_price_wins_on_curve(self):
        res, _ = self.scan(gt={"name": "Fox", "ticker": "FOX", "price_usd": 0.5, "liquidity_usd": 1000.0})
        self.assertEqual(res["header"]["price_usd"], 0.5)

    def test_not_fourmeme(self):
        with mock.patch.object(fm, "get_launch", return_value=None), \
                mock.patch.object(market, "fetch_market", return_value={}), \
                mock.patch.dict(os.environ, {"BNB_ENABLED": "true"}):
            with self.assertRaisesRegex(engine.ScanError, "not a four.meme token"):
                engine.scan(TOKEN, chain="bnb")


class TestBotBnb(unittest.TestCase):

    def test_trade_button_names_venue(self):
        from bot import text as T
        url = trade.url("bnb", TOKEN)
        [row] = T.report_button(TOKEN, url)["inline_keyboard"]
        self.assertEqual(row[1], {"text": "Trade on four.meme", "url": f"https://four.meme/token/{TOKEN}"})
        [row] = T.report_button(TOKEN, "https://axiom.trade/t/x/@crawlscan")["inline_keyboard"]
        self.assertEqual(row[1]["text"], "Trade on Axiom")


if __name__ == "__main__":
    unittest.main()

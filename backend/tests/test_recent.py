"""Тесты ленты «Recently scanned»: хранилище, запись после скана, /api/recent. Без сети."""
import json, os, tempfile, threading, time, unittest, urllib.error, urllib.request
from unittest import mock
from http.server import ThreadingHTTPServer

import fakes
from foxscanner import server
from foxscanner.history.recent import entry, RecentStore
from foxscanner.paths import FRONTEND_DIR

SOL = "fjKUqPWK9m331Y5TZZNFismtqoP2MGWAMHEkB62pump"


def res(token="0x" + "11" * 20, chain="robinhood", score=42, band="RISKY", rug=None, ticker="AAA", name="Alpha"):
    return {"token": token, "chain": chain, "header": {"ticker": ticker, "name": name},
            "score": score, "band": band, "rug": rug}


class TestStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = RecentStore(os.path.join(self.tmp.name, "r.db"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_record_and_order(self):
        self.store.record(res("0x" + "11" * 20), ts=100)
        self.store.record(res(SOL, chain="solana", score=80, band="CLEAN", ticker="SOLX"), ts=200)
        self.store.record(res("0x" + "33" * 20, band="DANGER", score=10, rug={"drop": 0.6}), ts=150)
        items = self.store.recent(12)
        self.assertEqual([x["token"] for x in items], [SOL, "0x" + "33" * 20, "0x" + "11" * 20])
        self.assertEqual(items[0], {"token": SOL, "chain": "solana", "launchpad": None, "ticker": "SOLX", "name": "Alpha",
                                    "score": 80, "band": "CLEAN", "rug": False, "mcap_usd": None, "ts": 200})
        self.assertTrue(items[1]["rug"])
        self.assertEqual(len(self.store.recent(2)), 2)
        self.assertEqual([x["token"] for x in self.store.recent(12, "DANGER")], ["0x" + "33" * 20])
        self.assertEqual([x["token"] for x in self.store.recent(12, "CLEAN")], [SOL])
        self.assertEqual(len(self.store.recent(12, "OK")), 3)

    def test_one_row_per_token(self):
        self.store.record(res(score=42, band="RISKY"), ts=100)
        self.store.record(res("0x" + "22" * 20), ts=150)
        self.store.record(res(score=12, band="DANGER", rug={"drop": 0.5}), ts=200)   # тот же токен — обновление
        items = self.store.recent(12)
        self.assertEqual(len(items), 2)
        self.assertEqual((items[0]["token"], items[0]["score"], items[0]["band"], items[0]["rug"], items[0]["ts"]),
                         ("0x" + "11" * 20, 12, "DANGER", True, 200))

    def test_too_early_and_missing_header(self):
        e = entry({"token": "0x" + "44" * 20, "chain": "robinhood", "header": None, "score": None,
                   "band": "TOO_EARLY_OR_LATE", "rug": None}, ts=5)
        self.assertEqual((e["score"], e["ticker"], e["name"], e["rug"]), (None, None, None, False))

    def test_radar_keeps_recent_clean_with_mcap(self):
        now = int(time.time())
        fresh = res("0x" + "aa" * 20, chain="bnb", score=88, band="CLEAN", ticker="NEW", name="New")
        fresh["header"]["mcap_usd"] = 3500.5
        self.store.record(fresh, ts=now - 20)
        self.store.record(res("0x" + "bb" * 20, chain="bnb", score=91, band="CLEAN"), ts=now - 8 * 86400)
        self.store.record(res("0x" + "cc" * 20, chain="bnb", score=10, band="DANGER"), ts=now - 10)
        self.store.record(res(SOL, chain="solana", score=95, band="CLEAN"), ts=now - 5)
        rows = self.store.radar()
        self.assertEqual([r["token"] for r in rows], ["0x" + "aa" * 20])
        self.assertEqual(rows[0]["mcap_usd"], 3500.5)
        self.assertEqual(rows[0]["band"], "CLEAN")

    def test_flap_launchpad(self):
        self.store.record(res("0x" + "66" * 20) | {"launchpad": "flap"}, ts=300)
        self.assertEqual(self.store.recent(1)[0]["launchpad"], "flap")

    def test_old_db_gets_launchpad_column(self):
        import sqlite3
        path = os.path.join(self.tmp.name, "old.db")
        db = sqlite3.connect(path)
        db.executescript("CREATE TABLE recent_scans (token TEXT PRIMARY KEY, chain TEXT NOT NULL, ticker TEXT, "
                         "name TEXT, score INTEGER, band TEXT NOT NULL, rug INTEGER NOT NULL, ts INTEGER NOT NULL);"
                         "INSERT INTO recent_scans VALUES ('0xold', 'robinhood', 'OLD', 'Old', 50, 'OK', 0, 1);")
        db.commit()
        db.close()
        st = RecentStore(path)
        try:
            self.assertIsNone(st.recent()[0]["launchpad"])
            self.assertIsNone(st.recent()[0]["mcap_usd"])
            st.record(res("0x" + "77" * 20) | {"launchpad": "flap"}, ts=2)
            self.assertEqual(st.recent()[0]["launchpad"], "flap")
        finally:
            st.close()

    def test_parse_new_pools_skips_wbnb(self):
        from foxscanner.scan.market import WBNB, parse_new_pools
        foo = "0x" + "ab" * 20
        older = "0x" + "cd" * 20
        data = {"data": [
            {"attributes": {"pool_created_at": "2026-10-23T09:00:00Z"},
             "relationships": {"base_token": {"data": {"id": "bsc_" + older}}}},
            {"attributes": {"pool_created_at": "2026-10-23T10:00:00Z"},
             "relationships": {"base_token": {"data": {"id": "bsc_" + WBNB}}}},
            {"attributes": {"pool_created_at": "2026-10-23T10:00:16Z"},
             "relationships": {"base_token": {"data": {"id": "bsc_" + foo}}}},
        ], "included": [
            {"id": "bsc_" + older, "type": "token",
             "attributes": {"address": older, "symbol": "OLD", "name": "Old"}},
            {"id": "bsc_" + WBNB, "type": "token",
             "attributes": {"address": WBNB, "symbol": "WBNB", "name": "Wrapped BNB"}},
            {"id": "bsc_" + foo, "type": "token",
             "attributes": {"address": foo, "symbol": "FOO", "name": "Foo", "image_url": "http://nope"}},
        ]}
        rows = parse_new_pools(data)
        self.assertEqual([x["symbol"] for x in rows], ["FOO", "OLD"])
        self.assertEqual([x["symbol"] for x in parse_new_pools(data, 1)], ["FOO"])
        self.assertEqual(rows[0]["image"], "")
        self.assertEqual(rows[0]["created"], int(__import__("datetime").datetime.fromisoformat("2026-10-23T10:00:16+00:00").timestamp()))

    def test_parse_four_new_uses_launch_image_and_time(self):
        from foxscanner.scan.market import WBNB, merge_new, parse_four_new
        fresh = "0x" + "ab" * 18 + "ffff"
        older = "0x" + "cd" * 18 + "4444"
        data = {"code": 0, "data": [
            {"tokenAddress": fresh, "shortName": "NEW", "name": "New", "symbol": "BNB",
             "img": "/market/a.jpg", "createDate": "1793003209000"},
            {"tokenAddress": fresh, "shortName": "DUP", "name": "Dup", "img": "", "createDate": 1793003209000},
            {"tokenAddress": older, "shortName": "OLD", "name": "Old", "img": "http://nope", "createDate": 1793000000},
            {"tokenAddress": WBNB, "shortName": "WBNB", "name": "Wrapped", "img": "/market/w.jpg", "createDate": 1793009999000},
        ]}
        rows = parse_four_new(data)
        self.assertEqual([x["symbol"] for x in rows], ["NEW", "OLD"])
        self.assertEqual(rows[0]["image"], "https://static.four.meme/market/a.jpg")
        self.assertEqual(rows[0]["created"], 1793003209)
        self.assertEqual(rows[1]["image"], "")
        self.assertEqual(rows[1]["created"], 1793000000)
        merged = merge_new([
            {"token": fresh, "symbol": "NEW", "name": "New", "image": rows[0]["image"], "created": 100},
            {"token": fresh.upper(), "symbol": "", "name": "", "image": "", "created": 250},
            {"token": older, "symbol": "POOL", "name": "Pool", "image": "", "created": 50},
        ])
        self.assertEqual(merged[0]["symbol"], "NEW")
        self.assertEqual(merged[0]["created"], 100)
        self.assertEqual(merged[0]["image"], "https://static.four.meme/market/a.jpg")
        self.assertEqual(merged[1]["token"], older)
        self.assertEqual(merged[1]["created"], 50)

    def test_viewed_counts_each_bnb_scan(self):
        now = int(time.time())
        ca = "0x" + "11" * 20
        self.store.record(res(ca, chain="bnb", ticker="NEW"), ts=now - 10)
        self.store.record(res(ca, chain="bnb", ticker="NEW", score=10, band="DANGER"), ts=now)
        self.store.record(res("0x" + "22" * 20, chain="bnb", ticker="OLD"), ts=now - 7200)
        self.store.record(res("0x" + "33" * 20, chain="robinhood"), ts=now)
        day = {x["token"]: x for x in self.store.viewed("24h")}
        self.assertEqual(day[ca]["checks"], 2)
        self.assertEqual(day[ca]["band"], "DANGER")
        self.assertEqual(day["0x" + "22" * 20]["checks"], 1)
        self.assertNotIn("0x" + "33" * 20, day)
        hour = {x["token"] for x in self.store.viewed("1h")}
        self.assertIn(ca, hour)
        self.assertNotIn("0x" + "22" * 20, hour)
        self.assertEqual(self.store.viewed("nope")[0]["token"], ca)

    def test_no_verdict_not_saved(self):
        for bad in (None, {}, {"token": "0x" + "55" * 20}, {"band": "OK"}, "error"):
            self.assertIsNone(self.store.record(bad))
        self.assertEqual(self.store.recent(), [])


class TestServerFeed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        with server._lock:
            server.JOBS.clear(); server.BY_TOKEN.clear(); server.RECENT.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"DRAW_DB_PATH": os.path.join(self.tmp.name, "f.db")})
        self.env.__enter__()
        self.fakes = fakes.patched()
        self.fakes.__enter__()

    def tearDown(self):
        self.fakes.__exit__(None, None, None)
        with server._stores_lock:
            for st in server._recent_stores.values():
                st.close()
            server._recent_stores.clear()
        self.env.__exit__(None, None, None)
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.status, json.loads(r.read()), dict(r.headers)

    def scan(self, token):
        req = urllib.request.Request(self.base + "/api/scan", data=json.dumps({"token": token}).encode(),
                                     method="POST", headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                job = json.loads(r.read())["job"]
        except urllib.error.HTTPError as e:
            with e:
                return e.code
        t0 = time.time()
        while time.time() - t0 < 10:
            _, d, _ = self.get(f"/api/result?job={job}")
            if d["done"]:
                time.sleep(0.05)       # запись в ленту — сразу после done
                return d
            time.sleep(0.05)
        self.fail("скан не завершился")

    def test_scan_is_recorded(self):
        d = self.scan(fakes.TOKEN)
        self.assertIn("result", d)
        code, feed, headers = self.get("/api/recent?limit=12")
        self.assertEqual(code, 200)
        self.assertEqual([x["token"] for x in feed["items"]], [fakes.TOKEN])
        x = feed["items"][0]
        self.assertEqual((x["chain"], x["score"], x["band"], x["rug"]),
                         ("robinhood", d["result"]["score"], d["result"]["band"], bool(d["result"]["rug"])))
        self.assertIn("max-age=15", headers["cache-control"])

    def test_errors_not_recorded(self):
        self.assertEqual(self.scan("not an address"), 400)
        d = self.scan(fakes.OTHER)                       # not a Pons V2 token — ошибка скана
        self.assertIn("error", d)
        _, feed, _ = self.get("/api/recent")
        self.assertEqual(feed, {"items": []})

    def test_db_failure_does_not_break_scan(self):
        with mock.patch.object(server, "recent_store", side_effect=OSError("disk full")):
            d = self.scan(fakes.TOKEN)
            self.assertIn("result", d)
            self.assertNotIn("error", d)
            _, feed, _ = self.get("/api/recent")
        self.assertEqual(feed, {"items": []})            # чтение тоже не падает

    def test_cache_and_limit(self):
        st = server.recent_store()
        for i in range(5):
            st.record(res("0x" + f"{i:02d}" * 20), ts=100 + i)
        _, feed, _ = self.get("/api/recent?limit=3")
        self.assertEqual([x["ts"] for x in feed["items"]], [104, 103, 102])
        st.record(res("0x" + "99" * 20), ts=200)         # мимо record_recent: кэш не сброшен
        _, again, _ = self.get("/api/recent?limit=3")
        self.assertEqual(again, feed)
        with mock.patch.object(server.time, "time", return_value=time.time() + server.RECENT_TTL + 1):
            _, fresh, _ = self.get("/api/recent?limit=3")
        self.assertEqual(fresh["items"][0]["ts"], 200)
        for bad in ("abc", "0", "1000"):
            code, d, _ = self.get(f"/api/recent?limit={bad}")
            self.assertEqual(code, 200)
            self.assertLessEqual(len(d["items"]), 50)

    def test_new_scan_shows_at_once(self):
        """Скан записался — лента без ожидания RECENT_TTL (кэш сброшен), новый токен сверху."""
        st = server.recent_store()
        st.record(res("0x" + "11" * 20), ts=int(time.time()) - 3600)
        _, old, _ = self.get("/api/recent?limit=12")
        self.assertEqual(len(old["items"]), 1)
        self.scan(fakes.TOKEN)
        _, feed, _ = self.get("/api/recent?limit=12")
        self.assertEqual(feed["items"][0]["token"], fakes.TOKEN)
        self.assertLess(time.time() - feed["items"][0]["ts"], 60)

    def test_read_racing_write_is_not_cached(self):
        """Чтение базы началось до записи скана, закончилось после: старый ответ в кэш не попадает."""
        st = server.recent_store()
        st.record(res("0x" + "11" * 20), ts=100)
        real = st.recent

        def slow(limit):
            out = real(limit)
            server.record_recent(res("0x" + "22" * 20))      # скан записался, пока читали
            return out
        with mock.patch.object(st, "recent", side_effect=slow):
            stale = server.get_recent(12)
        self.assertEqual([x["ts"] for x in stale["items"]], [100])
        fresh = server.get_recent(12)
        self.assertEqual(fresh["items"][0]["token"], "0x" + "22" * 20)

    def test_frontend_polls_bypass_browser_cache(self):
        """Cloudflare переписывает Cache-Control на max-age=14400: опросы на странице идут с cache: 'no-store'."""
        with open(os.path.join(FRONTEND_DIR, "static", "js", "api.js"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("const NO_STORE = {cache: 'no-store'};", src)
        self.assertIn("recent: () => getJSON('/api/recent?limit=12')", src)
        self.assertIn("const r = await fetch(url, NO_STORE);", src)       # getJSON: events, result, chart, early, ...
        self.assertEqual(src.count("fetch("), 2)                          # getJSON and POST /api/scan
        self.assertIn("cache: 'no-store'});", src)                        # POST /api/scan


if __name__ == "__main__":
    unittest.main()

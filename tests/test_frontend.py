"""Страница FoxScanner (index.html + static/): все ассеты на месте и версионируются, контракт скана и бренд."""
import os, re, unittest

import fakes  # noqa: F401
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda *p: open(os.path.join(ROOT, *p), encoding="utf-8").read()


class TestPage(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")
        self.js = {n: read("static", "js", n) for n in os.listdir(os.path.join(ROOT, "static", "js"))}

    def test_assets_exist_and_are_versioned(self):
        refs = re.findall(r'(?:src|href)="(/static/[^"?]+)(\?v=)?"', self.html)
        self.assertTrue(refs)
        for path, v in refs:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, *path.split("/"))), path)
            if not path.startswith("/static/fonts/"):
                self.assertEqual(v, "?v=", path)                        # сервер подставит хэш содержимого
        scripts = re.findall(r'<script src="/static/js/([a-z]+\.js)\?v="></script>', self.html)
        self.assertEqual(scripts, ["api.js", "chart.js", "scan.js", "result.js", "recent.js", "app.js"])   # порядок важен
        self.assertEqual(set(scripts), set(self.js))
        body = server.versioned(self.html.encode())
        self.assertNotIn(b'?v="', body)
        self.assertNotIn(b"?v=0\"", body)                                # ни одного отсутствующего файла
        for f in ("inter-latin.woff2", "orbitron-latin.woff2"):
            self.assertIn(f"/static/fonts/{f}", read("static", "css", "app.css"))

    def test_scan_contract(self):
        scan, app, res = self.js["scan.js"], self.js["app.js"], self.js["result.js"]
        self.assertIn("const POLL_MS = 300;", scan)
        self.assertIn("api.events(job, after)", scan)
        self.assertIn("for (const e of d.events || []) { after++;", scan)
        self.assertIn("new URLSearchParams(location.search)", app)
        self.assertIn("p.get('ca'), chain = (p.get('chain') || '').toLowerCase()", app)
        self.assertIn("const NO_EARLY = new Set(['TOO_ESTABLISHED', 'TOO_ACTIVE']);", res)
        self.assertIn("const RISK = {CLEAN: 'low', OK: 'low', RISKY: 'medium', DANGER: 'high'};", self.js["api.js"])
        self.assertIn("data-rug-arrow", self.js["chart.js"])

    def test_brand_and_mobile(self):
        css = read("static", "css", "app.css")
        for token in ("#FFD800", "#0B0B0B", "#1A1A1A", "#2A2A2A", '"Orbitron"', '"Inter"', "@media (max-width:640px)"):
            self.assertIn(token, css)
        self.assertIn("<title>FoxScanner", self.html)
        low = (self.html + "".join(self.js.values()) + css).lower()
        for old in ("crawlscan", "crawler", "spider", "fonts.googleapis", "rh-crawler"):
            self.assertNotIn(old, low, old)


if __name__ == "__main__":
    unittest.main()

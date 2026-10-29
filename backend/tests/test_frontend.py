"""Страница FoxScanner (frontend/index.html + static/): все ассеты на месте и версионируются, контракт скана и бренд."""
import os, re, unittest

import fakes  # noqa: F401
from foxscanner import server
from foxscanner.paths import FRONTEND_DIR as ROOT

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
        self.assertEqual(set(self.js) - set(scripts), {"tokens.js", "radar.js"})
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
        self.assertIn("const RISK = {CLEAN: 'low', OK: 'fair', RISKY: 'medium', DANGER: 'high'};", self.js["api.js"])
        self.assertIn("data-rug-arrow", self.js["chart.js"])
        self.assertIn("if (document.hidden) await waitTick();", scan)
        self.assertIn("const FOX_CA = '';", app)
        self.assertIn("Holder score", res)
        self.assertIn("This scan does not check contract owner, mint, honeypot or tax.", res)
        self.assertIn("Contract is not published yet.", app)
        self.assertNotIn("order:-1", read("static", "css", "app.css"))


if __name__ == "__main__":
    unittest.main()

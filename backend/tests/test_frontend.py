"""Страница FoxScanner (frontend/index.html + static/): все ассеты на месте и версионируются, контракт скана и бренд."""
import os, re, unittest
from unittest import mock

import fakes  # noqa: F401
from foxscanner import server
from foxscanner.paths import FRONTEND_DIR as ROOT

def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as source:
        return source.read()


class TestPage(unittest.TestCase):
    def setUp(self):
        self.html = server.render_site_page(os.path.join(ROOT, "index.html")).decode()
        js_dir = os.path.join(ROOT, "static", "js")
        self.js = {n: read("static", "js", n) for n in os.listdir(js_dir) if os.path.isfile(os.path.join(js_dir, n))}

    def test_assets_exist_and_are_versioned(self):
        refs = re.findall(r'(?:src|href)="(/static/[^"?]+)(\?v=)?"', self.html)
        self.assertTrue(refs)
        for path, v in refs:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, *path.split("/"))), path)
            if not path.startswith("/static/fonts/"):
                self.assertEqual(v, "?v=", path)                        # сервер подставит хэш содержимого
        scripts = re.findall(r'<script type="module" src="/static/js/entries/([a-z-]+\.js)\?v="></script>', self.html)
        self.assertEqual(scripts, ["home.js"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "static", "js", "entries", scripts[0])))
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

    def test_shared_shell_and_module_entries(self):
        pages = {
            "index.html": ("home", "/"),
            "about.html": ("about", "/about"),
            "api.html": ("api", "/api"),
            "radar.html": ("radar", "/radar"),
            "tokens.html": ("tokens", "/tokens"),
            "token-management.html": ("token-management", "/token-management"),
        }
        for name, (entry, active_href) in pages.items():
            with self.subTest(name=name):
                body = server.render_site_page(os.path.join(ROOT, name)).decode()
                self.assertEqual(body.count('<header class="top">'), 1)
                self.assertEqual(body.count('<footer>'), 1)
                self.assertIn(f'/static/js/entries/{entry}.js?v="', body)
                self.assertIn(f'href="{active_href}" class="on" aria-current="page"', body)
                self.assertNotIn('<script src="/static/js/api.js?v=">', body)

    def test_signal_room_pages_load_versioned_page_styles(self):
        pages = {
            "index.html": "home",
            "about.html": "about",
            "api.html": "api",
            "radar.html": "radar",
            "tokens.html": "tokens",
            "token-management.html": "token-management",
        }
        for name, slug in pages.items():
            with self.subTest(name=name):
                body = server.render_site_page(os.path.join(ROOT, name)).decode()
                self.assertIn(f'/static/css/pages/{slug}.css?v="', body)
                self.assertEqual(body.count(f'/static/css/pages/{slug}.css?v="'), 1)
                self.assertEqual(body.count("<h1"), 1)

    def test_shared_header_has_accessible_mobile_navigation(self):
        body = server.render_site_page(os.path.join(ROOT, "about.html")).decode()
        self.assertIn('data-nav-toggle', body)
        self.assertIn('aria-controls="site-nav"', body)
        self.assertIn('aria-expanded="false"', body)
        self.assertIn('id="site-nav"', body)
        self.assertIn('data-site-nav', body)

    def test_refactored_pages_keep_balanced_markup_and_single_scan_action(self):
        for name in ("index.html", "tokens.html", "radar.html"):
            with self.subTest(name=name):
                source = read(name)
                self.assertEqual(source.count("<header"), source.count("</header>"))
        home = read("index.html")
        self.assertEqual(home.count("data-go"), 1)
        self.assertIn('class="search-go" aria-hidden="true"', home)
        self.assertIn('<h1 class="home-title" data-i18n="Check BNB token for rug risk">', home)
        self.assertIn('href="/token-management" data-i18n="Manage"', home)
        self.assertNotIn("data-home-demo", home)

    def test_mobile_refactor_keeps_copy_controls_and_compact_header(self):
        tokens_css = read("static", "css", "pages", "tokens.css")
        app_css = read("static", "css", "app.css")
        self.assertNotIn(".tok-copy { display:none", tokens_css)
        self.assertIn('aria-labelledby="new-tokens"', tokens_css)
        self.assertIn("@media (max-width:360px)", app_css)

    def test_home_tokens_and_radar_guard_critical_responsive_states(self):
        app_css = read("static", "css", "app.css")
        home_css = read("static", "css", "pages", "home.css")
        tokens_css = read("static", "css", "pages", "tokens.css")
        radar_css = read("static", "css", "pages", "radar.css")
        mobile_nav = read("static", "js", "components", "mobile-navigation.js")
        tokens_js = read("static", "js", "tokens.js")
        radar_js = read("static", "js", "radar.js")
        radar_html = read("radar.html")

        self.assertIn("@media (max-width:960px)", app_css)
        self.assertIn('const MOBILE_QUERY = "(max-width: 960px)"', mobile_nav)
        self.assertIn(".home-terminal .hero-actions .hero-btn", home_css)
        self.assertIn("height:44px", home_css)
        self.assertIn(".tokens-page .ranges button { min-width:44px; min-height:44px; }", tokens_css)
        tokens_html = read("tokens.html")
        self.assertIn('data-i18n="Recently Verified"', tokens_html)
        self.assertNotIn("data-token-state-copy", tokens_html)
        self.assertNotIn("Token Pulse", tokens_html)
        self.assertIn("Checks are unavailable.", tokens_js)
        self.assertIn('tabindex="0" data-ca=', tokens_js)
        self.assertIn("onRowKeydown", tokens_js)
        self.assertIn("Radar update unavailable.", radar_js)
        self.assertIn("data-radar-retry", radar_js)
        self.assertIn("data-radar-token", radar_js)
        self.assertIn("@media (max-width: 360px)", radar_css)
        self.assertIn('data-radar-count aria-live="polite">—</b>', radar_html)
        self.assertIn('aria-pressed="true"', radar_html)
        entries = os.path.join(ROOT, "static", "js", "entries")
        for name in os.listdir(entries):
            if not name.endswith(".js"):
                continue
            with self.subTest(entry=name):
                source = read("static", "js", "entries", name)
                self.assertNotRegex(source, r'(?m)^import(?:\s+.*?\s+from\s+)?["\'][^"\']+\.js["\'];')

    def test_signal_room_pages_expose_honest_preview_and_accessible_controls(self):
        manage = server.render_site_page(os.path.join(ROOT, "token-management.html")).decode()
        api = server.render_site_page(os.path.join(ROOT, "api.html")).decode()
        about = server.render_site_page(os.path.join(ROOT, "about.html")).decode()
        self.assertRegex(manage.lower(), r"preview|demo")
        self.assertRegex(api.lower(), r"preview|demo")
        self.assertRegex(about.lower(), r"preview|methodology")
        self.assertIn('data-code-explorer', api)
        self.assertIn('data-copy', api)
        self.assertNotIn("Create an account", api)

    def test_signal_room_assets_and_page_modules_exist(self):
        assets = (
            ("manage-trust-chain.svg", "token-management.html"),
            ("api-signal-pipeline.svg", "api.html"),
            ("about-wallet-constellation.svg", "about.html"),
        )
        for asset, page in assets:
            with self.subTest(asset=asset):
                path = os.path.join(ROOT, "static", "img", "pages", asset)
                self.assertTrue(os.path.isfile(path), path)
                self.assertIn(f'/static/img/pages/{asset}?v=', read(page))
        for page in ("about", "api", "token-management"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "static", "js", "pages", f"{page}.js")))
            entry = read("static", "js", "entries", f"{page}.js")
            self.assertIn(f'../pages/{page}.js', entry)

    def test_replay_uses_external_entry(self):
        body = server.render_site_page(os.path.join(ROOT, "replay.html")).decode()
        self.assertIn('<style>', body)
        self.assertIn('.grid{display:grid', body)
        self.assertIn('/static/js/entries/replay.js?v="', body)
        self.assertNotIn("fetch('/api/replay'", body)

    def test_home_hides_replay_cta_when_feature_is_disabled(self):
        path = os.path.join(ROOT, "index.html")
        with mock.patch.dict(os.environ, {"REPLAY_ENABLED": "false"}):
            disabled = server.render_site_page(path).decode()
        with mock.patch.dict(os.environ, {"REPLAY_ENABLED": "true"}):
            enabled = server.render_site_page(path).decode()
        self.assertNotIn('href="/replay"', disabled)
        self.assertIn('href="/replay"', enabled)


if __name__ == "__main__":
    unittest.main()

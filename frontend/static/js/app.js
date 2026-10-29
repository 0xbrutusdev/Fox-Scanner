// FoxScanner: page wiring — config, chain selector, scan form, ?ca=&chain= deep link, scan view, counters
(function () {
  'use strict';
  const FS = window.FS;
  const {api} = FS;
  const $ = s => document.querySelector(s);
  const EVM = new Set(['bnb', 'robinhood']);
  const EVM_RE = /^0x[0-9a-fA-F]{40}$/;
  const SOL_RE = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/;
  const DEFAULT_CFG = {chains: {bnb: true, robinhood: false, solana: false}, default_chain: 'bnb',
    chain_names: {bnb: 'BNB Chain', robinhood: 'Robinhood Chain', solana: 'Solana'}, explorers: {}, trade: {},
    flap: false, bankr: false, flap_bnb: true, genius_bnb: true};
  const FOX_CA = '';   // BNB 0x… once $FOX is live; empty = contract not published
  const FOX_TRADE = 'https://four.meme/token/{address}';

  const state = {cfg: DEFAULT_CFG, chain: 'bnb', cancel: null, last: null, retry: null};
  const t = (s, v) => FS.i18n.t(s, v);

  function chainFor(ca) {   // this site scans BNB Chain only
    if (EVM_RE.test(ca)) return 'bnb';
    if (SOL_RE.test(ca)) return 'solana';
    return null;
  }

  function renderChains() {
    state.chain = 'bnb';
    const names = state.cfg.chain_names || {};
    const scanning = state.last && $('#scanner') && !$('#scanner').classList.contains('hidden');
    setNet(scanning ? state.last.chain : 'bnb');
    const input = $('#ca');
    if (input) input.placeholder = t('Token address, name, or symbol');
    const title = $('[data-hero-title]');
    if (title) title.textContent = t('Check {chain} tokens', {chain: names.bnb || 'BNB Chain'});
  }

  function setNet(chain) {
    const names = state.cfg.chain_names || {};
    const net = $('[data-net]');
    if (net) net.textContent = names[chain] || chain || names[state.chain] || state.chain;
  }

  function chainStatus() {
    const el = $('[data-chain-status]');
    if (!el) return;
    const cfg = state.cfg, names = cfg.chain_names || {}, chains = cfg.chains || {};
    const order = ['bnb', 'solana', 'robinhood'];
    const live = order.filter(c => chains[c]).map(c => names[c] || c);
    const soon = order.filter(c => c in chains && !chains[c]).map(c => names[c] || c);
    const loc = FS.i18n.lang();
    const join = xs => xs.length <= 1 ? (xs[0] || '') : (loc === 'zh' || loc === 'ja') ? xs.join('、') : xs.slice(0, -1).join(', ') + ' and ' + xs[xs.length - 1];
    let text = '';
    if (live.length) text = t(live.length === 1 ? '{list} is live.' : '{list} are live.', {list: join(live)});
    if (soon.length) text += (text ? ' ' : '') + t(soon.length === 1 ? '{list} is coming next.' : '{list} are coming next.', {list: join(soon)});
    el.textContent = text;
  }

  function renderFox() {
    const status = $('[data-fox-status]'), card = $('[data-fox]');
    if (!status || !card) return;
    const ca = FOX_CA.trim();
    card.querySelector('.actions') && card.querySelector('.actions').remove();
    if (!EVM_RE.test(ca)) {
      status.textContent = t('Contract is not published yet.');
      return;
    }
    const trade = FOX_TRADE.split('{address}').join(ca);
    status.innerHTML = '<span class="addr-row"><button type="button" data-fox-copy="' + FS.fmt.esc(ca)
      + '" title="Copy address" aria-label="Copy $FOX contract address">' + FS.fmt.esc(FS.fmt.short(ca))
      + ' ⧉</button><span class="pill y">BNB Chain</span></span>';
    const actions = document.createElement('div');
    actions.className = 'actions';
    actions.innerHTML = '<a class="btn ghost sm" href="' + FS.fmt.esc(trade) + '" target="_blank" rel="noopener">four.meme ↗</a>';
    card.appendChild(actions);
    const b = status.querySelector('[data-fox-copy]');
    if (b) b.addEventListener('click', () => FS.copy(b.dataset.foxCopy));
  }

  function msg(text, info) {
    const el = $('[data-form-msg]');
    el.textContent = text || '';
    el.classList.toggle('info', !!info);
  }

  function busy(on) {
    document.querySelectorAll('[data-go]').forEach(b => {
      b.disabled = on;
      b.setAttribute('aria-busy', on ? 'true' : 'false');
      const label = b.querySelector('span');
      if (!label) return;
      const key = label.getAttribute('data-i18n') || 'Check';
      label.textContent = on ? t('Checking…') : t(key);
    });
  }

  function scan(ca, chain, push) {
    ca = (ca || '').trim();
    const trend = $('[data-trend]');
    if (trend) trend.hidden = true;
    msg('');
    if (!ca) { msg(t('Paste a token contract address first')); return; }
    chain = chain && (state.cfg.chains || {})[chain] ? chain : chainFor(ca);
    if (!chain) { msg(t('That does not look like a token address')); return; }
    if (!(state.cfg.chains || {})[chain]) { msg(t('{chain} support is coming soon', {chain: (state.cfg.chain_names || {})[chain] || chain})); return; }
    if (chain !== 'bnb') { msg(t('{chain} support is coming soon', {chain: (state.cfg.chain_names || {})[chain] || chain})); return; }
    setNet(chain);
    $('#ca').value = ca;
    if (state.cancel) state.cancel();
    state.last = {ca, chain};
    if (push !== false) {
      const url = '?ca=' + encodeURIComponent(ca) + (EVM.has(chain) ? '&chain=' + chain : '');
      if (location.search !== url) history.pushState({ca, chain}, '', url);
    }
    document.body.classList.add('is-scan');
    document.body.dataset.scanTitle = '1';
    document.title = t('Scanning {token} · FoxScanner', {token: FS.fmt.short(ca)});
    const sec = $('#scanner');
    sec.classList.remove('hidden');
    state.console.reset(ca);
    state.result.clear();
    $('[data-result-wait]').classList.remove('hidden');
    sec.scrollIntoView({behavior: 'smooth', block: 'start'});
    busy(true);
    const again = () => scan(ca, chain, false);
    state.retry = again;
    state.cancel = FS.scan.run(ca, EVM.has(chain) ? chain : null, {
      onEvent: e => state.console.event(e),
      onDone: r => {
        busy(false);
        $('[data-result-wait]').classList.add('hidden');
        const h = r.header || {};
        document.title = t('{title} · FoxScanner', {title: (h.ticker ? '$' + h.ticker + ' · ' : '') + FS.fmt.riskLabel(r.band)});
        state.result.show(r, again);
        state.recent.load();
        if (state.marked) state.marked.load();
      },
      onError: m => {
        busy(false);
        $('[data-result-wait]').classList.add('hidden');
        delete document.body.dataset.scanTitle;
        document.title = t('FoxScanner · Spot the rug before it hits');
        state.console.error(m);
        state.result.error(m, again);
      },
    });
  }

  function fromUrl() {
    const p = new URLSearchParams(location.search);
    const ca = p.get('ca'), chain = (p.get('chain') || '').toLowerCase();
    if (!ca) return;
    if (!$('[data-scan-form]')) {
      location.replace('/?ca=' + encodeURIComponent(ca) + '&chain=bnb');
      return;
    }
    scan(ca, 'bnb', false);
  }

  function counters() {
    if (!$('[data-stat-scanned]')) return;
    api.stats().then(d => {
      if (!d || !(d.tokens_scanned > 0)) return;
      $('[data-stat-scanned]').textContent = d.tokens_scanned.toLocaleString('en-US');
      $('[data-stat-danger]').textContent = (d.danger || 0).toLocaleString('en-US');
      const rate = d.tokens_scanned ? d.danger / d.tokens_scanned : 0;
      $('[data-stat-rate]').textContent = (rate * 100).toFixed(1) + '%';
      $('[data-counters]').classList.remove('hidden');
    }, () => {});
  }

  function setNav(id) {
    document.querySelectorAll('.nav a[data-nav]').forEach(a => {
      const on = a.dataset.nav === id;
      a.classList.toggle('on', on);
      if (on) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }

  function tokenRows(items) {
    return items.map(x => {
      const sym = x.symbol || x.name || FS.fmt.short(x.token);
      const av = x.image
        ? '<img alt="" src="' + FS.fmt.esc(x.image) + '">'
        : '<span class="trend-av">' + FS.fmt.esc(String(sym).slice(0, 2).toUpperCase()) + '</span>';
      const sub = x.name && x.name !== sym ? '<small>' + FS.fmt.esc(x.name) + '</small>' : '';
      return '<button type="button" class="trend-row" data-token="' + FS.fmt.esc(x.token) + '" data-chain="bnb">'
        + av + '<span class="trend-id"><b>' + FS.fmt.esc(sym) + '</b>' + sub
        + '<small class="mono">' + FS.fmt.esc(FS.fmt.short(x.token)) + '</small></span>'
        + '<span class="trend-mc"><small>MC</small><b>' + FS.fmt.esc(FS.fmt.usd(x.mcap_usd)) + '</b></span></button>';
    }).join('');
  }

  function wireTrend() {
    const box = $('[data-trend]'), input = $('#ca');
    if (!box || !input) return;
    const paint = () => {
      const raw = input.value.trim();
      const q = raw.toLowerCase();
      if (EVM_RE.test(raw)) { box.hidden = true; return; }
      const searching = q.length >= 2;
      const items = searching ? state.hits : state.trend;
      if (searching && state.searching) {
        box.hidden = false;
        box.innerHTML = '<p class="trend-empty">' + FS.fmt.esc(t('Searching…')) + '</p>';
        return;
      }
      if (!items) {
        box.innerHTML = '<p class="trend-empty">' + FS.fmt.esc(t('Loading trending tokens…')) + '</p>';
        return;
      }
      const list = (searching ? items : items.filter(x => !q || [x.symbol, x.name, x.token].some(v => String(v || '').toLowerCase().includes(q)))).slice(0, 20);
      if (!list.length) {
        box.innerHTML = '<p class="trend-empty">' + FS.fmt.esc(t(searching || items.length ? 'No matching token' : 'Trending list is unavailable')) + '</p>';
        return;
      }
      box.innerHTML = '<div class="trend-h">' + FS.fmt.esc(t(searching ? 'Tokens' : 'Trending tokens')) + '</div>' + tokenRows(list);
    };
    const load = () => {
      if (state.trend || state.trendLoading) return;
      state.trendLoading = true;
      api.trending().then(d => {
        state.trend = (d && d.items) || [];
        state.trendLoading = false;
        if (!box.hidden && input.value.trim().length < 2) paint();
      }, () => {
        state.trend = [];
        state.trendLoading = false;
        if (!box.hidden && input.value.trim().length < 2) paint();
      });
    };
    const open = () => { box.hidden = false; load(); paint(); };
    let timer = 0;
    input.addEventListener('focus', open);
    input.addEventListener('click', open);
    input.addEventListener('input', () => {
      const raw = input.value.trim();
      box.hidden = false;
      clearTimeout(timer);
      if (raw.length < 2 || EVM_RE.test(raw)) {
        state.searching = false;
        state.hits = null;
        paint();
        return;
      }
      state.searching = true;
      state.hits = null;
      paint();
      const seq = (state.searchSeq = (state.searchSeq || 0) + 1);
      timer = setTimeout(() => {
        api.search(raw).then(d => {
          if (seq !== state.searchSeq) return;
          state.searching = false;
          state.hits = (d && d.items) || [];
          if (!box.hidden) paint();
        }, () => {
          if (seq !== state.searchSeq) return;
          state.searching = false;
          state.hits = [];
          if (!box.hidden) paint();
        });
      }, 280);
    });
    box.addEventListener('click', e => {
      const b = e.target.closest('[data-token]');
      if (!b) return;
      box.hidden = true;
      scan(b.dataset.token, 'bnb');
    });
    document.addEventListener('click', e => { if (!e.target.closest('.finder')) box.hidden = true; });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') box.hidden = true; });
    state.paintTrend = paint;
    load();
  }

  function submitQuery() {
    const raw = $('#ca').value.trim();
    if (!raw) { msg(t('Paste a token contract address first')); return; }
    if (EVM_RE.test(raw)) { scan(raw, 'bnb'); return; }
    const choose = items => {
      const ql = raw.toLowerCase();
      const exact = (items || []).filter(x => (x.symbol || '').toLowerCase() === ql || (x.name || '').toLowerCase() === ql);
      const pick = exact.length === 1 ? exact[0] : ((items || []).length === 1 ? items[0] : null);
      if (pick) { scan(pick.token, 'bnb'); return; }
      state.hits = items || [];
      state.searching = false;
      const box = $('[data-trend]');
      if (box) box.hidden = false;
      if (state.paintTrend) state.paintTrend();
      msg((items || []).length ? t('Pick a token') : t('No matching token'), !!(items || []).length);
    };
    if (state.hits && !state.searching) { choose(state.hits); return; }
    msg(t('Searching…'), true);
    api.search(raw).then(d => choose((d && d.items) || []), () => choose([]));
  }

  function wireNav() {
    const nav = document.querySelector('.nav');
    if (!nav) return;
    let lock = 0;
    const spy = () => {
      if (Date.now() < lock) return;
      let cur = 'home';
      ['recent', 'marked', 'how'].forEach(id => {
        const el = document.getElementById(id);
        if (!el || el.classList.contains('hidden')) return;
        if (el.getBoundingClientRect().top <= 96) cur = id;
      });
      setNav(cur);
    };
    nav.addEventListener('click', e => {
      const a = e.target.closest('a[data-nav]');
      if (!a) return;
      lock = Date.now() + 800;
      setNav(a.dataset.nav);
    });
    window.addEventListener('scroll', spy, {passive: true});
    window.addEventListener('hashchange', () => {
      const id = (location.hash || '#top').slice(1);
      setNav(id === 'top' || id === 'scanner' ? 'home' : (document.querySelector('.nav a[data-nav="' + id + '"]') ? id : 'home'));
    });
    if (location.hash && location.hash !== '#top') {
      const id = location.hash.slice(1);
      if (document.querySelector('.nav a[data-nav="' + id + '"]')) setNav(id);
    }
  }

  const BSC = '0x38';

  function paintWallet(addr) {
    const btn = $('[data-wallet]');
    const label = $('[data-wallet-label]');
    const menu = $('[data-wallet-menu]');
    if (!btn || !label) return;
    if (menu) menu.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
    if (addr) {
      btn.classList.add('on');
      btn.dataset.account = addr;
      btn.setAttribute('aria-haspopup', 'menu');
      label.removeAttribute('data-i18n');
      label.textContent = addr.slice(0, 6) + '…' + addr.slice(-4);
    } else {
      btn.classList.remove('on');
      delete btn.dataset.account;
      btn.removeAttribute('aria-haspopup');
      label.setAttribute('data-i18n', 'Connect Wallet');
      label.textContent = t('Connect Wallet');
    }
  }

  function toastWallet(msg) {
    if (FS.toast) FS.toast(msg);
  }

  async function connectWallet() {
    const eth = window.ethereum;
    const btn = $('[data-wallet]');
    if (!eth) { toastWallet(t('No wallet found. Install MetaMask or another BNB wallet.')); return; }
    if (btn) btn.disabled = true;
    try {
      const accounts = await eth.request({method: 'eth_requestAccounts'});
      try {
        await eth.request({method: 'wallet_switchEthereumChain', params: [{chainId: BSC}]});
      } catch (err) {
        if (err && err.code === 4902) {
          await eth.request({method: 'wallet_addEthereumChain', params: [{
            chainId: BSC, chainName: 'BNB Smart Chain',
            nativeCurrency: {name: 'BNB', symbol: 'BNB', decimals: 18},
            rpcUrls: ['https://bsc-dataseed.binance.org'],
            blockExplorerUrls: ['https://bscscan.com'],
          }]});
        }
      }
      if (accounts && accounts[0]) {
        paintWallet(accounts[0]);
        try { localStorage.setItem('fs.wallet', '1'); } catch (e) { /* ignore */ }
      }
    } catch (err) {
      if (!(err && err.code === 4001)) toastWallet(t('Wallet connection was cancelled'));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function wireWallet() {
    const btn = $('[data-wallet]');
    const menu = $('[data-wallet-menu]');
    const box = btn && btn.closest('.wallet');
    if (!btn || !box) return;
    const close = () => { if (menu) menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); };
    btn.addEventListener('click', e => {
      e.stopPropagation();
      if (!btn.dataset.account) { connectWallet(); return; }
      if (!menu) return;
      menu.hidden = !menu.hidden;
      btn.setAttribute('aria-expanded', menu.hidden ? 'false' : 'true');
    });
    const disc = $('[data-disconnect]');
    if (disc) disc.addEventListener('click', () => {
      paintWallet(null);
      try { localStorage.removeItem('fs.wallet'); } catch (e) { /* ignore */ }
    });
    document.addEventListener('click', e => { if (!box.contains(e.target)) close(); });
    const eth = window.ethereum;
    if (eth && eth.on) {
      eth.on('accountsChanged', accs => {
        let remembered = false;
        try { remembered = localStorage.getItem('fs.wallet') === '1'; } catch (e) { remembered = false; }
        if (!accs || !accs.length) paintWallet(null);
        else if (btn.dataset.account || remembered) paintWallet(accs[0]);
      });
    }
    let remembered = false;
    try { remembered = localStorage.getItem('fs.wallet') === '1'; } catch (e) { remembered = false; }
    if (eth && remembered && eth.request) {
      eth.request({method: 'eth_accounts'}).then(accs => {
        if (accs && accs[0]) paintWallet(accs[0]);
      }).catch(() => {});
    }
  }

  function applyTheme(theme) {
    const next = theme === 'light' ? 'light' : 'dark';
    if (next === 'light') document.documentElement.setAttribute('data-theme', 'light');
    else document.documentElement.removeAttribute('data-theme');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', next === 'light' ? '#F7F7F5' : '#0B0B0B');
    const btn = $('[data-theme-toggle]');
    if (btn) {
      btn.setAttribute('aria-pressed', next === 'light' ? 'true' : 'false');
      btn.setAttribute('aria-label', t(next === 'light' ? 'Dark mode' : 'Light mode'));
    }
  }

  function wireTheme() {
    let saved = null;
    try { saved = localStorage.getItem('fs.theme'); } catch (e) { saved = null; }
    applyTheme(saved === 'light' ? 'light' : 'dark');
    const btn = $('[data-theme-toggle]');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('fs.theme', next); } catch (e) { /* ignore */ }
      applyTheme(next);
    });
    document.addEventListener('fs:lang', () => applyTheme(document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'));
  }

  function wireLang() {
    const box = document.querySelector('.lang');
    const toggle = box && box.querySelector('[data-lang-toggle]');
    const menu = box && box.querySelector('.lang-menu');
    if (box && toggle && menu) {
      const close = () => { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); };
      toggle.addEventListener('click', e => {
        e.stopPropagation();
        const open = menu.hidden;
        menu.hidden = !open;
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      box.addEventListener('click', e => {
        const b = e.target.closest('[data-lang]');
        if (!b) return;
        FS.i18n.setLang(b.dataset.lang);
        close();
      });
      document.addEventListener('click', e => { if (!box.contains(e.target)) close(); });
      document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    }
    document.addEventListener('fs:lang', () => {
      FS.i18n.apply();
      renderChains();
      chainStatus();
      renderFox();
      const go = $('[data-go]');
      busy(!!(go && go.disabled));
      if (state.console) state.console.labels();
      if (state.paintTrend && $('[data-trend]') && !$('[data-trend]').hidden) state.paintTrend();
      const walletBtn = $('[data-wallet]');
      if (walletBtn && walletBtn.dataset.account) paintWallet(walletBtn.dataset.account);
      if (state.result && state.result.r && state.retry) state.result.show(state.result.r, state.retry);
      if (document.body.dataset.scanTitle && state.last) {
        const h = (state.result && state.result.r && state.result.r.header) || {};
        document.title = state.result && state.result.r
          ? t('{title} · FoxScanner', {title: (h.ticker ? '$' + h.ticker + ' · ' : '') + FS.fmt.riskLabel(state.result.r.band)})
          : t('Scanning {token} · FoxScanner', {token: FS.fmt.short(state.last.ca)});
      }
    });
    FS.i18n.apply();
    const go = $('[data-go]');
    busy(!!(go && go.disabled));
    if (state.console) state.console.labels();
  }

  function init(cfg) {
    state.cfg = Object.assign({}, DEFAULT_CFG, cfg || {});
    state.chain = 'bnb';
    const consoleEl = $('[data-console]');
    state.console = consoleEl && FS.scan ? new FS.scan.Console(consoleEl) : null;
    const resultEl = $('[data-result]');
    state.result = resultEl && FS.Result ? new FS.Result(resultEl, state.cfg) : null;
    const recentEl = document.getElementById('recent');
    state.recent = recentEl && recentEl.querySelector('[data-recent-track]') && FS.Recent
      ? new FS.Recent(recentEl, state.cfg, (ca, chain) => scan(ca, chain)) : null;
    state.marked = document.getElementById('marked') && FS.Marked ? new FS.Marked($('#marked'), state.cfg, (ca, chain) => scan(ca, chain)) : null;
    wireTrend();
    wireNav();
    wireTheme();
    wireWallet();
    wireLang();
    renderChains();
    const form = $('[data-scan-form]');
    if (form) form.addEventListener('submit', e => { e.preventDefault(); submitQuery(); });
    window.addEventListener('popstate', () => {
      if (!$('[data-scan-form]')) return;
      const p = new URLSearchParams(location.search);
      if (p.get('ca')) fromUrl();
      else { if (state.cancel) state.cancel(); state.last = null; busy(false); $('#scanner').classList.add('hidden'); document.body.classList.remove('is-scan'); delete document.body.dataset.scanTitle; document.title = t('FoxScanner · Spot the rug before it hits'); setNet(state.chain); }
    });
    chainStatus();
    renderFox();
    counters();
    fromUrl();
  }

  document.addEventListener('DOMContentLoaded', () => {
    api.config().then(init, () => init(null));
  });
})();

// FoxScanner: network + formatting helpers shared by the page scripts (window.FS)
(function () {
  'use strict';
  const FS = window.FS = window.FS || {};

  // Cloudflare rewrites Cache-Control on API answers: every poll bypasses the browser cache
  const NO_STORE = {cache: 'no-store'};
  const BUSY_TEXT = 'Scanner is busy, try again in a few seconds';

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
    c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  async function getJSON(url) {
    const r = await fetch(url, NO_STORE);
    let d = null;
    try { d = await r.json(); } catch (e) { d = null; }
    if (!r.ok) {
      const err = new Error((d && (d.message || d.error)) || ('http ' + r.status));
      err.status = r.status; err.body = d;
      throw err;
    }
    return d;
  }

  const q = (path, params) => {
    const s = Object.entries(params || {}).filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
    return s ? path + '?' + s : path;
  };

  // POST /api/scan -> job id; busy (503) and rate_limited (429) come back with a human message
  async function startScan(token, chain) {
    const body = {token};
    if (chain) body.chain = chain;
    let r, d = null;
    try {
      r = await fetch('/api/scan', {method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify(body), cache: 'no-store'});
    } catch (e) {
      throw new Error('network error, check your connection');
    }
    try { d = await r.json(); } catch (e) { d = null; }
    const fail = msg => { const e = new Error(msg); e.status = r.status; e.code = d && d.error; throw e; };
    if (d && d.error === 'busy') fail(d.message || BUSY_TEXT);
    if (!r.ok || !d || !d.job) fail(d && (d.message || d.error) || ('http ' + r.status));
    return d.job;
  }

  FS.api = {
    NO_STORE, BUSY_TEXT, getJSON, startScan,
    config: () => getJSON('/api/config'),
    stats: () => getJSON('/api/stats'),
    events: (job, after) => getJSON(q('/api/events', {job, after})),
    result: job => getJSON(q('/api/result', {job})),
    chart: (token, chain) => getJSON(q('/api/chart', {token, chain})),
    early: (token, chain) => getJSON(q('/api/early', {token, chain})),
    index: (token, chain) => getJSON(q('/api/index', {token, chain})),
    recent: () => fetch('/api/recent?limit=12', NO_STORE).then(r => r.ok ? r.json() : {items: []}),
  };

  // ---------------------------------------------------------------- formatting
  const SUBD = '₀₁₂₃₄₅₆₇₈₉';
  const price = p => {   // $0.000131, tiny ones as $0.0₅441
    if (!(p > 0)) return '—';
    if (p >= 1) return '$' + p.toLocaleString('en-US', {maximumFractionDigits: p >= 100 ? 0 : 2});
    const z = Math.floor(-Math.log10(p));
    if (z < 4) return '$' + p.toFixed(z + 3);
    return '$0.0' + String(z).split('').map(c => SUBD[c]).join('')
      + String(Math.round(p * Math.pow(10, z + 3))).replace(/0+$/, '');
  };
  const usd = v => {
    if (v == null || !isFinite(v)) return '—';
    const a = Math.abs(v);
    if (a >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
    if (a >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K';
    return '$' + v.toFixed(0);
  };
  const pct = (v, d) => v == null || !isFinite(v) ? '—' : (v * 100).toFixed(d == null ? 1 : d) + '%';
  const short = a => !a ? '' : a.length > 14 ? a.slice(0, 6) + '…' + a.slice(-4) : a;
  const age = h => {
    if (h == null) return '—';
    if (h < 1) return Math.max(1, Math.round(h * 60)) + 'm';
    if (h < 48) return h.toFixed(h < 10 ? 1 : 0) + 'h';
    return Math.round(h / 24) + 'd';
  };
  const ago = ts => {
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    return Math.floor(s / 86400) + 'd ago';
  };
  const secs = s => s == null ? '—' : s < 60 ? '+' + s + 's' : s < 3600 ? '+' + Math.round(s / 60) + 'm' : '+' + (s / 3600).toFixed(1) + 'h';

  // verdict band -> risk level shown on the site
  const RISK = {CLEAN: 'low', OK: 'low', RISKY: 'medium', DANGER: 'high'};
  const RISK_LABEL = {low: 'Low risk', medium: 'Medium risk', high: 'High risk'};
  const BAND_LABEL = {TOO_EARLY_OR_LATE: 'Too early', TOO_ESTABLISHED: 'Established', TOO_ACTIVE: 'Too active'};
  const risk = band => RISK[band] || 'na';
  const riskLabel = band => RISK_LABEL[RISK[band]] || BAND_LABEL[band] || 'No verdict';
  const RISK_COLOR = {low: 'var(--low)', medium: 'var(--med)', high: 'var(--high)', na: 'var(--grey)'};

  const LAUNCHPAD = {fourmeme: 'four.meme', flap: 'Flap', bankr: 'Bankr · Uniswap V4', pons: 'Pons', pumpfun: 'pump.fun'};
  const CHAIN_SHORT = {bnb: 'BNB', robinhood: 'RH', solana: 'SOL'};

  FS.fmt = {esc, price, usd, pct, short, age, ago, secs, risk, riskLabel, RISK_COLOR, LAUNCHPAD, CHAIN_SHORT};

  // ---------------------------------------------------------------- explorer and trade links
  FS.links = {
    explorer(cfg, chain, kind, id) {   // kind: token | address | tx
      const base = ((cfg && cfg.explorers) || {})[chain];
      if (!base || !id) return null;
      const path = chain === 'solana' && kind === 'address' ? 'account' : kind;
      return base.replace(/\/$/, '') + '/' + path + '/' + encodeURIComponent(id);
    },
    trade(cfg, chain, token) {
      const t = ((cfg && cfg.trade) || {})[chain];
      if (!t || !token) return null;
      const url = t.split('{address}').join(encodeURIComponent(token));
      return /^https:\/\//.test(url) ? url : null;
    },
  };

  FS.toast = msg => {
    let el = document.querySelector('.toast');
    if (!el) { el = document.createElement('div'); el.className = 'toast'; document.body.appendChild(el); }
    el.textContent = msg; el.classList.remove('hidden');
    clearTimeout(FS.toast._t);
    FS.toast._t = setTimeout(() => el.classList.add('hidden'), 1600);
  };
  FS.copy = text => {
    const done = () => FS.toast('Address copied');
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => {});
  };
})();

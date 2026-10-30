// Launch Radar: CLEAN BNB scans from the last 7 days. Polls /api/radar every 15 seconds.
(function () {
  'use strict';
  const root = document.querySelector('[data-radar]');
  if (!root || !window.FS) return;
  const FS = window.FS;
  const {esc, short, usd, LAUNCHPAD} = FS.fmt;
  const t = (s, v) => FS.i18n.t(s, v);
  const EVERY = 15000;
  const WINDOW = 7 * 86400;
  let windowSec = WINDOW;
  let cfg = {trade: {
    bnb: 'https://four.meme/token/{address}',
    robinhood: 'https://axiom.trade/t/{address}/@foxscan?chain=robinhood',
    solana: 'https://axiom.trade/t/{address}/@foxscan'
  }, flap_bnb: true, genius_bnb: true};
  let items = [];
  let filter = 'all';
  let loadedAt = 0;
  let loadStatus = 'idle';

  function fresh(ts) {
    const s = Math.max(0, Math.floor(Date.now() / 1000 - Number(ts || 0)));
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
  }

  function padLabel(x) {
    if (x.launchpad === 'flap') return (cfg.flap || cfg.flap_bnb) ? 'Flap' : '';
    if (x.launchpad === 'genius') return cfg.genius_bnb ? 'Genius.fun' : '';
    if (x.launchpad === 'bankr') return cfg.bankr ? 'Bankr' : '';
    return LAUNCHPAD[x.launchpad] || '';
  }

  function venue(url, pad) {
    if (pad === 'flap') return 'Flap';
    if (pad === 'genius') return 'Genius.fun';
    if (pad === 'fourmeme' || (url && url.indexOf('four.meme') >= 0)) return 'four.meme';
    if (url && url.indexOf('axiom.trade') >= 0) return 'Axiom';
    if (url && url.indexOf('flap.sh') >= 0) return 'Flap';
    if (url && url.indexOf('genius.fun') >= 0) return 'Genius.fun';
    return url ? 'Trade' : '';
  }

  function avatar(x) {
    const tk = x.ticker || x.name || short(x.token) || '?';
    const letters = esc(String(tk).replace(/^\$/, '').slice(0, 2).toUpperCase());
    if (typeof x.image === 'string' && x.image.startsWith('https://')) {
      return '<img alt="" src="' + esc(x.image) + '" data-letters="' + letters + '" onerror="var n=document.createElement(\'i\');n.textContent=this.dataset.letters;this.replaceWith(n)">';
    }
    return '<i>' + letters + '</i>';
  }

  function card(x) {
    const tk = String(x.ticker || short(x.token) || '—').replace(/^\$/, '');
    const pad = padLabel(x);
    const trade = FS.links.trade(cfg, x.chain, x.token, x.launchpad);
    const who = venue(trade, x.launchpad);
    const scan = '/?ca=' + encodeURIComponent(x.token) + '&chain=' + encodeURIComponent(x.chain || 'bnb');
    const score = x.score == null ? '—' : String(x.score);
    const cake = x.chain === 'bnb'
      ? 'https://pancakeswap.finance/swap?chain=bsc&outputCurrency=' + encodeURIComponent(x.token) : '';
    const tradeBtn = trade && who
      ? '<a class="radar-act" href="' + esc(trade) + '" target="_blank" rel="noopener">' + esc(t('Trade on {venue}', {venue: who})) + '</a>' : '';
    const cakeBtn = cake
      ? '<a class="radar-act" href="' + esc(cake) + '" target="_blank" rel="noopener">' + esc(t('Trade on PancakeSwap')) + '</a>' : '';
    return '<article class="radar-card" data-radar-token="' + esc(x.token) + '"><header><div class="radar-av">' + avatar(x) + '</div><div class="radar-id"><b>$'
      + esc(tk) + '</b><span class="radar-age" data-ts="' + esc(x.ts) + '">' + esc(fresh(x.ts)) + '</span>'
      + (x.name ? '<small>' + esc(x.name) + '</small>' : '')
      + '</div><div class="radar-tags">'
      + (pad ? '<span class="pill">' + esc(pad) + '</span>' : '')
      + '</div></header><div class="radar-metrics"><div><span>' + esc(t('Mcap at scan')) + '</span><b>'
      + esc(usd(x.mcap_usd)) + '</b></div><div class="radar-score"><b>' + esc(score)
      + '<small>/100</small></b><span class="radar-clean">' + esc(t('CLEAN')) + '</span></div></div><p class="radar-addr"><span>'
      + esc(short(x.token)) + '</span><button type="button" data-copy="' + esc(x.token) + '" aria-label="'
      + esc(t('Copy address')) + '"><svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.7"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 0 1 2-2h10"/></g></svg></button></p><div class="radar-actions">'
      + tradeBtn + cakeBtn + '<a class="radar-act" href="' + esc(scan) + '">' + esc(t('Full scan')) + '</a></div></article>';
  }

  function spanLabel(seconds) {
    const s = Math.max(0, seconds);
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + 'm';
    if (s < 86400) return Math.max(1, Math.round(s / 3600)) + 'h';
    const d = s / 86400;
    const text = Math.abs(d - Math.round(d)) < 0.05 ? String(Math.round(d)) : d.toFixed(1);
    return text + 'd';
  }

  function paintDial() {
    const svg = root.querySelector('[data-radar-dial]');
    if (!svg || svg.dataset.ready) return;
    svg.dataset.ready = '1';
    const parts = [16, 31, 46].map(r => '<circle cx="50" cy="50" r="' + r + '"/>');
    parts.push('<line x1="50" y1="4" x2="50" y2="96"/><line x1="4" y1="50" x2="96" y2="50"/>');
    for (let i = 0; i < 72; i++) {
      const a = i / 72 * Math.PI * 2;
      const inner = i % 6 === 0 ? 43.2 : 44.7;
      const x1 = 50 + Math.cos(a) * inner;
      const y1 = 50 + Math.sin(a) * inner;
      const x2 = 50 + Math.cos(a) * 46;
      const y2 = 50 + Math.sin(a) * 46;
      parts.push('<line x1="' + x1.toFixed(2) + '" y1="' + y1.toFixed(2) + '" x2="' + x2.toFixed(2) + '" y2="' + y2.toFixed(2) + '"/>');
    }
    svg.innerHTML = parts.join('');
  }

  function plot(list) {
    const now = Date.now() / 1000;
    return list.slice(0, 8).map((x, i) => {
      const age = Math.min(windowSec, Math.max(0, now - Number(x.ts || now)));
      const radius = 14 + (age / windowSec) * 30;
      let h = 0;
      const id = x.token || String(i);
      for (let c = 0; c < id.length; c++) h = (h * 33 + id.charCodeAt(c)) >>> 0;
      const a = (i * 137.5 + (h % 28)) * Math.PI / 180;
      return {x, left: 50 + Math.cos(a) * radius, top: 50 + Math.sin(a) * radius};
    });
  }

  function render() {
    const list = items.filter(x => (x.chain === 'bnb' || x.chain === 'bsc') && (filter === 'all' || String(x.launchpad || '').toLowerCase() === filter));
    const count = root.querySelector('[data-radar-count]');
    if (count) count.textContent = loadedAt ? String(list.length) : '—';
    const grid = root.querySelector('[data-radar-list]');
    if (grid) {
      if (!loadedAt && (loadStatus === 'idle' || loadStatus === 'loading')) {
        grid.innerHTML = '<p class="radar-empty">' + esc(t('Checking launch feeds…')) + '</p>';
      } else if (!loadedAt && loadStatus === 'error') {
        grid.innerHTML = '<div class="radar-empty"><span>' + esc(t('Radar update unavailable.'))
          + '</span><button type="button" data-radar-retry>' + esc(t('Retry')) + '</button></div>';
      } else {
        grid.innerHTML = list.length ? list.map(card).join('')
          : '<p class="radar-empty">' + esc(t('No clean launches in the last 7 days.')) + '</p>';
      }
    }
    const state = root.querySelector('[data-radar-state]');
    if (state) {
      const copy = state.querySelector('span:last-child');
      state.classList.toggle('is-stale', !loadedAt || loadStatus === 'error');
      state.classList.toggle('is-error', loadStatus === 'error');
      if (copy) copy.textContent = loadStatus === 'error' ? t('Update unavailable') : loadedAt ? t('Updated just now') : t('Waiting for the first update');
    }
    paintDial();
    const out = root.querySelector('[data-radar-out]');
    const mid = root.querySelector('[data-radar-mid]');
    const nowEl = root.querySelector('[data-radar-now]');
    if (out) out.textContent = spanLabel(windowSec);
    if (mid) mid.textContent = spanLabel(windowSec / 2);
    if (nowEl) nowEl.textContent = t('now');
    const box = root.querySelector('[data-radar-blips]');
    if (!box) return;
    const spots = plot(list);
    box.innerHTML = spots.map(s => {
      const x = s.x;
      const scan = '/?ca=' + encodeURIComponent(x.token) + '&chain=' + encodeURIComponent(x.chain || 'bnb');
      const tk = String(x.ticker || short(x.token) || '').replace(/^\$/, '');
      const side = s.left > 54 ? ' radar-blip-left' : '';
      return '<a class="radar-blip' + side + '" data-radar-token="' + esc(x.token) + '" style="left:' + s.left.toFixed(1) + '%;top:' + s.top.toFixed(1) + '%" href="'
        + esc(scan) + '"><span class="radar-face">' + avatar(x) + '</span><span class="radar-sticker">$'
        + esc(tk) + '</span></a>';
    }).join('');
  }

  root.addEventListener('click', e => {
    if (e.target.closest('[data-radar-retry]')) {
      load();
      return;
    }
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    e.preventDefault();
    FS.copy(b.dataset.copy);
  });
  const filters = root.querySelector('[data-radar-filters]');
  if (filters) filters.addEventListener('click', e => {
    const b = e.target.closest('[data-radar-filter]');
    if (!b) return;
    filter = b.dataset.radarFilter || 'all';
    filters.querySelectorAll('[data-radar-filter]').forEach(x => {
      const active = x === b;
      x.classList.toggle('is-active', active);
      x.setAttribute('aria-pressed', String(active));
    });
    render();
  });

  function selectToken(token) {
    root.querySelectorAll('[data-radar-token]').forEach(el => el.classList.toggle('is-selected', Boolean(token) && el.dataset.radarToken === token));
  }
  root.addEventListener('mouseover', e => {
    const item = e.target.closest('[data-radar-token]');
    if (item) selectToken(item.dataset.radarToken);
  });
  root.addEventListener('mouseout', e => {
    const from = e.target.closest('[data-radar-token]');
    const to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('[data-radar-token]') : null;
    if (from && (!to || to.dataset.radarToken !== from.dataset.radarToken)) selectToken(to && to.dataset.radarToken);
  });
  root.addEventListener('focusin', e => {
    const item = e.target.closest('[data-radar-token]');
    if (item) selectToken(item.dataset.radarToken);
  });
  root.addEventListener('focusout', e => {
    const to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('[data-radar-token]') : null;
    selectToken(to && to.dataset.radarToken);
  });
  document.addEventListener('fs:lang', render);
  setInterval(() => {
    root.querySelectorAll('[data-ts]').forEach(el => { el.textContent = fresh(el.dataset.ts); });
  }, 1000);

  function load() {
    if (document.hidden) return;
    loadStatus = loadedAt ? 'refreshing' : 'loading';
    render();
    FS.api.radar().then(d => {
      items = (d && d.items) || [];
      loadedAt = Date.now();
      loadStatus = 'ready';
      if (d && d.window_min > 0) windowSec = d.window_min * 60;
      render();
    }, () => {
      loadStatus = 'error';
      render();
    });
  }
  document.addEventListener('visibilitychange', load);
  render();
  FS.api.config().then(c => { cfg = Object.assign(cfg, c || {}); }, () => {}).then(load);
  setInterval(load, EVERY);
})();

/* Tokens page: recently verified chips, checks in a time window, new BNB pools. */
(function () {
  const $ = s => document.querySelector(s);
  const esc = s => FS.fmt.esc(s);
  const t = (s, vars) => FS.i18n.t(s, vars);

  let chips = [];
  let viewed = [];
  let fresh = [];
  let windowId = '24h';
  const status = {chips: 'loading', viewed: 'loading', fresh: 'loading'};

  function letters(x) {
    const raw = String(x.symbol || x.ticker || '').replace(/^\$/, '').trim();
    const s = raw || String(x.token || '').slice(2, 4);
    return esc(s.slice(0, 2).toUpperCase() || '??');
  }

  function face(x) {
    const mark = letters(x);
    if (typeof x.image === 'string' && x.image.startsWith('https://')) {
      return `<img alt="" src="${esc(x.image)}" data-letters="${mark}" onerror="var n=document.createElement('i');n.textContent=this.dataset.letters;this.replaceWith(n)">`;
    }
    return `<i>${mark}</i>`;
  }

  function openToken(ca) {
    if (ca) location.href = '/?ca=' + encodeURIComponent(ca) + '&chain=bnb';
  }

  function compact(n) {
    n = Number(n) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
  }

  function when(ts) {
    if (!ts) return '—';
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return t('{n}s ago', {n: Math.max(1, Math.floor(s))});
    return FS.fmt.ago(ts);
  }

  function riskPill(band) {
    if (!band) return '—';
    return `<span class="risk ${FS.fmt.risk(band)}">${esc(FS.fmt.riskLabel(band))}</span>`;
  }

  function tokenCell(x) {
    const ca = x.token || '';
    const symbol = x.symbol || x.ticker || FS.fmt.short(ca) || '—';
    return `<div class="tok">${face(x)}<span><b>${esc(symbol)}</b>` +
      `<small>${esc(FS.fmt.short(ca))}` +
      `<button type="button" class="tok-copy" data-copy="${esc(ca)}" aria-label="Copy">` +
      `<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></g></svg>` +
      `</button></small></span></div>`;
  }

  function paintChips() {
    const box = $('[data-chips]');
    if (!box) return;
    if (status.chips === 'loading') {
      box.innerHTML = `<p class="tick-empty">${esc(t('Loading recent scans…'))}</p>`;
      return;
    }
    if (status.chips === 'error') {
      box.innerHTML = `<p class="tick-empty">${esc(t('Recent scans are unavailable.'))}</p>`;
      return;
    }
    if (!chips.length) {
      box.innerHTML = `<p class="tick-empty">${esc(t('No scans yet.'))}</p>`;
      return;
    }
    const one = items => items.map(x => {
      const symbol = x.ticker || FS.fmt.short(x.token) || '—';
      return `<button type="button" class="tick" data-ca="${esc(x.token)}">${face(x)}` +
        `<span class="tick-copy"><b>${esc(symbol)}</b><small>${esc(x.name || '')}</small></span></button>`;
    }).join('');
    let html = one(chips), n = chips.length;
    while (n < 8) { html += one(chips); n += chips.length; }
    box.innerHTML = `<div class="tick-run">${html}${html}</div>`;
  }

  function stateRow(columns, message, retry) {
    const action = retry
      ? `<button type="button" data-retry="${esc(retry)}">${esc(t('Retry'))}</button>` : '';
    return `<tr><td colspan="${columns}"><div class="token-data-state"><span>${esc(t(message))}</span>${action}</div></td></tr>`;
  }

  function paintViewed() {
    const body = $('[data-viewed]');
    if (!body) return;
    if (status.viewed === 'loading') {
      body.innerHTML = stateRow(4, 'Loading checks…');
      return;
    }
    if (status.viewed === 'error') {
      body.innerHTML = stateRow(4, 'Checks are unavailable.', 'viewed');
      return;
    }
    if (!viewed.length) {
      body.innerHTML = `<tr><td colspan="4"><p class="token-empty">${esc(t('No checks in this window.'))}</p></td></tr>`;
      return;
    }
    body.innerHTML = viewed.map(x =>
      `<tr tabindex="0" data-ca="${esc(x.token)}"><td>${tokenCell(x)}</td>` +
      `<td class="tok-name">${esc(x.name || '—')}</td>` +
      `<td class="tok-num">${esc(compact(x.checks))}</td>` +
      `<td>${riskPill(x.band)}</td></tr>`).join('');
  }

  function paintNew() {
    const body = $('[data-new]');
    if (!body) return;
    if (status.fresh === 'loading') {
      body.innerHTML = stateRow(2, 'Loading new tokens…');
      return;
    }
    if (status.fresh === 'error') {
      body.innerHTML = stateRow(2, 'New tokens are unavailable.', 'new');
      return;
    }
    if (!fresh.length) {
      body.innerHTML = `<tr><td colspan="2"><p class="token-empty">${esc(t('No new tokens right now.'))}</p></td></tr>`;
      return;
    }
    body.innerHTML = fresh.map(x =>
      `<tr tabindex="0" data-ca="${esc(x.token)}"><td>${tokenCell(x)}</td><td>${esc(when(x.created))}</td></tr>`).join('');
  }

  function paintFreshness() {
    const el = $('[data-token-state]');
    const copy = $('[data-token-state-copy]');
    if (!el || !copy) return;
    const values = Object.values(status);
    const failed = values.includes('error');
    const loading = values.includes('loading');
    el.classList.toggle('is-error', failed);
    el.classList.toggle('is-loading', !failed && loading);
    copy.textContent = t(failed ? 'Some market data is unavailable' : loading ? 'Loading market data' : 'Updated just now');
  }

  function paint() {
    paintChips();
    paintViewed();
    paintNew();
    paintFreshness();
  }

  function busy(btn, on) {
    if (!btn) return;
    btn.classList.toggle('is-busy', on);
    btn.disabled = on;
    btn.setAttribute('aria-busy', String(on));
  }

  async function loadChips() {
    status.chips = 'loading';
    paintChips();
    paintFreshness();
    try {
      const d = await FS.api.recent();
      chips = (d && d.items) || [];
      status.chips = 'ready';
    } catch (e) {
      status.chips = 'error';
    }
    paintChips();
    paintFreshness();
  }

  async function loadViewed() {
    const btn = $('[data-refresh="viewed"]');
    busy(btn, true);
    status.viewed = 'loading';
    paintViewed();
    paintFreshness();
    try {
      const d = await FS.api.tokensViewed(windowId);
      viewed = (d && d.items) || [];
      status.viewed = 'ready';
    } catch (e) {
      status.viewed = 'error';
    }
    busy(btn, false);
    paintViewed();
    paintFreshness();
  }

  async function loadNew(manual) {
    const btn = manual ? $('[data-refresh="new"]') : null;
    busy(btn, true);
    status.fresh = 'loading';
    paintNew();
    paintFreshness();
    try {
      const d = await FS.api.tokensNew();
      fresh = ((d && d.items) || []).slice().sort((a, b) => (b.created || 0) - (a.created || 0)).slice(0, 7);
      status.fresh = 'ready';
    } catch (e) {
      status.fresh = 'error';
    }
    busy(btn, false);
    paintNew();
    paintFreshness();
  }

  function onRowClick(e) {
    const retry = e.target.closest('[data-retry]');
    if (retry) {
      if (status.chips === 'error') loadChips();
      retry.dataset.retry === 'viewed' ? loadViewed() : loadNew(true);
      return;
    }
    const copy = e.target.closest('[data-copy]');
    if (copy) {
      e.stopPropagation();
      FS.copy(copy.getAttribute('data-copy') || '');
      return;
    }
    const row = e.target.closest('[data-ca]');
    if (row) openToken(row.getAttribute('data-ca'));
  }

  function onRowKeydown(e) {
    if (e.key !== 'Enter' || e.target.closest('button, a')) return;
    const row = e.target.closest('[data-ca]');
    if (row) openToken(row.getAttribute('data-ca'));
  }

  function init() {
    const ranges = $('[data-ranges]');
    if (ranges) ranges.addEventListener('click', e => {
      const b = e.target.closest('[data-window]');
      if (!b || b.dataset.window === windowId) return;
      windowId = b.dataset.window;
      ranges.querySelectorAll('[data-window]').forEach(x => x.classList.toggle('on', x === b));
      loadViewed();
    });
    const viewedBtn = $('[data-refresh="viewed"]');
    const newBtn = $('[data-refresh="new"]');
    if (viewedBtn) viewedBtn.addEventListener('click', loadViewed);
    if (newBtn) newBtn.addEventListener('click', () => loadNew(true));
    const viewedBody = $('[data-viewed]');
    const newBody = $('[data-new]');
    const chipBox = $('[data-chips]');
    if (viewedBody) viewedBody.addEventListener('click', onRowClick);
    if (newBody) newBody.addEventListener('click', onRowClick);
    if (viewedBody) viewedBody.addEventListener('keydown', onRowKeydown);
    if (newBody) newBody.addEventListener('keydown', onRowKeydown);
    if (chipBox) chipBox.addEventListener('click', e => {
      const chip = e.target.closest('[data-ca]');
      if (chip) openToken(chip.getAttribute('data-ca'));
    });
    document.addEventListener('fs:lang', paint);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) loadNew(false); });
    paint();
    loadChips();
    loadViewed();
    loadNew(true);
    setInterval(() => { if (!document.hidden) paintNew(); }, 5000);
    setInterval(() => { if (!document.hidden) loadNew(false); }, 15000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

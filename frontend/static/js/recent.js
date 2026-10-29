// FoxScanner: "Live token scanner" — GET /api/recent?limit=12 on load, every 30 s and on tab return; hidden tab — no requests
(function () {
  'use strict';
  const FS = window.FS;
  const {esc, short, ago, risk, riskLabel, LAUNCHPAD, CHAIN_SHORT} = FS.fmt;
  const EVERY_MS = 30000;
  const t = (s, v) => FS.i18n.t(s, v);

  function padOf(x, cfg) {
    return x.launchpad === 'flap' ? ((cfg.flap || cfg.flap_bnb) ? 'Flap' : '') : x.launchpad === 'bankr' ? (cfg.bankr ? 'Bankr' : '') : x.launchpad === 'genius' ? (cfg.genius_bnb ? 'Genius.fun' : '') : (LAUNCHPAD[x.launchpad] || '');
  }

  function rows(items, cfg) {
    return items.map(x => {
      const lvl = risk(x.band);
      const pad = padOf(x, cfg);
      const tk = x.ticker || x.name || short(x.token);
      return `<tr class="recent-row" tabindex="0" data-token="${esc(x.token)}" data-chain="${esc(x.chain)}">`
        + `<td><div class="tk"><i>${esc(String(tk).slice(0, 2).toUpperCase())}</i><div><b>${esc(tk)}</b><small>${esc(short(x.token))}</small></div></div></td>`
        + `<td><span class="pill y">${esc(CHAIN_SHORT[x.chain] || x.chain)}</span></td>`
        + `<td class="hide-m muted">${esc(pad)}</td>`
        + `<td class="num">${x.score == null ? '—' : x.score}</td>`
        + `<td><span class="risk ${lvl}">${esc(riskLabel(x.band))}</span>${x.rug ? ' <span class="flag bad">' + esc(t('rug risk')) + '</span>' : ''}</td>`
        + `<td class="num muted hide-m">${ago(x.ts)}</td>`
        + `<td class="num"><span class="btn ghost sm">${esc(t('View'))}</span></td></tr>`;
    }).join('');
  }

  function chips(items) {
    return items.map(x => {
      const tk = x.ticker || x.name || short(x.token);
      const sub = x.name && x.name !== tk ? x.name : short(x.token);
      const letters = esc(String(tk).slice(0, 2).toUpperCase());
      const img = typeof x.image === 'string' && x.image.startsWith('https://')
        ? `<img alt="" src="${esc(x.image)}" data-letters="${letters}" onerror="var n=document.createElement('i');n.textContent=this.dataset.letters;this.replaceWith(n)">`
        : `<i>${letters}</i>`;
      return `<button type="button" class="tick" data-token="${esc(x.token)}" data-chain="${esc(x.chain)}">`
        + img
        + `<span class="tick-copy"><b>${esc(tk)}</b><small>${esc(sub)}</small></span></button>`;
    }).join('');
  }

  function Recent(root, cfg, onPick) {
    this.root = root; this.cfg = cfg || {}; this.onPick = onPick;
    this.track = root.querySelector('[data-recent-track]');
    this.track.addEventListener('click', e => {
      const b = e.target.closest('[data-token]');
      if (b) this.onPick(b.dataset.token, b.dataset.chain);
    });
    document.addEventListener('visibilitychange', () => this.tick());
    document.addEventListener('fs:lang', () => this.render(this._items || []));
    setInterval(() => this.tick(), EVERY_MS);
    this.load();
  }

  Recent.prototype.tick = function () {
    const t = Date.now();
    if (document.hidden || t - (this._recentAt || 0) < 20000) return;
    this.load();
  };

  Recent.prototype.load = function () {
    this._recentAt = Date.now();
    FS.api.recent().then(d => this.render((d && d.items) || []), () => {});
  };

  Recent.prototype.render = function (items) {
    this._items = items || [];
    const on = this._items.filter(x => (this.cfg.chains || {})[x.chain] !== false);
    if (!this.track) return;
    if (!on.length) {
      this.track.innerHTML = `<span class="tick-empty">${esc(t('No scans yet.'))}</span>`;
      return;
    }
    let html = chips(on), n = on.length;
    while (n < 8) { html += chips(on); n += on.length; }
    this.track.innerHTML = `<div class="tick-run">${html}${html}</div>`;
  };

  function Marked(root, cfg, onPick) {
    this.root = root; this.cfg = cfg || {}; this.onPick = onPick;
    this.band = 'DANGER';
    this.items = {DANGER: [], CLEAN: []};
    this.body = root.querySelector('[data-marked-body]');
    this.empty = root.querySelector('[data-marked-empty]');
    this.table = this.body.closest('table');
    root.querySelector('[data-marked-tabs]').addEventListener('click', e => {
      const b = e.target.closest('[data-mark]');
      if (!b) return;
      this.band = b.dataset.mark;
      root.querySelectorAll('[data-mark]').forEach(x => {
        const on = x === b;
        x.classList.toggle('on', on);
        x.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      this.paint();
    });
    const open = e => {
      const tr = e.target.closest('[data-token]');
      if (tr) this.onPick(tr.dataset.token, tr.dataset.chain);
    };
    this.body.addEventListener('click', open);
    this.body.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(e); }
    });
    document.addEventListener('fs:lang', () => this.paint());
    this.load();
  }

  Marked.prototype.load = function () {
    Promise.all([FS.api.marked('DANGER'), FS.api.marked('CLEAN')]).then(([d, c]) => {
      this.items.DANGER = (d && d.items) || [];
      this.items.CLEAN = (c && c.items) || [];
      this.paint();
    }, () => this.paint());
  };

  Marked.prototype.paint = function () {
    const on = (this.items[this.band] || []).filter(x => (this.cfg.chains || {})[x.chain] !== false);
    this.body.innerHTML = on.length ? rows(on, this.cfg) : '';
    this.table.classList.toggle('hidden', !on.length);
    this.empty.textContent = t(this.band === 'CLEAN' ? 'No clean tokens yet.' : 'No dangerous tokens yet.');
    this.empty.classList.toggle('hidden', !!on.length);
  };

  FS.Recent = Recent;
  FS.Marked = Marked;
})();

// FoxScanner: "Live token scanner" — GET /api/recent?limit=12 on load, every 30 s and on tab return; hidden tab — no requests
(function () {
  'use strict';
  const FS = window.FS;
  const {esc, short, ago, risk, riskLabel, LAUNCHPAD, CHAIN_SHORT} = FS.fmt;
  const EVERY_MS = 30000;

  function Recent(root, cfg, onPick) {
    this.root = root; this.cfg = cfg || {}; this.onPick = onPick;
    this.body = root.querySelector('[data-recent-body]');
    this.body.addEventListener('click', e => {
      const tr = e.target.closest('[data-token]');
      if (tr) this.onPick(tr.dataset.token, tr.dataset.chain);
    });
    this.body.addEventListener('keydown', e => {
      const tr = e.target.closest('[data-token]');
      if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); this.onPick(tr.dataset.token, tr.dataset.chain); }
    });
    document.addEventListener('visibilitychange', () => this.tick());
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
    const cfg = this.cfg;
    const on = items.filter(x => (cfg.chains || {})[x.chain] !== false);
    this.root.classList.toggle('hidden', !on.length);
    this.body.innerHTML = on.map(x => {
      const lvl = risk(x.band);
      const pad = x.launchpad === 'flap' ? (cfg.flap ? 'Flap' : '') : x.launchpad === 'bankr' ? (cfg.bankr ? 'Bankr' : '') : (LAUNCHPAD[x.launchpad] || '');
      const tk = x.ticker || x.name || short(x.token);
      return `<tr class="recent-row" tabindex="0" data-token="${esc(x.token)}" data-chain="${esc(x.chain)}">`
        + `<td><div class="tk"><i>${esc(String(tk).slice(0, 2).toUpperCase())}</i><div><b>${esc(tk)}</b><small>${esc(short(x.token))}</small></div></div></td>`
        + `<td><span class="pill y">${esc(CHAIN_SHORT[x.chain] || x.chain)}</span></td>`
        + `<td class="hide-m muted">${esc(pad)}</td>`
        + `<td class="num">${x.score == null ? '—' : x.score}</td>`
        + `<td><span class="risk ${lvl}">${esc(riskLabel(x.band))}</span>${x.rug ? ' <span class="flag bad">rug risk</span>' : ''}</td>`
        + `<td class="num muted hide-m">${ago(x.ts)}</td>`
        + `<td class="num"><span class="btn ghost sm">View</span></td></tr>`;
    }).join('');
  };

  FS.Recent = Recent;
})();

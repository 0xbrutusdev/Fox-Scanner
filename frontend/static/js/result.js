// FoxScanner: result card — verdict, token facts, risk checklist, rug box, chart, holders, early buyers
(function () {
  'use strict';
  const FS = window.FS;
  const {api, links} = FS;
  const {esc, price, usd, pct, short, age, secs, risk, riskLabel, RISK_COLOR, LAUNCHPAD} = FS.fmt;

  const WEIGHTS = {operator: 35, virgin: 25, transfer: 20, sniper: 10, concentration: 10};
  const NO_EARLY = new Set(['TOO_ESTABLISHED', 'TOO_ACTIVE']);
  const EARLY_STATUS = {holding_all: 'Holding', added: 'Added more', sold_part: 'Sold part', sold_all: 'Sold all',
    moved: 'Moved out', burned: 'Burned', locked: 'Locked'};

  const link = (href, text, cls) => href ? `<a class="${cls || 'mono'}" href="${esc(href)}" target="_blank" rel="noopener">${text}</a>` : text;

  function checks(r) {
    const p = r.parts || {}, m = r.metrics || {};
    if (!Object.keys(p).length) return '';
    const rows = [
      ['operator', 'Biggest operator dump impact',
        m.impact != null ? `−${pct(m.impact, 0)} price if sold · ${pct(m.operator)} of float` : `${pct(m.operator)} of float (liquidity not measured)`],
      ['virgin', 'Fresh wallets in top holders', m.virgin != null ? pct(m.virgin, 0) + ' of top 20' : 'most of the top could not be read'],
      ['transfer', 'Supply received by transfer', pct(m.transfer) + ' of float'],
      ['sniper', 'Snipers still holding', pct(m.sniper) + ' of float'],
      ['concentration', 'Top 20 concentration', pct(m.concentration) + ' of float'],
    ].map(([k, label, val]) => {
      const ratio = p[k] == null ? null : p[k] / WEIGHTS[k];
      const st = ratio == null ? 'na' : ratio >= 0.8 ? 'pass' : ratio >= 0.4 ? 'warn' : 'fail';
      const word = {pass: 'Safe', warn: 'Watch', fail: 'Risk', na: 'n/a'}[st];
      const ic = {pass: '✓', warn: '!', fail: '✕', na: '–'}[st];
      return `<li class="check ${st}" data-check="${k}"><span class="ic">${ic}</span><div>${label}<small>${esc(val)}</small></div><em>${word}</em></li>`;
    }).join('');
    return `<div class="card"><div class="card-h"><h3>Risk checks</h3><span class="muted">score ${r.score == null ? '—' : r.score} / 100</span></div><ul class="checks">${rows}</ul></div>`;
  }

  function gates(r) {
    const g = r.gates || [];
    if (!g.length) return '';
    return '<ul class="gates">' + g.map(x => x.startsWith('soft:') ? `<li class="soft">${esc(x.slice(5).trim())}</li>` : `<li>${esc(x)}</li>`).join('') + '</ul>';
  }

  function rugBox(r) {
    if (!r.rug) return '';
    const rug = r.rug;
    return `<div class="rugbox" data-rug="1"><h3>⚠ Potential rug pull · −${FS.chart.dropPct(rug)}%</h3>`
      + `<p>Suspicious holders control ${pct(rug.share)} of float. If they sell into current liquidity, the price could fall about ${FS.chart.dropPct(rug)}%`
      + (rug.level_usd ? ` (to ${price(rug.level_usd)})` : '') + '.</p>' + FS.chart.rugRows(rug) + '</div>';
  }

  function padInfo(r, cfg) {
    const fm = r.fourmeme, fl = cfg.flap && r.launchpad === 'flap' ? r.flap : null, bk = cfg.bankr && r.launchpad === 'bankr' ? r.bankr : null;
    if (fm) {
      if (fm.phase === 'pancakeswap') return {label: 'Phase', value: 'PancakeSwap', bar: null};
      return {label: 'Bonding curve', value: fm.progress == null ? 'on curve' : pct(fm.progress, 0), bar: fm.progress};
    }
    if (fl) return {label: 'Flap', value: fl.phase === 'dex' ? 'graduated' : (fl.phase_text || 'bonding curve'), bar: fl.phase === 'dex' ? null : fl.progress};
    if (bk && bk.vesting) {
      const v = bk.vesting;
      return {label: 'Dev vesting', value: `${pct(v.total_share_supply)} (${pct(v.unlocked_share_supply)} unlocked)`, bar: null};
    }
    return null;
  }

  function stats(r, cfg) {
    const h = r.header || {};
    const cells = [['Price', price(h.price_usd)], ['Market cap', usd(h.mcap_usd || h.fdv_usd)], ['Liquidity', usd(h.liquidity_usd)],
      ['Volume 24h', usd(h.vol24h_usd)], ['Age', age(h.age_h)]];
    if (r.holders_total != null) cells.push(['Holders', r.holders_total.toLocaleString('en-US')]);
    const pad = padInfo(r, cfg);
    let html = cells.map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}</b></div>`).join('');
    if (pad) html += `<div class="stat" data-launchpad-info="1"><span>${esc(pad.label)}</span><b>${esc(pad.value)}</b>`
      + (pad.bar != null ? `<div class="progress"><div style="width:${Math.min(100, Math.max(0, pad.bar * 100)).toFixed(0)}%"></div></div>` : '') + '</div>';
    return `<div class="stats">${html}</div>`;
  }

  function holderFlags(s) {
    const out = [];
    if (s.is_deployer) out.push(['dev', 'y']);
    if (s.virgin) out.push(['fresh', 'bad']);
    if (s.sniper) out.push(['sniper', 'bad']);
    if (s.launch_bundle) out.push(['bundle', 'bad']);
    if (s.kind === 'transfer') out.push(['transfer', 'warn']);
    if (s.short_history) out.push(['short history', 'warn']);
    if (s.one_shot_funded) out.push(['one-shot funded', 'warn']);
    if (s.sold) out.push(['sold', '']);
    if (s.unread) out.push(['unread', '']);
    return out.map(([t, c]) => `<span class="flag ${c}">${t}</span>`).join('');
  }

  function holders(r, cfg) {
    const hs = r.holders || [];
    if (!hs.length) return '';
    const group = {};
    (r.operators || []).filter(o => (o.wallets || []).length > 1).forEach((o, i) => o.wallets.forEach(w => { group[w] = i + 1; }));
    const ops = (r.operators || []).filter(o => (o.wallets || []).length > 1);
    const rows = hs.map((h, i) => {
      const s = h.signals || {};
      return `<tr data-row="${esc(h.wallet)}"><td class="num muted">${i + 1}</td>`
        + `<td>${link(links.explorer(cfg, r.chain, 'address', h.wallet), esc(short(h.wallet)))}</td>`
        + `<td class="num">${pct(h.share_supply, 2)}</td>`
        + `<td class="hide-m">${s.kind ? esc(s.kind) : '<span class="muted">unknown</span>'}</td>`
        + `<td><div class="flags">${holderFlags(s)}</div></td>`
        + `<td class="num">${group[h.wallet] ? `<span class="op" title="operator ${group[h.wallet]}">#${group[h.wallet]}</span>` : ''}</td></tr>`;
    }).join('');
    const sum = ops.length ? `<div class="summary"><span><b>${ops.length}</b> operator${ops.length === 1 ? '' : 's'} (linked wallets)</span>`
      + ops.slice(0, 3).map((o, i) => `<span>#${i + 1}: <b>${o.wallets.length}</b> wallets · <b>${pct(o.share_supply)}</b> of supply</span>`).join('') + '</div>' : '';
    return `<div class="card" data-table="1"><div class="card-h"><h3>Top holders</h3><span class="muted">${hs.length} of ${r.holders_total == null ? '—' : r.holders_total}</span></div>`
      + sum + `<div class="table-wrap"><table><thead><tr><th class="num">#</th><th>Wallet</th><th class="num">Supply</th><th class="hide-m">Entry</th><th>Signals</th><th class="num">Op</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  function earlyHtml(d, r, cfg) {
    if (!d) return '<div class="card-b"><div class="skel" style="height:120px"></div></div>';
    if (d.available === false) return `<div class="empty">Early buyers: ${esc(d.reason || 'not available')}</div>`;
    if (d.error) return `<div class="empty">Early buyers temporarily unavailable <button class="btn ghost sm" data-early-retry="1">Retry</button></div>`;
    const bs = d.buyers || [], s = d.summary || {};
    if (!bs.length) return '<div class="empty">No early buyers found yet</div>';
    const rows = bs.map(b => {
      const st = EARLY_STATUS[b.status] || b.status;
      const where = b.status === 'locked' && b.locked_in && b.locked_in.length ? ' in ' + esc(short(b.locked_in[0])) : '';
      const fl = (b.scan_flags || []).map(f => `<span class="flag ${f === 'operator' ? 'bad' : 'warn'}">${esc(f)}</span>`).join('');
      return `<tr><td class="num muted">${b.rank}</td><td>${link(links.explorer(cfg, r.chain, 'address', b.wallet), esc(short(b.wallet)))}`
        + `${b.dev ? ' <span class="flag y">dev</span>' : ''}</td><td class="num hide-m">${secs(b.dt_s)}</td>`
        + `<td class="num">${pct(b.bought_share_supply, 2)}</td><td class="num">${pct(b.now_share_supply, 2)}</td>`
        + `<td><span class="status ${esc(b.status)}">${esc(st)}${where}</span></td><td class="hide-m"><div class="flags">${fl}</div></td></tr>`;
    }).join('');
    const stale = d.stale_at ? ` · as of ${new Date(d.stale_at * 1000).toISOString().slice(11, 16)} UTC` : '';
    return `<div class="summary"><span><b>${s.holding || 0}</b> still holding</span><span><b>${s.exited || 0}</b> exited</span>`
      + `<span>first ${s.buyers || bs.length} hold <b>${pct(s.held_share_supply)}</b> of supply</span>`
      + ((s.same_destination || []).length ? `<span style="color:var(--high)">${s.same_destination.length} shared exit address${s.same_destination.length === 1 ? '' : 'es'}</span>` : '')
      + `<span class="muted">${s.partial ? 'partial' : ''}${stale}</span></div>`
      + `<div class="table-wrap"><table><thead><tr><th class="num">#</th><th>Wallet</th><th class="num hide-m">Entry</th><th class="num">Bought</th><th class="num">Now</th><th>Status</th><th class="hide-m">Scan</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // ---------------------------------------------------------------- card
  function Result(root, cfg) {
    this.root = root; this.cfg = cfg || {};
    this._rs = () => this.paintChart();
    window.addEventListener('resize', this._rs);
  }
  Result.prototype.clear = function () { this.r = null; this.gen = (this.gen || 0) + 1; clearInterval(this._idx); this.root.innerHTML = ''; };

  Result.prototype.error = function (msg, retry) {
    this.clear();
    this.root.innerHTML = `<div class="card error-card"><img src="/static/img/logo.png" alt=""><h3>Couldn't scan this token</h3><p>${esc(msg)}</p>`
      + (retry ? '<button class="btn" data-retry="1">Try again</button>' : '') + '</div>';
    const b = this.root.querySelector('[data-retry]');
    if (b) b.addEventListener('click', retry);
  };

  Result.prototype.show = function (r, rescan) {
    this.clear();
    this.r = r;
    const cfg = this.cfg, h = r.header || {}, lvl = risk(r.band);
    const name = h.name || h.ticker || 'Unknown token';
    const trade = links.trade(cfg, r.chain, r.token);
    const pad = LAUNCHPAD[r.launchpad] && (r.launchpad !== 'flap' || cfg.flap) && (r.launchpad !== 'bankr' || cfg.bankr) ? LAUNCHPAD[r.launchpad] : null;
    const chainName = ((cfg.chain_names || {})[r.chain]) || r.chain;
    this.root.innerHTML =
      `<div class="card token-h"><div class="avatar">${esc((h.ticker || name).slice(0, 2).toUpperCase())}</div>`
      + `<div class="token-name"><h2>${esc(name)}${h.ticker && h.name ? `<small>$${esc(h.ticker)}</small>` : ''}</h2>`
      + `<div class="addr"><button type="button" data-copy="${esc(r.token)}" title="Copy address">${esc(short(r.token))} ⧉</button>`
      + `<span class="pill y">${esc(chainName)}</span>${pad ? `<span class="pill">${esc(pad)}</span>` : ''}`
      + (r.limited ? '<span class="pill">limited data</span>' : '') + '</div></div>'
      + `<div class="token-actions">${links.explorer(cfg, r.chain, 'token', r.token) ? `<a class="btn ghost sm" href="${esc(links.explorer(cfg, r.chain, 'token', r.token))}" target="_blank" rel="noopener">Explorer</a>` : ''}`
      + (trade ? `<a class="btn sm" data-trade="1" href="${esc(trade)}" target="_blank" rel="noopener">Trade ↗</a>` : '') + '</div></div>'
      + `<div class="card verdict"><div class="ring" style="--c:${RISK_COLOR[lvl]};--p:${r.score == null ? 0 : r.score}"><b>${r.score == null ? '—' : r.score}<small>/ 100</small></b></div>`
      + `<div><span class="risk ${lvl}" data-risk="${lvl}">${esc(riskLabel(r.band))}</span><h3>${esc(r.headline || '')}</h3><p>${esc(r.reason || '')}</p>${gates(r)}`
      + ((r.notes || []).length ? `<div class="notes">${r.notes.map(esc).join(' · ')}</div>` : '')
      + (r.partial_scan ? `<div class="notes" data-partial="1">Partial scan: ${esc(r.partial_scan.message || 'holder index is still building')} <span data-index-state></span></div>` : '')
      + `<div class="notes">Scanned in ${r.elapsed_s == null ? '—' : r.elapsed_s + 's'} · <button type="button" class="btn ghost sm" data-rescan="1" style="height:28px">Rescan</button></div></div></div>`
      + stats(r, cfg) + rugBox(r)
      + `<div class="card" data-chart-box="1"><div class="chart-box" data-chart-el></div></div>`
      + checks(r) + holders(r, cfg)
      + (NO_EARLY.has(r.band) ? '' : `<div class="card" data-early="1"><div class="card-h"><h3>Early buyers</h3><span class="muted">first 20 after launch</span></div><div data-early-el></div></div>`);
    this.root.querySelector('[data-copy]').addEventListener('click', e => FS.copy(e.currentTarget.dataset.copy));
    this.root.querySelector('[data-rescan]').addEventListener('click', rescan);
    this.loadChart();
    if (!NO_EARLY.has(r.band)) this.loadEarly();
    if (r.partial_scan && cfg.bankr) this.watchIndex(rescan);
  };

  Result.prototype.loadChart = function () {
    const r = this.r, gen = this.gen;
    this.chartSt = {status: 'loading'};
    this.paintChart();
    api.chart(r.token, r.chain).then(d => ({status: 'ok', data: d}), () => ({status: 'none', data: {}}))
      .then(st => { if (this.gen === gen) { this.chartSt = st; this.paintChart(); } });
  };
  Result.prototype.paintChart = function () {
    if (!this.r) return;
    FS.chart.paint(this.root.querySelector('[data-chart-el]'), this.chartSt, this.r);
  };

  Result.prototype.loadEarly = function () {
    const r = this.r, gen = this.gen, el = this.root.querySelector('[data-early-el]');
    if (!el) return;
    el.innerHTML = earlyHtml(null, r, this.cfg);
    api.early(r.token, r.chain).then(d => d, () => ({error: 'temporarily unavailable'})).then(d => {
      if (this.gen !== gen) return;
      el.innerHTML = earlyHtml(d, r, this.cfg);
      const b = el.querySelector('[data-early-retry]');
      if (b) b.addEventListener('click', () => this.loadEarly());
    });
  };

  // Bankr partial scan: the full holder index builds in the background; offer a rescan once it is ready
  Result.prototype.watchIndex = function (rescan) {
    const r = this.r, gen = this.gen, el = this.root.querySelector('[data-index-state]');
    const check = () => {
      if (document.hidden) return;
      api.index(r.token, r.chain).then(d => {
        if (this.gen !== gen || !el) return;
        if (d.state === 'ready') {
          clearInterval(this._idx);
          el.innerHTML = '<button type="button" class="btn sm" style="height:28px">Full index ready · rescan</button>';
          el.querySelector('button').addEventListener('click', rescan);
        } else if (d.eta_s) el.textContent = `· full index in ~${Math.ceil(d.eta_s / 60)} min`;
      }, () => {});
    };
    check();
    this._idx = setInterval(check, 30000);
  };

  FS.Result = Result;
})();

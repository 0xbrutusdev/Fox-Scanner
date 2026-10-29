// FoxScanner: result card — verdict, token facts, risk checklist, rug box, chart, holders, early buyers
(function () {
  'use strict';
  const FS = window.FS;
  const {api, links} = FS;
  const {esc, price, usd, pct, short, age, secs, risk, riskLabel, RISK_COLOR, LAUNCHPAD} = FS.fmt;
  const t = (s, v) => FS.i18n.t(s, v);

  const WEIGHTS = {operator: 35, virgin: 25, transfer: 20, sniper: 10, concentration: 10};
  const NO_EARLY = new Set(['TOO_ESTABLISHED', 'TOO_ACTIVE']);
  const EARLY_STATUS = {holding_all: 'Holding', added: 'Added more', sold_part: 'Sold part', sold_all: 'Sold all',
    moved: 'Moved out', burned: 'Burned', locked: 'Locked'};

  const link = (href, text, cls) => href ? `<a class="${cls || 'mono'}" href="${esc(href)}" target="_blank" rel="noopener">${text}</a>` : text;

  function checks(r) {
    const p = r.parts || {}, m = r.metrics || {};
    if (!Object.keys(p).length) return '';
    const rows = [
      ['operator', t('Biggest operator dump impact'),
        m.impact != null ? t('−{impact} price if sold · {share} of float', {impact: pct(m.impact, 0), share: pct(m.operator)}) : t('{share} of float (liquidity not measured)', {share: pct(m.operator)})],
      ['virgin', t('Fresh wallets in top holders'), m.virgin != null ? t('{p} of top 20', {p: pct(m.virgin, 0)}) : t('most of the top could not be read')],
      ['transfer', t('Supply received by transfer'), t('{p} of float', {p: pct(m.transfer)})],
      ['sniper', t('Snipers still holding'), t('{p} of float', {p: pct(m.sniper)})],
      ['concentration', t('Top 20 concentration'), t('{p} of float', {p: pct(m.concentration)})],
    ].map(([k, label, val]) => {
      const ratio = p[k] == null ? null : p[k] / WEIGHTS[k];
      const st = ratio == null ? 'na' : ratio >= 0.8 ? 'pass' : ratio >= 0.4 ? 'warn' : 'fail';
      const word = {pass: t('Safe'), warn: t('Watch'), fail: t('Risk'), na: t('n/a')}[st];
      const ic = {pass: '✓', warn: '!', fail: '✕', na: '–'}[st];
      return `<li class="check ${st}" data-check="${k}"><span class="ic">${ic}</span><div>${label}<small>${esc(val)}</small></div><em>${word}</em></li>`;
    }).join('');
    const hard = (r.gates || []).filter(x => !String(x).startsWith('soft:'));
    const note = hard.length
      ? t('score parts · verdict follows the rule above')
      : t('score {n} / 100', {n: r.score == null ? '—' : r.score});
    return `<div class="card" data-panel="checks"><div class="card-h"><h3>${esc(t('Risk checks'))}</h3><span class="muted">${esc(note)}</span></div><ul class="checks">${rows}</ul></div>`;
  }

  function gates(r) {
    const g = r.gates || [];
    if (!g.length) return '';
    const hard = g.some(x => !String(x).startsWith('soft:'));
    const head = hard
      ? '<p class="gate-note">' + esc(t('Verdict follows this rule, not the checklist average.')) + '</p>'
      : '<p class="gate-note">' + esc(t('Soft cap: the checklist still applies, but the band cannot go cleaner than Medium.')) + '</p>';
    return head + '<ul class="gates">' + g.map(x => x.startsWith('soft:')
      ? `<li class="soft">${esc(x.slice(5).trim())}</li>` : `<li>${esc(x)}</li>`).join('') + '</ul>';
  }

  function rugBox(r) {
    if (!r.rug) return '';
    const rug = r.rug;
    const drop = FS.chart.dropPct(rug);
    const line = rug.level_usd
      ? t('Suspicious holders control {share} of float. If they sell into current liquidity, the price could fall about {drop}% (to {price}).', {share: pct(rug.share), drop, price: price(rug.level_usd)})
      : t('Suspicious holders control {share} of float. If they sell into current liquidity, the price could fall about {drop}%.', {share: pct(rug.share), drop});
    return `<div class="rugbox" data-rug="1"><h3>⚠ ${esc(t('Potential rug pull · −{n}%', {n: drop}))}</h3>`
      + `<p>${esc(line)}</p>` + FS.chart.rugRows(rug) + '</div>';
  }

  function padInfo(r, cfg) {
    const flapOn = !!(cfg.flap || cfg.flap_bnb);
    const fm = r.fourmeme, fl = flapOn && r.launchpad === 'flap' ? r.flap : null, bk = cfg.bankr && r.launchpad === 'bankr' ? r.bankr : null;
    const gn = cfg.genius_bnb && r.launchpad === 'genius' ? r.genius : null;
    if (fm) {
      if (fm.phase === 'pancakeswap') return {label: t('Phase'), value: 'PancakeSwap', bar: null};
      return {label: t('Bonding curve'), value: fm.progress == null ? t('on curve') : pct(fm.progress, 0), bar: fm.progress};
    }
    if (fl) return {label: 'Flap', value: fl.phase === 'dex' ? t('graduated') : (fl.phase_text || t('bonding curve')), bar: fl.phase === 'dex' ? null : fl.progress};
    if (gn) return {label: 'Genius.fun', value: gn.phase === 'bonding_curve' ? (gn.progress == null ? 'on curve' : pct(gn.progress, 0)) : (gn.phase_text || gn.phase || 'Genius.fun'), bar: gn.phase === 'bonding_curve' ? gn.progress : null};
    if (bk && bk.vesting) {
      const v = bk.vesting;
      return {label: t('Dev vesting'), value: t('{total} ({unlocked} unlocked)', {total: pct(v.total_share_supply), unlocked: pct(v.unlocked_share_supply)}), bar: null};
    }
    return null;
  }

  function stats(r, cfg) {
    const h = r.header || {};
    const cells = [[t('Price'), price(h.price_usd)], [t('Market cap'), usd(h.mcap_usd || h.fdv_usd)], [t('Liquidity'), usd(h.liquidity_usd)],
      [t('Volume 24h'), usd(h.vol24h_usd)], [t('Age'), age(h.age_h)]];
    if (r.holders_total != null) cells.push([t('Holders'), r.holders_total.toLocaleString('en-US')]);
    const pad = padInfo(r, cfg);
    let html = cells.map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}</b></div>`).join('');
    if (pad) html += `<div class="stat" data-launchpad-info="1"><span>${esc(pad.label)}</span><b>${esc(pad.value)}</b>`
      + (pad.bar != null ? `<div class="progress"><div style="width:${Math.min(100, Math.max(0, pad.bar * 100)).toFixed(0)}%"></div></div>` : '') + '</div>';
    return `<div class="stats">${html}</div>`;
  }

  function holderFlags(s) {
    const out = [];
    if (s.is_deployer) out.push([t('dev'), 'y']);
    if (s.virgin) out.push([t('fresh'), 'bad']);
    if (s.sniper) out.push([t('sniper'), 'bad']);
    if (s.launch_bundle) out.push([t('bundle'), 'bad']);
    if (s.kind === 'transfer') out.push([t('transfer'), 'warn']);
    if (s.short_history) out.push([t('short history'), 'warn']);
    if (s.one_shot_funded) out.push([t('one-shot funded'), 'warn']);
    if (s.sold) out.push([t('sold'), '']);
    if (s.unread) out.push([t('unread'), '']);
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
        + `<td class="hide-m">${s.kind ? esc(t(s.kind)) : '<span class="muted">' + esc(t('unknown')) + '</span>'}</td>`
        + `<td><div class="flags">${holderFlags(s)}</div></td>`
        + `<td class="num">${group[h.wallet] ? `<span class="op" title="operator ${group[h.wallet]}">#${group[h.wallet]}</span>` : ''}</td></tr>`;
    }).join('');
    const sum = ops.length ? `<div class="summary"><span><b>${ops.length}</b> ${esc(t(ops.length === 1 ? 'operator (linked wallets)' : 'operators (linked wallets)'))}</span>`
      + ops.slice(0, 3).map((o, i) => `<span>#${i + 1}: <b>${o.wallets.length}</b> ${esc(t('wallets'))} · <b>${pct(o.share_supply)}</b> ${esc(t('of supply'))}</span>`).join('') + '</div>' : '';
    return `<div class="card" data-table="1" data-panel="holders"><div class="card-h"><h3>${esc(t('Top holders'))}</h3><span class="muted">${esc(t('{n} of {t}', {n: hs.length, t: r.holders_total == null ? '—' : r.holders_total}))}</span></div>`
      + sum + `<div class="table-wrap"><table><thead><tr><th class="num">#</th><th>${esc(t('Wallet'))}</th><th class="num">${esc(t('Supply'))}</th><th class="hide-m">${esc(t('Entry'))}</th><th>${esc(t('Signals'))}</th><th class="num">${esc(t('Op'))}</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  function earlyHtml(d, r, cfg) {
    if (!d) return '<div class="card-b"><div class="skel" style="height:120px"></div></div>';
    if (d.available === false) return `<div class="empty">${esc(t('Early buyers: {reason}', {reason: d.reason || t('not available')}))}</div>`;
    if (d.error) return `<div class="empty">${esc(t('Early buyers temporarily unavailable'))} <button class="btn ghost sm" data-early-retry="1">${esc(t('Retry'))}</button></div>`;
    const bs = d.buyers || [], s = d.summary || {};
    if (!bs.length) return `<div class="empty">${esc(t('No early buyers found yet'))}</div>`;
    const rows = bs.map(b => {
      const st = t(EARLY_STATUS[b.status] || b.status);
      const where = b.status === 'locked' && b.locked_in && b.locked_in.length ? ' in ' + esc(short(b.locked_in[0])) : '';
      const whereLabel = where ? esc(t(' in {where}', {where: short(b.locked_in[0])})) : '';
      const fl = (b.scan_flags || []).map(f => `<span class="flag ${f === 'operator' ? 'bad' : 'warn'}">${esc(f)}</span>`).join('');
      return `<tr><td class="num muted">${b.rank}</td><td>${link(links.explorer(cfg, r.chain, 'address', b.wallet), esc(short(b.wallet)))}`
        + `${b.dev ? ' <span class="flag y">dev</span>' : ''}</td><td class="num hide-m">${secs(b.dt_s)}</td>`
        + `<td class="num">${pct(b.bought_share_supply, 2)}</td><td class="num">${pct(b.now_share_supply, 2)}</td>`
        + `<td><span class="status ${esc(b.status)}">${esc(st)}${whereLabel}</span></td><td class="hide-m"><div class="flags">${fl}</div></td></tr>`;
    }).join('');
    const stale = d.stale_at ? ` · as of ${new Date(d.stale_at * 1000).toISOString().slice(11, 16)} UTC` : '';
    const exits = (s.same_destination || []).length;
    return `<div class="summary"><span><b>${s.holding || 0}</b> ${esc(t('still holding'))}</span><span><b>${s.exited || 0}</b> ${esc(t('exited'))}</span>`
      + `<span>${esc(t('first {n} hold {p} of supply', {n: s.buyers || bs.length, p: pct(s.held_share_supply)}))}</span>`
      + (exits ? `<span style="color:var(--high)">${esc(t(exits === 1 ? '{n} shared exit address' : '{n} shared exit addresses', {n: exits}))}</span>` : '')
      + `<span class="muted">${s.partial ? esc(t('partial')) : ''}${stale}</span></div>`
      + `<div class="table-wrap"><table><thead><tr><th class="num">#</th><th>${esc(t('Wallet'))}</th><th class="num hide-m">${esc(t('Entry'))}</th><th class="num">${esc(t('Bought'))}</th><th class="num">${esc(t('Now'))}</th><th>${esc(t('Status'))}</th><th class="hide-m">${esc(t('Scan'))}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function riskLines(r) {
    const hard = (r.gates || []).filter(x => !String(x).startsWith('soft:')).map(x => String(x).trim()).filter(Boolean);
    if (hard.length) return hard.slice(0, 4);
    const p = r.parts || {};
    const labels = {
      operator: t('Biggest operator dump impact'),
      virgin: t('Fresh wallets in top holders'),
      transfer: t('Supply received by transfer'),
      sniper: t('Snipers still holding'),
      concentration: t('Top 20 concentration'),
    };
    return Object.keys(labels).filter(k => p[k] != null && p[k] / WEIGHTS[k] < 0.4).map(k => labels[k]).slice(0, 4);
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
    this.root.innerHTML = `<div class="card error-card"><img src="/static/img/logo.png" alt=""><h3>${esc(t('Couldn\'t scan this token'))}</h3><p>${esc(msg)}</p>`
      + (retry ? '<button class="btn" data-retry="1">' + esc(t('Try again')) + '</button>' : '') + '</div>';
    const b = this.root.querySelector('[data-retry]');
    if (b) b.addEventListener('click', retry);
  };

  Result.prototype.show = function (r, rescan) {
    this.clear();
    this.r = r;
    const cfg = this.cfg, h = r.header || {}, lvl = risk(r.band);
    const name = h.name || h.ticker || t('Unknown token');
    const trade = links.trade(cfg, r.chain, r.token, r.launchpad);
    const flapOn = !!(cfg.flap || cfg.flap_bnb);
    const pad = LAUNCHPAD[r.launchpad] && (r.launchpad !== 'flap' || flapOn) && (r.launchpad !== 'bankr' || cfg.bankr) && (r.launchpad !== 'genius' || cfg.genius_bnb) ? LAUNCHPAD[r.launchpad] : null;
    const chainName = ((cfg.chain_names || {})[r.chain]) || r.chain;
    const warn = r.band === 'DANGER' || r.band === 'RISKY';
    const m = r.metrics || {};
    const ops = (r.operators || []).filter(o => (o.wallets || []).length > 1);
    const lines = riskLines(r);
    const shown = lines.length ? lines : (warn && r.reason ? [r.reason] : []);
    const tile = (label, value, jump, on) => `<button type="button" class="tile${on ? ' on' : ''}" data-jump="${jump}"><span>${esc(label)}</span><b>${esc(String(value))}</b></button>`;
    const dev = (r.holders || []).find(x => (x.signals || {}).is_deployer);
    const dep = (r.launch || {}).deployer;
    const facts = [
      [t('Price'), price(h.price_usd)],
      [t('Market cap'), usd(h.mcap_usd || h.fdv_usd)],
      [t('Liquidity'), usd(h.liquidity_usd)],
      [t('Volume 24h'), usd(h.vol24h_usd)],
      [t('Age'), age(h.age_h)],
      [t('Holders'), r.holders_total == null ? '—' : r.holders_total.toLocaleString('en-US')],
    ];
    if (pad) facts.push([t('Launch'), pad]);
    if (dep) facts.push([t('Deployer'), link(links.explorer(cfg, r.chain, 'address', dep), esc(short(dep))), true]);
    if (dev) facts.push([t('Deployer balance'), pct(dev.share_supply, 1)]);
    const info = padInfo(r, cfg);
    if (info) facts.push([info.label, info.value]);
    const factRows = facts.map(([k, v, raw]) => `<tr><td>${esc(k)}</td><td>${raw ? v : esc(v)}</td></tr>`).join('');
    const explorer = links.explorer(cfg, r.chain, 'token', r.token);
    this.root.innerHTML =
      `<div class="card report"><div class="report-top"><div class="avatar">${esc((h.ticker || name).slice(0, 2).toUpperCase())}</div>`
      + `<div class="token-name"><h2>${esc(name)}${h.ticker && h.name ? `<small>$${esc(h.ticker)}</small>` : ''}</h2>`
      + `<div class="addr"><button type="button" data-copy="${esc(r.token)}" title="${esc(t('Copy address'))}" aria-label="${esc(t('Copy contract address'))}">${esc(short(r.token))} ⧉</button>`
      + `<span class="pill y">${esc(chainName)}</span>${pad ? `<span class="pill">${esc(pad)}</span>` : ''}`
      + (r.limited ? '<span class="pill">' + esc(t('limited data')) + '</span>' : '') + '</div></div>'
      + `<div class="report-price"><b>${esc(price(h.price_usd))}</b><div class="token-actions">`
      + (explorer ? `<a class="btn ghost sm" href="${esc(explorer)}" target="_blank" rel="noopener">${esc(t('Explorer'))}</a>` : '')
      + (trade ? `<a class="btn sm${warn ? ' ghost' : ''}" data-trade="1" href="${esc(trade)}" target="_blank" rel="noopener">${esc(t('Trade ↗'))}</a>` : '')
      + `</div></div></div>`
      + `<div class="report-dash"><div class="gauge"><div class="ring" style="--c:${RISK_COLOR[lvl]};--p:${r.score == null ? 0 : r.score}"><b>${r.score == null ? '—' : r.score}<small>/ 100</small></b></div>`
      + `<span class="ring-cap">${esc(t('Holder score'))}</span><span class="ring-sub">${esc(t('100 = cleaner distribution'))}</span>`
      + `<span class="risk ${lvl}" data-risk="${lvl}">${esc(riskLabel(r.band))}</span></div>`
      + `<div class="tiles">`
      + tile(t('Overview'), riskLabel(r.band), 'overview', true)
      + tile(t('Liquidity'), usd(h.liquidity_usd), 'markets')
      + tile(t('Holders'), r.holders_total == null ? '—' : r.holders_total.toLocaleString('en-US'), 'holders')
      + tile(t('Operators'), String(ops.length), 'holders')
      + tile(t('Snipers'), pct(m.sniper, 0), 'checks')
      + tile(t('Launch'), pad || chainName, 'overview')
      + `</div><aside class="risk-col"><h3>${esc(t('Risks'))}</h3>`
      + (shown.length ? '<ul>' + shown.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>' : `<p class="ok">${esc(t('No major risks'))}</p>`)
      + `</aside></div>`
      + `<div class="report-ov" data-panel="overview">`
      + (r.headline ? `<p class="report-line">${esc(r.headline)}</p>` : '')
      + (r.reason ? `<p class="reason">${esc(r.reason)}</p>` : '')
      + gates(r)
      + `<h3>${esc(t('Token overview'))}</h3><table class="ov-table"><tbody>${factRows}</tbody></table>`
      + ((r.notes || []).length ? `<div class="notes">${r.notes.map(esc).join(' · ')}</div>` : '')
      + (r.partial_scan ? `<div class="notes" data-partial="1">${esc(t('Partial scan: {msg}', {msg: r.partial_scan.message || t('holder index is still building')}))} <span data-index-state></span></div>` : '')
      + `<div class="notes">${esc(t('This scan does not check contract owner, mint, honeypot or tax.'))}</div>`
      + `<div class="notes">${esc(r.elapsed_s == null ? t('Scanned in —') : t('Scanned in {s}s', {s: r.elapsed_s}))} · <button type="button" class="btn ghost sm" data-rescan="1" style="height:28px">${esc(t('Rescan'))}</button></div>`
      + `</div></div>`
      + rugBox(r)
      + `<div class="card" data-panel="markets" data-chart-box="1"><div class="chart-box" data-chart-el></div></div>`
      + checks(r) + holders(r, cfg)
      + (NO_EARLY.has(r.band) ? '' : `<div class="card" data-early="1" data-panel="early"><div class="card-h"><h3>${esc(t('Early buyers'))}</h3><span class="muted">${esc(t('first 20 after launch'))}</span></div><div data-early-el></div></div>`);
    this.root.querySelector('[data-copy]').addEventListener('click', e => FS.copy(e.currentTarget.dataset.copy));
    this.root.querySelector('[data-rescan]').addEventListener('click', rescan);
    this.root.querySelectorAll('[data-jump]').forEach(b => b.addEventListener('click', () => {
      const el = this.root.querySelector('[data-panel="' + b.dataset.jump + '"]');
      if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
    }));
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
          el.innerHTML = '<button type="button" class="btn sm" style="height:28px">' + esc(t('Full index ready · rescan')) + '</button>';
          el.querySelector('button').addEventListener('click', rescan);
        } else if (d.eta_s) el.textContent = t('· full index in ~{n} min', {n: Math.ceil(d.eta_s / 60)});
      }, () => {});
    };
    check();
    this._idx = setInterval(check, 30000);
  };

  FS.Result = Result;
})();

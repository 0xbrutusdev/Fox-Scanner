// FoxScanner: price chart (GET /api/chart after the verdict) with the probably-rug arrow; plain SVG, no library
(function () {
  'use strict';
  const FS = window.FS;
  const {esc, price} = FS.fmt;
  const C = {line: '#FFD800', grid: '#1f1f1f', axis: '#6a6a6a', rug: '#EF4444', now: '#FFD800', ink: '#0B0B0B'};
  const RUG_LABEL = {linked: 'Linked wallets', transfer: 'Received by transfer', virgin: 'Fresh wallets', bundle: 'Bundle / snipers'};
  const GT_NET = {bnb: 'bsc', robinhood: 'robinhood', solana: 'solana'};
  const dropPct = r => Math.round(r.drop * 100);

  function rugRows(rug) {
    if (!rug) return '';
    const tot = rug.share || 1;
    return (rug.parts || []).map(p => {
      const n = (p.wallets || []).length;
      return `<div class="rug-row"><span>${RUG_LABEL[p.kind] || esc(p.kind)}</span>`
        + `<div class="track"><div style="width:${Math.max(2, p.share / tot * 100).toFixed(1)}%"></div></div>`
        + `<span>${n} wallet${n === 1 ? '' : 's'} · <b>${(p.share * 100).toFixed(1)}%</b></span></div>`;
    }).join('');
  }

  function widgetUrl(chain, pool) {
    const net = GT_NET[chain];
    return pool && net ? `https://www.geckoterminal.com/${net}/pools/${encodeURIComponent(pool)}?embed=1&info=0&swaps=0&grayscale=0&light_chart=0` : null;
  }

  const head = (tf, stale, src) => `<div class="chart-head"><span>Price${tf ? ' · ' + esc(tf) : ''}</span><span>`
    + (stale > 0 ? `chart as of ${new Date(stale * 1000).toISOString().slice(11, 16)} UTC · ` : '') + esc(src) + '</span></div>';

  function widget(url, W) {
    const H = W < 640 ? 240 : 320;
    return head('', 0, 'GeckoTerminal') + `<div class="chart-body"><iframe data-chart-widget="1" src="${esc(url)}" title="price chart" loading="lazy" `
      + `sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="strict-origin-when-cross-origin" style="height:${H}px"></iframe></div>`;
  }

  function svg(data, rug, hdrPrice, W, down) {
    const mob = W < 640, H = mob ? 240 : 310, sw = W - 24;
    const cs = (data.candles || []).filter(c => c && c.length >= 5 && c[4] > 0);
    const now = data.price_usd > 0 ? data.price_usd : cs.length ? cs[cs.length - 1][4] : (hdrPrice > 0 ? hdrPrice : null);
    if (!now) {
      return head('', 0, 'GeckoTerminal') + `<div class="chart-empty" data-chart-empty="1">${down ? 'Chart temporarily unavailable' : 'No price data for this token yet'}`
        + (rug ? `<div style="margin-top:8px;color:var(--high);font-weight:700">Probably rug −${dropPct(rug)}% if suspicious holders sell</div>` : '') + '</div>';
    }
    const few = cs.length < 5;
    const pl = 6, pr = mob ? 72 : 84, pt = 22, pb = 26, pw = sw - pl - pr, ph = H - pt - pb;
    const xEnd = pl + pw * (rug ? 0.74 : 0.97), xArrow = pl + pw * 0.96;
    const level = rug ? now * rug.level_factor : null;
    const vals = (few ? [] : cs.map(c => c[4])).concat([now]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (level != null) lo = Math.min(lo, level);
    if (hi <= lo) { hi = now * 1.25; lo = Math.min(lo, now * 0.75); }
    const pad = (hi - lo) * 0.08; hi += pad; lo = Math.max(0, lo - pad);
    const gap = rug ? 24 : 0;
    const y = v => pt + (1 - (v - lo) / (hi - lo)) * (ph - gap);
    const t0 = few ? 0 : cs[0][0], t1 = few ? 1 : cs[cs.length - 1][0];
    const x = t => pl + (t1 > t0 ? (t - t0) / (t1 - t0) : 1) * (xEnd - pl);
    const yn = y(now), yl = level != null ? y(level) : null;
    const f = v => v.toFixed(1);
    let g = '';
    const nt = mob ? 3 : 4;
    for (let i = 0; i <= nt; i++) {
      const v = lo + (hi - lo) * i / nt, yy = y(v);
      g += `<line x1="${pl}" x2="${pl + pw}" y1="${f(yy)}" y2="${f(yy)}" stroke="${C.grid}"/>`;
      if (Math.abs(yy - yn) > 16 && (yl == null || Math.abs(yy - yl) > 16))
        g += `<text x="${pl + pw + 8}" y="${f(yy + 3.5)}" fill="${C.axis}" font-size="10.5">${price(v)}</text>`;
    }
    if (!few) {
      const span = t1 - t0, nx = mob ? 3 : 5;
      const lab = t => {
        const dt = new Date(t * 1000), hm = dt.toTimeString().slice(0, 5), md = dt.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
        return span < 172800 ? hm : span < 518400 && !mob ? md + ' ' + hm : md;
      };
      for (let i = 0; i < nx; i++) {
        const t = t0 + span * i / (nx - 1);
        g += `<text x="${f(x(t))}" y="${H - 8}" fill="${C.axis}" font-size="10.5" text-anchor="${i === 0 ? 'start' : i === nx - 1 ? 'end' : 'middle'}">${lab(t)}</text>`;
      }
      const pts = cs.map(c => [x(c[0]), y(c[4])]); pts.push([xEnd, yn]);
      const line = pts.map((p, i) => (i ? 'L' : 'M') + f(p[0]) + ' ' + f(p[1])).join(' ');
      g += `<defs><linearGradient id="fs-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.line}" stop-opacity="0.22"/><stop offset="1" stop-color="${C.line}" stop-opacity="0"/></linearGradient></defs>`;
      g += `<path d="${line} L${f(xEnd)} ${pt + ph} L${f(pts[0][0])} ${pt + ph} Z" fill="url(#fs-fill)"/>`;
      g += `<path d="${line}" fill="none" stroke="${C.line}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>`;
    } else {
      g += `<line x1="${pl}" x2="${f(xEnd)}" y1="${f(yn)}" y2="${f(yn)}" stroke="${C.line}" stroke-width="1.4" stroke-dasharray="4 4" opacity="0.8"/>`;
      g += `<text data-chart-few="1" x="${f(pl + (xEnd - pl) / 2)}" y="${f(yn > pt + ph / 2 ? yn - 14 : yn + 24)}" fill="${C.axis}" font-size="12" text-anchor="middle">${down ? 'chart temporarily unavailable' : 'not enough trades to chart yet'}</text>`;
    }
    if (rug) {
      const dx = xArrow - xEnd, dy = yl - yn, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len, ah = 10;
      const bx = xArrow - ux * ah, by = yl - uy * ah;
      g += `<line x1="${pl}" x2="${pl + pw}" y1="${f(yl)}" y2="${f(yl)}" stroke="${C.rug}" stroke-dasharray="3 5" opacity="0.45"/>`;
      g += `<line data-rug-arrow="1" x1="${f(xEnd)}" y1="${f(yn)}" x2="${f(bx)}" y2="${f(by)}" stroke="${C.rug}" stroke-width="2" stroke-dasharray="6 5"/>`;
      g += `<path d="M${f(xArrow)} ${f(yl)} L${f(bx - uy * 5)} ${f(by + ux * 5)} L${f(bx + uy * 5)} ${f(by - ux * 5)} Z" fill="${C.rug}"/>`;
      g += `<text x="${f(xArrow + 4)}" y="${f(yl + 19)}" fill="${C.rug}" font-size="${mob ? 11.5 : 13}" font-weight="700" text-anchor="end">probably rug −${dropPct(rug)}%</text>`;
      g += `<rect x="${pl + pw + 3}" y="${f(yl - 9)}" width="${pr - 4}" height="18" rx="4" fill="${C.rug}"/><text x="${pl + pw + 8}" y="${f(yl + 3.8)}" fill="#1a0707" font-size="10.5" font-weight="700">${price(level)}</text>`;
    }
    g += `<circle cx="${f(xEnd)}" cy="${f(yn)}" r="8" fill="${C.now}" opacity="0.2"/><circle cx="${f(xEnd)}" cy="${f(yn)}" r="3.8" fill="${C.now}"/>`;
    g += `<rect x="${pl + pw + 3}" y="${f(yn - 9)}" width="${pr - 4}" height="18" rx="4" fill="${C.now}"/><text x="${pl + pw + 8}" y="${f(yn + 3.8)}" fill="${C.ink}" font-size="10.5" font-weight="700">${price(now)}</text>`;
    const rec = few ? [] : cs.slice(-6).map(c => y(c[4]));
    const below = !few && !rug && rec.filter(v => v < yn - 3).length > rec.filter(v => v > yn + 3).length && yn + 20 <= pt + ph - 4;
    g += rug ? `<text x="${f(xEnd + 10)}" y="${f(yn - 8)}" fill="${C.now}" font-size="10.5">now</text>`
      : `<text x="${f(xEnd - 6)}" y="${f(below ? yn + 20 : yn - 12)}" fill="${C.now}" font-size="10.5" text-anchor="end">now</text>`;
    return head(data.timeframe, data.stale_at, 'GeckoTerminal') + `<div class="chart-body"><svg data-chart="1" width="${sw}" height="${H}" viewBox="0 0 ${sw} ${H}" `
      + `font-family="Inter,system-ui,sans-serif" role="img" aria-label="price chart${rug ? ', probably rug −' + dropPct(rug) + '%' : ''}">${g}</svg></div>`;
  }

  // st: {status: 'loading'|'ok'|'none', data}; result: scan result. Returns HTML for the chart card body.
  function render(st, result, W) {
    const rug = result.rug || null;
    if (!st || st.status === 'loading')
      return head('', 0, '') + `<div class="chart-body"><div class="skel" data-chart-loading="1" style="height:${W < 640 ? 200 : 270}px"></div></div>`;
    const d = st.data || {};
    const est = result.band === 'TOO_ESTABLISHED';
    const noCandles = !(Array.isArray(d.candles) && d.candles.length);
    const url = (est || noCandles) ? widgetUrl(result.chain, d.pool || result.market_pool) : null;
    if (url) return widget(url, W);
    return svg(d, rug, (result.header || {}).price_usd, W, st.status !== 'ok' || !!d.unavailable);
  }

  FS.chart = {
    render, rugRows, dropPct,
    // paints into el, re-renders on width change; a failure leaves a card instead of breaking the page
    paint(el, st, result) {
      if (!el || !el.clientWidth) return;
      const W = el.clientWidth, rug = result.rug;
      const key = [result.token, st && st.status, W < 640 ? 'm' : W, rug ? rug.drop : 0].join('|');
      if (el.dataset.k === key) return;
      el.dataset.k = key;
      try { el.innerHTML = render(st, result, W); }
      catch (err) { el.dataset.k = ''; el.innerHTML = '<div class="chart-empty" data-chart-empty="1">Chart temporarily unavailable</div>'; console.warn('chart render failed', err); }
    },
  };
})();

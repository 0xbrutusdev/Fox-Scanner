const ICON_COPY = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"></rect><path d="M10.5 3.5v-.5a1.5 1.5 0 0 0-1.5-1.5h-5A1.5 1.5 0 0 0 2.5 3v5a1.5 1.5 0 0 0 1.5 1.5h.5"></path></svg>';
const ICON_CHECK = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#22C55E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5"></path></svg>';
const CHAIN = {bnb: ['BNB Chain', '#FFD800'], robinhood: ['Robinhood', '#CCFF00'], solana: ['Solana', '#9945FF']};
const PAD = {fourmeme: ['four.meme', '#FFD800'], flap: ['Flap', '#f472b6'], genius: ['Genius.fun', '#34d399'], bankr: ['Bankr', '#ff8a3d']};
const SHOW = 15;
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const short = value => { const text = String(value || ''); return text.length > 14 ? text.slice(0, 6) + '…' + text.slice(-4) : text; };
const usd = value => { if (value == null || !Number.isFinite(value)) return '—'; const abs = Math.abs(value); if (abs >= 1e9) return '$' + (value / 1e9).toFixed(2) + 'B'; if (abs >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'; if (abs >= 1e3) return '$' + (value / 1e3).toFixed(1) + 'K'; return '$' + Math.round(value); };
const pct = value => value == null || !Number.isFinite(value) ? '—' : Math.round(value * 100) + '%';
const hours = value => { if (value == null || !Number.isFinite(value)) return ''; if (value < 1) return 'less than an hour after the scan'; const rounded = Math.round(value); return rounded + (rounded === 1 ? ' hour' : ' hours') + ' after the scan'; };
const ago = ts => { if (!ts) return ''; const seconds = Math.max(0, Date.now() / 1000 - ts); if (seconds < 3600) return Math.max(1, Math.round(seconds / 60)) + 'm ago'; if (seconds < 86400) return Math.round(seconds / 3600) + 'h ago'; return Math.round(seconds / 86400) + 'd ago'; };

function statCard(label, group, color) {
  return '<div class="stat"><div class="k">' + label + '</div><div class="v ' + color + '">' + pct(group.share) + '</div><div class="s">' + group.fell + ' of ' + group.tokens + ' tokens · scans older than 24 h, last 7 days</div></div>';
}

function renderStats(stats) {
  const root = document.getElementById('stats');
  if (!stats || !stats.ready) { root.innerHTML = ''; return; }
  root.innerHTML = statCard('Marked DANGER · fell 90%+ after the scan', stats.danger, 'red') + statCard('Marked CLEAN or OK · fell 90%+ after the scan', stats.clean, 'green');
}

function card(item) {
  const chain = CHAIN[item.chain] || [item.chain || '', '#8a959c'];
  const pad = PAD[item.launchpad] || (item.chain === 'solana' ? ['pump.fun', '#8a959c'] : ['Pons', '#8a959c']);
  const title = item.name || item.ticker || short(item.token);
  const ticker = item.name && item.ticker ? '<span class="tick">$' + esc(item.ticker) + '</span>' : '';
  const score = item.score != null ? '<span>score ' + esc(item.score) + '</span>' : '';
  const rug = item.rug_drop != null ? '<span class="rug">▼ probably rug −' + Math.round(item.rug_drop * 100) + '%</span>' : '';
  const nowPct = item.drop_now != null ? (item.drop_now >= 0 ? '−' + pct(item.drop_now) : '+' + pct(-item.drop_now)) : '';
  return '<article class="card"><div class="top"><div class="name" title="' + esc(title) + '">' + esc(title) + ticker + '</div><div class="pills"><span class="pill" style="color:' + chain[1] + '">' + esc(chain[0]) + '</span><span class="pill" style="color:' + pad[1] + '">' + esc(pad[0]) + '</span></div></div><div class="addr"><code title="' + esc(item.token) + '">' + esc(short(item.token)) + '</code><button class="copy" type="button" data-copy="' + esc(item.token) + '" title="copy contract address" aria-label="copy contract address">' + ICON_COPY + '</button></div><div class="verdict"><span class="band">' + esc(item.band || 'DANGER') + '</span>' + score + rug + '</div><div class="mcap"><div class="k">market cap at scan → now</div><div class="row"><span class="from">' + usd(item.mcap_scan) + '</span><span class="arrow">→</span><span class="to">' + usd(item.mcap_now) + '</span><span class="pct">' + nowPct + '</span></div></div><div class="when">fell 90%+ <b>' + esc(hours(item.hours_after)) + '</b></div><div class="foot"><span>scanned ' + esc(ago(item.scan_ts)) + '</span><a class="again" href="/?ca=' + encodeURIComponent(item.token) + '">Scan again →</a></div></article>';
}

function renderList(items) {
  const root = document.getElementById('list');
  root.innerHTML = items && items.length ? '<div class="grid">' + items.slice(0, SHOW).map(card).join('') + '</div>' : '<div class="empty">Tracking started today. Confirmed cases appear here as they happen.</div>';
}

async function load() {
  try {
    const response = await fetch('/api/replay', {cache: 'no-store'});
    const data = response.ok ? await response.json() : null;
    renderStats(data && data.stats); renderList(data && data.items);
  } catch (_) { renderStats(null); renderList([]); }
}

document.addEventListener('click', event => {
  const button = event.target.closest && event.target.closest('button[data-copy]');
  if (!button) return;
  const value = button.getAttribute('data-copy');
  const done = () => { button.innerHTML = ICON_CHECK; setTimeout(() => { button.innerHTML = ICON_COPY; }, 1500); };
  const legacy = () => { const textarea = document.createElement('textarea'); textarea.value = value; textarea.setAttribute('readonly', ''); textarea.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(textarea); textarea.select(); try { if (document.execCommand('copy')) done(); } catch (_) {} document.body.removeChild(textarea); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value).then(done, legacy); else legacy();
});

load();
setInterval(() => { if (!document.hidden) load(); }, 60000);

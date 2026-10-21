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
    flap: false, bankr: false};

  const state = {cfg: DEFAULT_CFG, chain: 'bnb', cancel: null, last: null};

  function chainFor(ca) {   // 0x -> selected EVM chain; base58 -> solana
    if (EVM_RE.test(ca)) return EVM.has(state.chain) ? state.chain : state.cfg.default_chain;
    if (SOL_RE.test(ca)) return 'solana';
    return null;
  }

  function renderChains() {
    const cfg = state.cfg, names = cfg.chain_names || {};
    const order = ['bnb', 'solana', 'robinhood'];
    $('[data-chains]').innerHTML = order.filter(c => c in (cfg.chains || {})).map(c => {
      const on = cfg.chains[c];
      return `<button type="button" class="chain${state.chain === c ? ' on' : ''}" data-chain="${c}" ${on ? '' : 'disabled'} aria-pressed="${state.chain === c}">`
        + `<i>${FS.fmt.CHAIN_SHORT[c].slice(0, 1)}</i>${FS.fmt.esc(names[c] || c)}${on ? '' : '<small>soon</small>'}</button>`;
    }).join('');
    const net = $('[data-net]');
    if (net) net.textContent = names[state.chain] || state.chain;
    const ph = state.chain === 'solana' ? 'Paste a Solana token mint…' : 'Paste a ' + (names[state.chain] || '') + ' token address (0x…)';
    $('#ca').placeholder = ph;
  }

  function pickChain(c) {
    if (!(state.cfg.chains || {})[c]) return;
    state.chain = c;
    renderChains();
  }

  function msg(text, info) {
    const el = $('[data-form-msg]');
    el.textContent = text || '';
    el.classList.toggle('info', !!info);
  }

  function busy(on) {
    const b = $('[data-go]');
    b.disabled = on;
    b.querySelector('span').textContent = on ? 'Scanning…' : 'Start scanning';
  }

  function scan(ca, chain, push) {
    ca = (ca || '').trim();
    msg('');
    if (!ca) { msg('Paste a token contract address first'); return; }
    chain = chain && (state.cfg.chains || {})[chain] ? chain : chainFor(ca);
    if (!chain) { msg('That does not look like a token address'); return; }
    if (!(state.cfg.chains || {})[chain]) { msg(((state.cfg.chain_names || {})[chain] || chain) + ' support is coming soon'); return; }
    if (EVM.has(chain) && chain !== state.chain) pickChain(chain);
    $('#ca').value = ca;
    if (state.cancel) state.cancel();
    state.last = {ca, chain};
    if (push !== false) {
      const url = '?ca=' + encodeURIComponent(ca) + (EVM.has(chain) ? '&chain=' + chain : '');
      if (location.search !== url) history.pushState({ca, chain}, '', url);
    }
    document.title = 'Scanning ' + FS.fmt.short(ca) + ' · FoxScanner';
    const sec = $('#scanner');
    sec.classList.remove('hidden');
    state.console.reset(ca);
    state.result.clear();
    $('[data-result-wait]').classList.remove('hidden');
    sec.scrollIntoView({behavior: 'smooth', block: 'start'});
    busy(true);
    const again = () => scan(ca, chain, false);
    state.cancel = FS.scan.run(ca, EVM.has(chain) ? chain : null, {
      onEvent: e => state.console.event(e),
      onDone: r => {
        busy(false);
        $('[data-result-wait]').classList.add('hidden');
        const h = r.header || {};
        document.title = (h.ticker ? '$' + h.ticker + ' · ' : '') + FS.fmt.riskLabel(r.band) + ' · FoxScanner';
        state.result.show(r, again);
        state.recent.load();
      },
      onError: m => {
        busy(false);
        $('[data-result-wait]').classList.add('hidden');
        document.title = 'FoxScanner · Spot the rug before it hits';
        state.console.error(m);
        state.result.error(m, again);
      },
    });
  }

  function fromUrl() {
    const p = new URLSearchParams(location.search);
    const ca = p.get('ca'), chain = (p.get('chain') || '').toLowerCase();
    if (chain && (state.cfg.chains || {})[chain]) pickChain(chain);
    if (ca) scan(ca, chain || null, false);
  }

  function counters() {
    api.stats().then(d => {
      if (!d || !(d.tokens_scanned > 0)) return;
      $('[data-stat-scanned]').textContent = d.tokens_scanned.toLocaleString('en-US');
      $('[data-stat-danger]').textContent = (d.danger || 0).toLocaleString('en-US');
      const rate = d.tokens_scanned ? d.danger / d.tokens_scanned : 0;
      $('[data-stat-rate]').textContent = (rate * 100).toFixed(1) + '%';
      $('[data-counters]').classList.remove('hidden');
    }, () => {});
  }

  function init(cfg) {
    state.cfg = Object.assign({}, DEFAULT_CFG, cfg || {});
    const chains = state.cfg.chains || {};
    state.chain = chains[state.cfg.default_chain] ? state.cfg.default_chain : (Object.keys(chains).find(c => chains[c]) || 'bnb');
    state.console = new FS.scan.Console($('[data-console]'));
    state.result = new FS.Result($('[data-result]'), state.cfg);
    state.recent = new FS.Recent($('#recent'), state.cfg, (ca, chain) => scan(ca, chain));
    renderChains();
    $('[data-chains]').addEventListener('click', e => {
      const b = e.target.closest('[data-chain]');
      if (b && !b.disabled) pickChain(b.dataset.chain);
    });
    $('[data-scan-form]').addEventListener('submit', e => { e.preventDefault(); scan($('#ca').value); });
    window.addEventListener('popstate', () => {
      const p = new URLSearchParams(location.search);
      if (p.get('ca')) fromUrl();
      else { if (state.cancel) state.cancel(); busy(false); $('#scanner').classList.add('hidden'); }
    });
    counters();
    fromUrl();
  }

  document.addEventListener('DOMContentLoaded', () => {
    api.config().then(init, () => init(null));
  });
})();

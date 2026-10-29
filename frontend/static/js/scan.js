// FoxScanner: one scan — POST /api/scan, poll /api/events?job&after every 300 ms, then /api/result; plus the scan console
(function () {
  'use strict';
  const FS = window.FS;
  const {api} = FS;
  const {esc, short} = FS.fmt;
  const t = (s, v) => FS.i18n.t(s, v);
  const POLL_MS = 300;

  const STEPS = [
    ['launch', 'Finding the launch'],
    ['transfers', 'Reading transfer history'],
    ['entries', 'Classifying how holders got in'],
    ['wallets', 'Checking holder wallets'],
    ['links', 'Linking wallets into operators'],
    ['done', 'Verdict'],
  ];
  const BAD = new Set(['virgin', 'sniper', 'deployer', 'one_shot_funded']);
  const WARN = new Set(['short_history', 'unread', 'sold']);

  // run(token, chain, {onEvent, onDone, onError}) -> cancel()
  function run(token, chain, ui) {
    let stopped = false, timer = null, after = 0, vis = null;
    const stop = () => {
      stopped = true;
      clearTimeout(timer);
      if (vis) { document.removeEventListener('visibilitychange', vis); vis = null; }
    };
    const fail = msg => { if (!stopped) { stop(); ui.onError(msg); } };

    function waitTick() {
      return new Promise(r => {
        const go = () => { vis = null; timer = setTimeout(r, POLL_MS); };
        if (!document.hidden) return go();
        vis = () => {
          if (document.hidden) return;
          document.removeEventListener('visibilitychange', vis);
          go();
        };
        document.addEventListener('visibilitychange', vis);
      });
    }

    async function finish(job) {
      for (let i = 0; i < 40 && !stopped; i++) {
        const d = await api.result(job);
        if (d.done) {
          if (d.error) return fail(d.error);
          stop();
          return ui.onDone(d.result);
        }
        await waitTick();
      }
      fail('scan did not finish, try again');
    }

    async function poll(job) {
      if (stopped) return;
      if (document.hidden) await waitTick();
      if (stopped) return;
      try {
        const d = await api.events(job, after);
        for (const e of d.events || []) { after++; if (!stopped) ui.onEvent(e); }
        if (d.done) return finish(job);
      } catch (e) {
        if (e.status === 404) return fail('scan expired, start it again');
      }
      await waitTick();
      poll(job);
    }

    api.startScan(token, chain).then(job => poll(job)).catch(e => fail(e.message));
    return stop;
  }

  // ---------------------------------------------------------------- console
  function Console(root) {
    this.steps = root.querySelector('[data-steps]');
    this.bar = root.querySelector('[data-bar]');
    this.log = root.querySelector('[data-log]');
    this.title = root.querySelector('[data-console-title]');
  }
  Console.prototype.reset = function (token) {
    this.at = -1;
    this.title.innerHTML = esc(t('Scan')) + ' <span class="mono">' + esc(short(token)) + '</span>';
    this.steps.innerHTML = STEPS.map(([k, label]) => `<li class="step" data-step="${k}"><i></i><span>${esc(t(label))}</span></li>`).join('');
    this.log.innerHTML = '';
    this.setStep(0);
  };
  Console.prototype.setStep = function (i) {
    if (i <= this.at) return;
    this.at = i;
    this.steps.querySelectorAll('.step').forEach((el, j) => {
      el.classList.toggle('ok', j < i || (i === STEPS.length - 1 && j === i));
      el.classList.toggle('on', j === i && i < STEPS.length - 1);
    });
    this.bar.style.width = Math.round(i / (STEPS.length - 1) * 100) + '%';
  };
  Console.prototype.line = function (html, cls) {
    const li = document.createElement('li');
    if (cls) li.className = cls;
    li.innerHTML = html;
    this.log.appendChild(li);
    while (this.log.children.length > 400) this.log.removeChild(this.log.firstChild);
    this.log.scrollTop = this.log.scrollHeight;
  };
  Console.prototype.event = function (e) {
    const w = e.wallet ? `<span class="w">${esc(short(e.wallet))}</span> ` : '';
    switch (e.type) {
      case 'stage': {
        const i = STEPS.findIndex(s => s[0] === e.detail);
        if (i >= 0) { this.setStep(i); this.line('› ' + esc(t(STEPS[i][1])) + '…'); }
        break;
      }
      case 'wallet_flag': {
        const fl = e.flags || [];
        const cls = fl.some(f => BAD.has(f)) ? 'bad' : fl.some(f => WARN.has(f)) ? 'warn' : 'good';
        this.line(w + esc(e.detail), cls);
        break;
      }
      case 'link':
        this.line(`link ${esc(e.kind || e.detail)}: ${esc(short(e.wallet))} ↔ ${esc(short(e.b))}`, 'warn');
        break;
      case 'cluster':
        this.line('operator ' + w + esc(e.detail), 'bad');
        break;
      case 'done':
        this.setStep(STEPS.length - 1);
        this.line('✓ ' + esc(e.headline || e.detail || 'done'), 'good');
        break;
      default:
        break;
    }
  };
  Console.prototype.labels = function () {
    if (!this.steps) return;
    this.steps.querySelectorAll('[data-step] span').forEach(el => {
      const row = STEPS.find(s => s[0] === el.parentNode.dataset.step);
      if (row) el.textContent = t(row[1]);
    });
    const mono = this.title && this.title.querySelector('.mono');
    if (!this.title) return;
    if (mono) this.title.innerHTML = esc(t('Scan')) + ' ' + mono.outerHTML;
    else this.title.textContent = t('Scan');
  };
  Console.prototype.error = function (msg) {
    this.steps.querySelectorAll('.step.on').forEach(el => el.classList.remove('on'));
    this.line('✕ ' + esc(msg), 'bad');
  };

  FS.scan = {run, Console, POLL_MS};
})();

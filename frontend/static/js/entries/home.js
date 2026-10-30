import "../api.js?module=1";
import "../chart.js?module=1";
import "../scan.js?module=1";
import "../result.js?module=1";
import "../recent.js?module=1";
import "../app.js?module=1";
import { initMobileNavigation } from "../components/mobile-navigation.js?module=1";

initMobileNavigation();

// Local preview only: explain the evidence model without fabricating a score
// or making a network request.
document.addEventListener('DOMContentLoaded', () => {
  const trigger = document.querySelector('[data-home-demo]');
  const close = document.querySelector('[data-home-demo-close]');
  const panel = document.querySelector('[data-home-demo-panel]');
  if (!trigger || !close || !panel) return;
  const setOpen = open => {
    panel.hidden = !open;
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) panel.querySelector('button')?.focus();
  };
  trigger.setAttribute('aria-expanded', 'false');
  trigger.addEventListener('click', () => setOpen(panel.hidden));
  close.addEventListener('click', () => { setOpen(false); trigger.focus(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !panel.hidden) { setOpen(false); trigger.focus(); } });
});

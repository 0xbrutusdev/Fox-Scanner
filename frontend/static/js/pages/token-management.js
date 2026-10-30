import { initSignalAnimations } from "../components/signal-animation.js";
import { MARKETING_PREVIEW } from "../data/marketing-preview.js";

const EVM_ADDRESS = /^0x[a-fA-F0-9]{40}$/;
const STATES = Object.freeze({
  unverified: { verdict: "Unverified", proof: "Not connected" },
  signature: { verdict: "Signature detected", proof: "Wallet linked" },
  verified: { verdict: "Verified", proof: "Identity published" },
});

function translated(value) {
  return window.FS?.i18n?.t?.(value) || value;
}

function toast(value) {
  window.FS?.toast?.(translated(value));
}

function initAddress(page) {
  const form = page.querySelector("#tm-form");
  const input = page.querySelector("#tm-ca");
  const url = page.querySelector("#tm-url");
  const status = page.querySelector("[data-address-status]");
  const preview = page.querySelector("[data-preview-address]");
  const initials = page.querySelector("[data-preview-initials]");
  if (!form || !input) return;

  const sync = () => {
    const address = input.value.trim();
    const valid = EVM_ADDRESS.test(address);
    if (url) url.href = valid ? `/?ca=${encodeURIComponent(address)}&chain=bnb` : "/";
    if (preview) preview.textContent = address ? `${address.slice(0, 8)}…${address.slice(-6)}` : MARKETING_PREVIEW.token.address;
    if (initials) initials.textContent = address ? address.slice(2, 4).toUpperCase() : MARKETING_PREVIEW.token.symbol.slice(0, 2);
    input.removeAttribute("aria-invalid");
    if (status) status.textContent = "";
  };
  form.addEventListener("submit", (event) => {
    if (EVM_ADDRESS.test(input.value.trim())) return;
    event.preventDefault();
    input.setAttribute("aria-invalid", "true");
    if (status) status.textContent = translated("Enter a 42-character BNB token address beginning with 0x.");
    input.focus();
  });
  input.addEventListener("input", sync);
  const placeholder = () => { input.placeholder = translated("BNB token address (0x…)"); };
  document.addEventListener("fs:lang", placeholder);
  placeholder();
  sync();
}

function initPreviewStates(page) {
  const setState = (state) => {
    const model = STATES[state] || STATES.unverified;
    page.dataset.previewState = state;
    page.querySelector("[data-preview-verdict]").textContent = translated(model.verdict);
    page.querySelector("[data-preview-proof]").textContent = translated(model.proof);
    page.querySelectorAll("[data-preview-state-target]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.previewStateTarget === state));
    });
  };
  page.querySelectorAll("[data-preview-state-target]").forEach((button) => {
    button.addEventListener("click", () => setState(button.dataset.previewStateTarget));
  });
  setState("unverified");
}

function initPreviewActions(page) {
  page.querySelectorAll("[data-pay]").forEach((button) => button.addEventListener("click", () => {
    const wallet = document.querySelector("[data-wallet]");
    if (wallet && !wallet.dataset.account) {
      wallet.click();
      return;
    }
    toast(`Preview only — no payment was submitted. Example amount: ${button.dataset.pay}.`);
  }));
  page.querySelector("[data-review]")?.addEventListener("click", () => {
    const note = page.querySelector("[data-review-note]");
    const address = page.querySelector("#tm-ca")?.value.trim() || "";
    if (!note) return;
    note.hidden = false;
    note.textContent = translated(EVM_ADDRESS.test(address) ? "No review on file for this token." : "Paste the token address first.");
  });
}

function initMobileWorkflow(page) {
  const query = matchMedia("(max-width: 800px)");
  const details = [...page.querySelectorAll(".manage-step details")];
  const prepare = ({matches}) => {
    if (!matches || page.dataset.mobileWorkflowReady === "true") return;
    details.forEach((item, index) => { item.open = index === 0; });
    page.dataset.mobileWorkflowReady = "true";
  };
  prepare(query);
  query.addEventListener?.("change", prepare);
}

export function initTokenManagementPage(scope = document) {
  const page = scope.querySelector("[data-manage-room]");
  if (!page || page.dataset.initialized === "true") return;
  page.dataset.initialized = "true";
  page.dataset.motionReady = "true";
  page.querySelectorAll(".manage-preview, .manage-step").forEach((node) => node.setAttribute("data-signal-animation", ""));
  initAddress(page);
  initPreviewStates(page);
  initPreviewActions(page);
  initMobileWorkflow(page);
  initSignalAnimations(page);
}

initTokenManagementPage();

import { initCodeExplorer } from "../components/code-explorer.js";
import { initCopyControls } from "../components/copy-control.js";
import { initDisclosures } from "../components/disclosure.js";
import { initSignalAnimations } from "../components/signal-animation.js";
import { MARKETING_PREVIEW } from "../data/marketing-preview.js";

const PREVIEW_PLANS = MARKETING_PREVIEW.plans;

const EVM_ADDRESS = /^0x[a-fA-F0-9]{40}$/;

function renderPlan(root, planId) {
  const plan = PREVIEW_PLANS.find((item) => item.id === planId) || PREVIEW_PLANS[1];
  const detail = root.querySelector("[data-plan-detail]");
  if (!detail) return;
  detail.replaceChildren();

  const header = document.createElement("div");
  header.className = "api-plan-detail__header";
  const identity = document.createElement("div");
  const label = document.createElement("p");
  label.className = "api-plan-detail__label";
  label.textContent = "PREVIEW PLAN";
  const title = document.createElement("h3");
  title.textContent = plan.name;
  identity.append(label, title);
  const price = document.createElement("p");
  price.className = "api-plan-detail__price";
  price.textContent = plan.price;
  header.append(identity, price);

  const note = document.createElement("p");
  note.className = "api-plan-detail__note";
  note.textContent = plan.note;
  const list = document.createElement("ul");
  plan.limits.forEach((limit) => {
    const item = document.createElement("li");
    item.textContent = limit;
    list.append(item);
  });
  const boundary = document.createElement("p");
  boundary.className = "api-plan-detail__boundary";
  boundary.textContent = "Preview only — no checkout or active account is available from this page.";
  const access = document.createElement("a");
  access.className = "btn ghost";
  access.href = "https://x.com/0x_Punisher";
  access.target = "_blank";
  access.rel = "noopener noreferrer";
  access.textContent = "Request API access on X";
  detail.append(header, note, list, boundary, access);

  root.querySelectorAll("[data-plan-id]").forEach((button) => {
    const selected = button.dataset.planId === plan.id;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  const select = root.querySelector("[data-plan-select]");
  if (select) select.value = plan.id;
}

function initPlanSelector(scope) {
  const root = scope.querySelector("[data-plan-selector]");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";
  const tabs = root.querySelector("[data-plan-tabs]");
  const select = root.querySelector("[data-plan-select]");

  PREVIEW_PLANS.forEach((plan) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.dataset.planId = plan.id;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", "false");
    tab.textContent = plan.recommended ? `${plan.name} · Suggested` : plan.name;
    tabs?.append(tab);
    const option = document.createElement("option");
    option.value = plan.id;
    option.textContent = plan.recommended ? `${plan.name} — Suggested` : plan.name;
    select?.append(option);
  });

  tabs?.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-plan-id]");
    if (tab) renderPlan(root, tab.dataset.planId);
  });
  tabs?.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...tabs.querySelectorAll("[data-plan-id]")];
    const current = buttons.indexOf(document.activeElement);
    let next = current;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = buttons.length - 1;
    if (event.key === "ArrowRight") next = (current + 1) % buttons.length;
    if (event.key === "ArrowLeft") next = (current - 1 + buttons.length) % buttons.length;
    event.preventDefault();
    buttons[next]?.focus();
    buttons[next]?.click();
  });
  select?.addEventListener("change", () => renderPlan(root, select.value));
  renderPlan(root, "developer");
}

function initDemoAddress(scope) {
  const form = scope.querySelector("[data-api-address-form]");
  const input = form?.querySelector("input[name='address']");
  const status = form?.querySelector("[role='status']");
  if (!form || !input || !status || form.dataset.initialized === "true") return;
  form.dataset.initialized = "true";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const address = input.value.trim();
    if (!EVM_ADDRESS.test(address)) {
      input.setAttribute("aria-invalid", "true");
      status.textContent = "Enter a 42-character EVM address beginning with 0x.";
      return;
    }
    input.removeAttribute("aria-invalid");
    scope.querySelectorAll("[data-demo-address]").forEach((slot) => { slot.textContent = address; });
    status.textContent = "Example updated locally. No scan was submitted.";
  });
}

export function initApiPage(scope = document) {
  const page = scope.querySelector(".signal-api");
  if (!page || page.dataset.initialized === "true") return;
  page.dataset.initialized = "true";
  initCodeExplorer(page);
  initCopyControls(page);
  initDisclosures(page);
  initSignalAnimations(page);
  initDemoAddress(page);
  initPlanSelector(page);
  page.classList.add("is-enhanced");
}

initApiPage();

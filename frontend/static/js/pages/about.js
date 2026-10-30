import { initSignalAnimations } from "../components/signal-animation.js";

export function initAboutPage(scope = document) {
  const page = scope.querySelector("[data-about-page]");
  if (!page || page.dataset.initialized === "true") return;
  page.dataset.initialized = "true";
  page.querySelectorAll("[data-signal-reveal]").forEach((node) => {
    node.setAttribute("data-signal-animation", "");
  });
  page.classList.add("is-signal-ready");
  initSignalAnimations(page);
}

initAboutPage();

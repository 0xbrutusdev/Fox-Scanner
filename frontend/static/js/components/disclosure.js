export function initDisclosures(root = document) {
  root.querySelectorAll("[data-disclosure]").forEach((container) => {
    if (container.matches("details")) return;
    const trigger = container.querySelector("[data-disclosure-trigger]");
    const panel = container.querySelector("[data-disclosure-panel]");
    if (!trigger || !panel || trigger.dataset.ready === "true") return;
    trigger.dataset.ready = "true";
    trigger.addEventListener("click", () => {
      const open = trigger.getAttribute("aria-expanded") !== "true";
      trigger.setAttribute("aria-expanded", String(open));
      panel.hidden = !open;
    });
  });
}

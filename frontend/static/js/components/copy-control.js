const restoreLabels = new WeakMap();

export function initCopyControls(root = document) {
  root.querySelectorAll("[data-copy], [data-copy-control]").forEach((button) => {
    if (button.dataset.ready === "true") return;
    button.dataset.ready = "true";
    const label = button.querySelector("[data-copy-label]");
    restoreLabels.set(button, (label || button).textContent.trim());
    button.addEventListener("click", async () => {
      const selector = button.dataset.copy || button.dataset.copyTarget;
      const source = selector ? root.querySelector(selector) : button.closest("[data-copy-scope]")?.querySelector("code");
      const value = source?.textContent?.trim() || button.dataset.copyText || "";
      if (!value) return;
      const output = button.querySelector("[data-copy-label]") || button;
      try {
        await navigator.clipboard.writeText(value);
        output.textContent = "Copied";
      } catch (_) {
        output.textContent = "Select to copy";
        source?.focus?.();
      }
      const live = root.querySelector("[data-copy-status]");
      if (live) live.textContent = output.textContent;
      window.setTimeout(() => {
        output.textContent = restoreLabels.get(button) || "Copy";
        if (live) live.textContent = "";
      }, 1600);
    });
  });
}

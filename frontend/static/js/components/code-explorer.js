export function initCodeExplorer(root = document) {
  root.querySelectorAll("[data-code-explorer]").forEach((explorer) => {
    const tabs = [...explorer.querySelectorAll("[data-code-tab]")];
    const panels = [...explorer.querySelectorAll("[data-code-panel]")];
    if (!tabs.length || tabs[0].dataset.ready === "true") return;
    const activate = (key, focus = false) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.codeTab === key;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.codePanel !== key; });
      const activePanel = panels.find((panel) => panel.dataset.codePanel === key);
      const activeCode = activePanel?.querySelector("code[id]");
      const copy = explorer.querySelector("[data-copy-control], [data-copy]");
      const activeTab = tabs.find((tab) => tab.dataset.codeTab === key);
      if (copy && activeCode) {
        copy.dataset.copyTarget = `#${activeCode.id}`;
        copy.setAttribute("aria-label", `Copy ${activeTab?.textContent.trim() || "active"} example`);
      }
    };
    tabs.forEach((tab, index) => {
      tab.dataset.ready = "true";
      tab.addEventListener("click", () => activate(tab.dataset.codeTab));
      tab.addEventListener("keydown", (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const delta = event.key === 'ArrowRight' ? 1 : -1;
        const next = tabs[(index + delta + tabs.length) % tabs.length];
        activate(next.dataset.codeTab, true);
      });
    });
    activate(tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.codeTab || tabs[0].dataset.codeTab);
  });
}

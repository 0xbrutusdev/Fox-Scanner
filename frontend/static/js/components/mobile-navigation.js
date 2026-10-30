const MOBILE_QUERY = "(max-width: 960px)";

export function initMobileNavigation(root = document) {
  const toggle = root.querySelector("[data-nav-toggle]");
  const nav = root.querySelector("[data-site-nav]");
  if (!toggle || !nav || toggle.dataset.ready === "true") return;
  toggle.dataset.ready = "true";

  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    nav.toggleAttribute("data-open", open);
    document.body.classList.toggle("nav-open", open);
  };
  const close = () => setOpen(false);

  toggle.addEventListener("click", () => {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) close();
  });
  document.addEventListener("click", (event) => {
    if (toggle.getAttribute("aria-expanded") === "true" && !nav.contains(event.target) && !toggle.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
      toggle.focus();
    }
  });
  matchMedia(MOBILE_QUERY).addEventListener?.("change", ({matches}) => {
    if (!matches) close();
  });
}

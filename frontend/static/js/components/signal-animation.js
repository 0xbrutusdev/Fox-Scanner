export function initSignalAnimations(root = document) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nodes = root.querySelectorAll("[data-signal-animation]");
  nodes.forEach((node) => node.classList.toggle("is-static", reduced));
  if (reduced || !nodes.length) return;
  if (!("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, {threshold: 0.2});
  nodes.forEach((node) => observer.observe(node));
}

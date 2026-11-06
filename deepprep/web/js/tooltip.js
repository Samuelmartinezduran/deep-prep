// Tooltip propio para los gráficos: sigue al ratón y no tapa la marca.
import { $ } from "./util.js";

export function activarTooltip() {
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest("[data-tip]");
    $("tip").hidden = !t;
    if (t) $("tip").innerHTML = t.dataset.tip;
  });
  document.addEventListener("mousemove", (e) => {
    const tip = $("tip");
    if (tip.hidden) return;
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    tip.style.transform = `translate(${x}px, ${e.clientY + 16}px)`;
  });
}

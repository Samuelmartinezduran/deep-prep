// Una sola página para las dos ventanas: la principal y la que va encima del juego (?vista=overlay).
import { ARMAZON } from "./cabecera.js";
import { estado } from "./estado.js";
import { activarEventos } from "./eventos.js";
import { activarTooltip } from "./tooltip.js";
import { $, sinImagenesRotas } from "./util.js";
import { cambiarVista, refrescar, reloj } from "./vistas.js";

estado.overlay = new URLSearchParams(location.search).get("vista") === "overlay";
document.body.classList.toggle("overlay", estado.overlay);
$("app").innerHTML = estado.overlay ? `<div id="principal"></div>` : ARMAZON;
sinImagenesRotas();
if (!estado.overlay) {
  activarEventos();
  activarTooltip();
}

// Se puede abrir directamente en una pestaña: /#revisiones o /#ajustes.
if (!estado.overlay && ["revisiones", "ajustes"].includes(location.hash.slice(1))) cambiarVista(location.hash.slice(1));
refrescar();
setInterval(refrescar, 1500);
setInterval(reloj, 1000);

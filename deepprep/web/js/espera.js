// Ventana principal, pestaña Partida, sin partida ni selección: qué hace la app y cómo sale el overlay.
import { LOGO } from "./iconos.js";
import { teclas } from "./piezas.js";
import { esc, pct } from "./util.js";

export function pintarEspera(e) {
  const sync = e.sync.total && e.sync.hechas < e.sync.total
    ? `<div class="sync"><div class="linea2">Descargando tu historial de la temporada · <span class="num">${e.sync.hechas} de ${e.sync.total}</span></div><span class="progreso"><i style="width:${pct(e.sync.hechas, e.sync.total)}%"></i></span></div>`
    : "";
  const texto = e.fase
    ? "En cuanto entres en partida, el panel se rellena solo."
    : "Abre el cliente del LoL. Mientras tanto puedes ver la partida de cualquier jugador con el buscador de arriba.";
  const ov = e.overlay || {};
  const atajo = teclas(ov.atajo);
  const pasos = ov.activo
    ? `<ol class="pasos limpia">
        <li><span class="n">01</span><div><b>Pantalla de carga</b><div class="linea2 envuelve">El panel sale solo encima del juego y se esconde al empezar.</div></div></li>
        <li><span class="n">02</span><div><b>Ya jugando</b><div class="linea2 envuelve">Mantén ${atajo} para verlo; al soltar, desaparece.</div></div></li>
        <li><span class="n">03</span><div><b>Dentro de las normas</b><div class="linea2 envuelve">Durante la partida solo enseña datos de antes de empezar, como permite Riot.</div></div></li>
      </ol>`
    : "";
  const aviso = ov.aviso ? `<div class="aviso-ventana">${esc(ov.aviso)}</div>` : "";
  return `<div class="espera">
      <div class="espera-icono">${LOGO}</div>
      <div class="etiqueta-cab">Deep Prep</div><h1>${esc(e.fase_txt)}</h1><p>${texto}</p>${sync}${pasos}${aviso}</div>`;
}

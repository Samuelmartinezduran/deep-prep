// Overlay (la ventana encima del juego, ?vista=overlay): lo justo para leerlo en dos segundos.
import { cajaDuelo } from "./duelo.js";
import { LOGO_PEQUENO } from "./iconos.js";
import { etapa, etiquetas, rango, retrato, rol, tarjetas, teclas, titulo } from "./piezas.js";
import { claseWr, esc } from "./util.js";

function ovFila(f) {
  let wr = `<span class="cargando">…</span>`;
  if (f.muestra.n) {
    const c = f.camp;
    wr = c.n
      ? `<div class="num ${claseWr(c.v, c.n)}">${c.v}/${c.n}</div><div class="linea2">campeón</div>`
      : `<div class="num ${claseWr(f.muestra.v, f.muestra.n)}">${f.muestra.v}/${f.muestra.n}</div><div class="linea2">últimas</div>`;
  }
  return `<div class="ov-fila ${f.soy_yo ? "yo" : ""}">
      ${rol(f.rol)}
      ${retrato(f.icono)}
      <div style="min-width:0"><div class="nombre"><bdi>${esc(f.nombre)}</bdi></div>${etiquetas(f.etiquetas, 2) || `<div class="linea2">${esc(f.campeon)}</div>`}</div>
      ${rango(f, true)}
      <div class="wr">${wr}</div>
    </div>`;
}

export function pintarOverlay(e) {
  const p = e.panel;
  if (!p) return `<div class="ov"><div class="ov-cab">${LOGO_PEQUENO}<span class="titulo">Deep Prep</span><span class="linea2">Esperando la partida…</span></div></div>`;
  const j = p.jungla;
  const jungla = j
    ? `<section class="caja">${titulo(`Jungla rival · ${esc(j.campeon)}`, `${j.n} partidas · ${j.n_lineas} líneas de tiempo`)}${tarjetas(j, true)}</section>`
    : `<section class="caja">${titulo("Jungla rival")}<p class="vacio">Sin datos.</p></section>`;
  const notas = (p.notas || []).map((n) => `<div class="aviso nota-ov"><span><b class="${n.rival ? "rival-txt" : "aliado-txt"}">${esc(n.campeon)}</b> ${esc(n.texto)}</span></div>`).join("");
  const destacado =
    notas +
    (e.modo === "juego"
      ? p.avisos.slice(0, Math.max(1, 3 - (p.notas || []).length)).map((a) => `<div class="aviso">${esc(a.texto)}</div>`).join("")
      : (p.plan.length ? `<ol class="limpia plan">${p.plan.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : "") +
        p.avisos.slice(0, 2).map((a) => `<div class="aviso ${esc(a.tono)}">${esc(a.texto)}</div>`).join(""));
  const atajo = teclas(e.overlay && e.overlay.atajo);
  const duelo = e.modo !== "juego" && p.duelo ? cajaDuelo(p.duelo, true) : "";
  return `<div class="ov">
      <div class="ov-cab">${LOGO_PEQUENO}
        <span class="titulo">${etapa(e.modo, p)}</span><span class="etiqueta-cab">${esc(p.cola)}</span>
        <span class="hueco"></span><span class="linea2 atajo">${e.modo === "juego" ? "Suelta" : "En partida, mantén"} ${atajo}</span>
        <span class="reloj" id="reloj"></span>
      </div>
      <div class="ov-equipos">
        <div class="ov-equipo aliado"><span class="etiqueta-cab">Tu equipo</span>${p.equipos.aliado.map(ovFila).join("")}</div>
        <div class="ov-equipo rival"><span class="etiqueta-cab">Rival</span>${p.equipos.rival.map(ovFila).join("")}</div>
      </div>
      <div class="ov-pie ${duelo ? "con-duelo" : ""}">${jungla}${duelo}<section class="caja">${titulo(e.modo === "juego" ? "Datos destacados" : "Antes de empezar")}${destacado || `<p class="vacio">Nada que destacar.</p>`}</section></div>
    </div>`;
}

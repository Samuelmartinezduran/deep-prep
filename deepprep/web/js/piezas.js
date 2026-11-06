// Piezas de HTML que comparten varias vistas. Todas devuelven texto HTML y escapan lo que viene de la app.
import { tip } from "./tooltip.js";
import { claseWr, esc, pct, ROL_TXT, ROLES } from "./util.js";

export const retrato = (url, clase = "retrato") => (url ? `<img class="${clase}" src="${esc(url)}" alt="">` : `<span class="${clase}"></span>`);
export const rol = (r) => (ROLES[r] ? `<span class="rol" style="--icono:url('/img/rol/${ROLES[r]}.svg')" title="${esc(ROL_TXT[r] || r)}"></span>` : `<span></span>`);
// Título de caja. Recibe HTML: lo que venga de la app tiene que llegar ya escapado.
export const titulo = (txt, extra = "") => `<h2><span class="etiqueta-cab">${txt}</span>${extra ? `<small>${extra}</small>` : ""}</h2>`;
// Caja vacía con un aviso (sin datos o con un error al pedirlos).
export const cajaVacia = (texto) => `<section class="caja"><p class="vacio">${esc(texto)}</p></section>`;
export const lp = (c) => `<span class="num lp ${c > 0 ? "bien" : c < 0 ? "mal" : "suave"}">${c > 0 ? "+" : c < 0 ? "−" : "±"}${Math.abs(c)} LP</span>`;
export const diferencia = (a, b, sufijo = "") => {
  const d = a - b;
  return `<span class="${d > 0 ? "bien" : d < 0 ? "mal" : "suave"}">${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d)}${sufijo}</span>`;
};
// "ctrl+tab" -> <kbd>CTRL</kbd><kbd>TAB</kbd>
export const teclas = (atajo) => (atajo ? atajo.split("+").map((k) => `<kbd>${esc(k.trim().toUpperCase())}</kbd>`).join("") : "");

export function etapa(modo, p) {
  if (p.terminada) return "Partida terminada";
  return modo === "juego" ? "En partida" : modo === "carga" ? "Pantalla de carga" : "En vivo";
}

export function racha(lista) {
  if (!lista || !lista.length) return "";
  // La más reciente a la derecha, como se lee una racha; victoria hacia arriba, derrota hacia abajo.
  const v = lista.filter(Boolean).length;
  return `<div class="racha" title="Últimas ${lista.length}: ${v}V ${lista.length - v}D, la más reciente a la derecha">${lista
    .slice()
    .reverse()
    .map((g) => `<i class="${g ? "v" : ""}"></i>`)
    .join("")}</div>`;
}

// Barra de porcentaje con la marca del 50 %. El color lo lleva la cifra, no la barra.
export function barraWr(v, n) {
  const p = pct(v, n);
  return `<span class="barra-wr" title="${v} de ${n}"><i style="width:${p}%"></i></span>`;
}

export function rango(f, compacto) {
  if (f.oculto) return `<div class="linea2">Perfil oculto</div>`;
  if (!f.liga) return `<div class="cargando">…</div>`;
  const s = f.liga.solo;
  const flex = f.liga.flex && !compacto ? ` · Flex ${esc(f.liga.flex.txt)}` : "";
  if (!s) return `<div class="rango"><img src="/img/rango/unranked.svg" alt=""><div><div class="txt">Sin rango</div><div class="linea2">en solo/dúo${flex}</div></div></div>`;
  const total = s.v + s.d;
  const detalle = compacto ? `${s.lp} LP` : `${s.lp} LP${total ? ` · <span class="${claseWr(s.v, total)}">${pct(s.v, total)}%</span>` : ""}`;
  return `<div class="rango"><img src="/img/rango/${esc(s.nivel)}.svg" alt="">
    <div style="min-width:0" title="${total ? `${s.v}V ${s.d}D en solo/dúo` : ""}"><div class="txt">${esc(s.txt)}</div><div class="linea2 num">${detalle}${flex}</div></div></div>`;
}

export function etiquetas(lista, max) {
  const l = max ? lista.slice(0, max) : lista;
  return l.length ? `<div class="etiquetas">${l.map((e) => `<span class="etq ${esc(e.tono)}" title="${esc(e.d)}">${esc(e.t)}</span>`).join("")}</div>` : "";
}

// "min 4:33 · top 4 · mid 1 · bot 2" -> barras por línea; si el texto no tiene ese formato, se deja tal cual.
export function graficoGank(valor) {
  const lineas = [...String(valor).matchAll(/\b(top|mid|bot)\s+(\d+)/g)].map((m) => ({ l: m[1], n: Number(m[2]) }));
  if (lineas.length < 2) return "";
  const max = Math.max(...lineas.map((x) => x.n));
  const total = lineas.reduce((a, x) => a + x.n, 0);
  return `<div class="mini-barras" role="img" aria-label="Primer gank por línea: ${esc(lineas.map((x) => `${x.l} ${x.n}`).join(", "))}">${lineas
    .map((x) => `<div class="mb-fila" ${tip(["b", x.l], ` · ${x.n} de ${total}`)}><span>${esc(x.l)}</span><span class="mb-pista"><i style="width:${(100 * x.n) / max}%"></i></span><span class="num">${x.n}</span></div>`)
    .join("")}</div>`;
}

export function tarjetas(j, compacto) {
  return `<div class="tarjetas">${j.tarjetas
    .map((t) => {
      const grafico = !compacto && /gank/i.test(t.titulo) ? graficoGank(t.valor) : "";
      return `<div class="tarjeta ${esc(t.tono)}"><div class="etiqueta-cab">${esc(t.titulo)}</div><div class="v">${esc(t.valor)}</div>${grafico}${compacto ? "" : `<div class="d">${esc(t.detalle)}</div>`}</div>`;
    })
    .join("")}</div>`;
}

// Tu historial contra los campeones de la partida (panel y selección de campeón).
export function filasVs(vs, miCampeon) {
  const filas = vs
    .filter((f) => f.n)
    .map((f) => {
      const mio = f.n_mio ? `con ${esc(miCampeon)} <b class="num">${f.v_mio}V ${f.n_mio - f.v_mio}D</b>` : "";
      return `<div class="vs">${retrato(f.icono, "mini")}<span>${esc(f.nombre)}</span><span class="linea2">${mio}</span><span class="num"><span class="suave">total</span> <span class="${claseWr(f.v, f.n)}">${f.v}V ${f.n - f.v}D</span></span></div>`;
    })
    .join("");
  const sin = vs.filter((f) => !f.n).map((f) => esc(f.nombre));
  return filas + (sin.length ? `<div class="linea2 envuelve" style="margin-top:8px">Sin cruces con ${sin.join(", ")}.</div>` : "");
}

// Notas por campeón (las escribes en Ajustes).
export function cajaNotas(notas) {
  if (!notas || !notas.length) return "";
  return `<section class="caja">${titulo("Tus notas")}${notas
    .map((n) => `<div class="nota">${retrato(n.icono, "mini")}<div><b class="${n.rival ? "rival-txt" : "aliado-txt"}">${esc(n.campeon)}</b><div>${esc(n.texto)}</div></div></div>`)
    .join("")}</section>`;
}

// Ventana principal, pestaña Partida, durante la selección de campeón.
import { cajaDuelo } from "./duelo.js";
import { barraWr, cajaNotas, filasVs, racha, retrato, titulo } from "./piezas.js";
import { claseWr, esc, pct } from "./util.js";

// Tus opciones contra el campeón rival de tu posición. Son datos para elegir tú: no se marca ninguno.
export function cajaPool(pool, pos) {
  if (!pool) {
    return pos
      ? `<section class="caja">${titulo("Tu pool")}<p class="vacio">Cuando el rival elija a alguien de ${esc(pos)} verás aquí tus campeones contra él.</p></section>`
      : "";
  }
  const filas = pool.filas
    .map((f) => {
      const master = f.wr == null
        ? `<span class="linea2">${f.n ? `${f.n} partidas, pocas` : "sin partidas"}</span>`
        : `<span class="num ${f.wr >= 53 ? "bien" : f.wr <= 47 ? "mal" : ""}">${f.wr}%</span>${barraWr(f.v, f.n)}<span class="num suave">${f.n}</span>`;
      const yo = f.yo_n ? `<span class="num">${f.yo_v}V ${f.yo_n - f.yo_v}D</span>` : `<span class="suave">—</span>`;
      const vs = f.vs_n ? `<span class="num">${f.vs_v}V ${f.vs_n - f.vs_v}D</span>` : `<span class="suave">—</span>`;
      return `<div class="pool-fila"><span class="pool-camp">${retrato(f.icono, "mini")}<b>${esc(f.nombre)}</b></span><span class="pool-master">${master}</span>${yo}${vs}</div>`;
    })
    .join("");
  return `<section class="caja">${titulo(`Tu pool contra ${esc(pool.rival)}`, `${esc(pool.pos)} · partidas de Master+ y las tuyas de la temporada`)}
      <div class="pool-fila cabeza"><span>Campeón</span><span>Master+ contra ${esc(pool.rival)}</span><span>Tú con él</span><span>Tú contra ${esc(pool.rival)}</span></div>
      ${filas || `<p class="vacio">No tienes campeones de ${esc(pool.pos)} con 5 partidas o más esta temporada.</p>`}
      <div class="linea2 envuelve pie-tu">Ordenado por el % de Master+ (con 8 partidas o más). Son datos para decidir tú.</div></section>`;
}

export function pintarSeleccion(s) {
  const h = s.historial;
  const mio = s.mio;
  const sub = mio
    ? h.campeon && h.campeon.n
      ? `<span class="num">${h.campeon.v}V ${h.campeon.n - h.campeon.v}D</span> con ${esc(mio.nombre)} esta temporada${esc(h.cola_txt)} · <span class="num ${claseWr(h.campeon.v, h.campeon.n)}">${pct(h.campeon.v, h.campeon.n)}%</span>`
      : `Sin partidas con ${esc(mio.nombre)} esta temporada`
    : "Cuando elijas campeón verás aquí tu historial con él.";
  return `<section class="hero">${mio ? retrato(mio.icono, "retrato hero-retrato") : ""}
      <div class="hero-txt"><div class="etiqueta-cab">Selección de campeón</div><h1>${mio ? esc(mio.nombre) : "Aún no has elegido"}</h1><div class="sub">${sub}</div></div>
      <div class="derecha">${h.campeon && h.campeon.racha ? `<div class="dato"><span class="etiqueta-cab">Últimas con él</span>${racha(h.campeon.racha)}</div>` : ""}</div></section>
    <div class="cuerpo">
      <div class="principal-col">
      ${cajaPool(s.pool, s.pos)}
      <section class="caja">${titulo("Contra lo que van eligiendo", `tus ${h.n} clasificatorias${esc(h.cola_txt)} de la temporada`)}
        ${h.vs.length ? filasVs(h.vs, mio ? mio.nombre : "") : `<p class="vacio">El rival aún no ha elegido.</p>`}</section>
      </div>
      <aside class="lateral">${cajaDuelo(s.duelo)}${cajaNotas(s.notas)}<section class="caja">${titulo("Qué se ve aquí")}
        <p class="envuelve">Solo campeones y tu historial contra ellos. En clasificatoria los nombres de tus aliados están ocultos y la app no intenta averiguarlos.${s.pos && !s.duelo ? ` Tu duelo de ${esc(s.pos)} sale cuando el rival elija a alguien de esa posición.` : ""}</p></section></aside>
    </div>`;
}

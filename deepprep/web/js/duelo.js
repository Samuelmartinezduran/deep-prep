// Tu duelo contra el rival directo (Master+) y tú contra tu referencia (la eliges en Ajustes).
import { retrato, titulo } from "./piezas.js";
import { esc, numero } from "./util.js";

// Barras emparejadas por fila, cada fila con su propia escala; tú en violeta, la referencia en gris.
export function tablaComparacion(c, pie) {
  if (!c || !c.filas.length) return "";
  const clase = (m) => (m === true ? "bien" : m === false ? "mal" : "");
  const filas = c.filas
    .map((f) => {
      const a = numero(f.tu);
      const b = numero(f.ref);
      const barras = Number.isFinite(a) && Number.isFinite(b) && (a || b);
      const max = barras ? Math.max(Math.abs(a), Math.abs(b)) : 1;
      const signo = a < 0 || b < 0;
      const barra = (v, cl) => {
        const w = (50 * Math.abs(v)) / max;
        return signo
          ? `<span class="par-pista centro"><i class="${cl}" style="${v < 0 ? `right:50%` : `left:50%`};width:${w}%"></i></span>`
          : `<span class="par-pista"><i class="${cl}" style="left:0;width:${2 * w}%"></i></span>`;
      };
      return `<div class="par">
          <div class="par-que">${esc(f.que)}</div>
          <div class="par-val num ${clase(f.mejor)}">${esc(f.tu)}</div>${barras ? barra(a, "tu") : "<span></span>"}
          <div class="par-val num suave">${esc(f.ref)}</div>${barras ? barra(b, "ref") : "<span></span>"}
        </div>`;
    })
    .join("");
  return `<div class="comparativa">
      <div class="leyenda"><span><i class="tu"></i>Tú</span><span><i class="ref"></i>${esc(c.ref)}</span></div>
      ${filas}
      <div class="linea2 envuelve pie-tu">${pie} ${esc(c.ref)}: media de ${c.n_ref} partidas. Se cambia en Ajustes.</div>
    </div>`;
}

// Solo antes de empezar. compacto: la versión del overlay (dos datos, sin tablas ni build).
export function cajaDuelo(d, compacto) {
  if (!d) return "";
  const cab = `<div class="duelo-cab">
      <div class="duelista">${retrato(d.icono_a, "mini")}<b>${esc(d.a)}</b></div>
      <span class="vs-txt">vs</span>
      <div class="duelista">${retrato(d.icono_b, "mini")}<b class="rival-txt">${esc(d.b)}</b></div>
      ${d.poco ? "" : `<div class="duelo-wr"><span class="num">${d.wr}%</span><span class="linea2">gana ${esc(d.a)}</span></div>`}
    </div>`;
  const cabecera = titulo(`Tu duelo · ${esc(d.pos)}`, `${d.n} partidas de Master+`);
  if (d.poco) {
    const motivo = d.en_pool
      ? "Aún hay pocas partidas de este duelo; el recolector sigue buscando."
      : `${esc(d.a)} en ${esc(d.pos)} no está entre tus campeones más jugados, así que no se recogen sus partidas.`;
    const tuPoco = compacto ? "" : tablaComparacion(d.tu, `Tú: tus ${d.tu ? d.tu.n : 0} partidas con ${esc(d.a)} de ${esc(d.pos)}.`);
    return `<section class="caja duelo">${cabecera}${cab}<p class="vacio">${motivo}</p>${tuPoco}</section>`;
  }
  const datos = (compacto ? d.datos.slice(0, 2) : d.datos)
    .map((x) => `<li class="dato-duelo"><div>${esc(x.texto)}</div>${compacto ? "" : `<div class="linea2 envuelve">${esc(x.detalle)}</div>`}</li>`)
    .join("");
  const tu = compacto ? "" : tablaComparacion(d.tu, `Tú: tus ${d.tu ? d.tu.n : 0} partidas con ${esc(d.a)} de ${esc(d.pos)}, contra cualquiera.`);
  const b = d.build;
  const build = !compacto && b
    ? `<div class="build-duelo"><span class="etiqueta-cab">Lo más jugado</span><div>${esc(b.runa)} + ${esc(b.secundaria)} · ${esc(b.objeto)} <span class="suave">(min ${esc(b.minuto)}, gana ${b.wr_objeto}% de ${b.n_objeto})</span>${b.maximiza ? ` · ${esc(b.maximiza)}` : ""}</div></div>`
    : "";
  return `<section class="caja duelo">${cabecera}${cab}<ul class="limpia">${datos}</ul>${tu}${build}</section>`;
}

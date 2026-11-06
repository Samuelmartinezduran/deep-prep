// Ventana principal, pestaña Ajustes: el formulario, guardarlo y cerrar la app.
import { enviar, ErrorApi, pedir } from "./api.js";
import { estado } from "./estado.js";
import { cajaVacia } from "./piezas.js";
import { $, esc } from "./util.js";

export function filaReferencia(nombre, rid, estadoRef) {
  return `<div class="nota-edit ref-edit"><input type="text" list="lista-campeones" class="campeon-ref" value="${esc(nombre)}" placeholder="Campeón">
    <input type="text" class="rid-ref" value="${esc(rid)}" placeholder="Jugador (Nombre#TAG), de cualquier servidor"><button class="quitar-nota" title="Quitar">Quitar</button>
    ${estadoRef ? `<span class="linea2 estado-ref">${esc(estadoRef)}</span>` : ""}</div>`;
}

export function filaNota(nombre, texto) {
  return `<div class="nota-edit"><input type="text" list="lista-campeones" class="campeon-nota" value="${esc(nombre)}" placeholder="Campeón">
    <input type="text" class="texto-nota" value="${esc(texto)}" placeholder="Tu nota (sale cuando está en la partida)"><button class="quitar-nota" title="Quitar">Quitar</button></div>`;
}

const grupo = (nombre, desc, cuerpo) =>
  `<section class="grupo"><div class="grupo-txt"><h2>${nombre}</h2><p>${desc}</p></div><div class="grupo-campos">${cuerpo}</div></section>`;
const interruptor = (id, activo, texto) =>
  `<label class="interruptor"><input type="checkbox" id="${id}" ${activo ? "checked" : ""}><span class="pista" aria-hidden="true"></span><span>${texto}</span></label>`;

// El formulario entero a partir de /api/ajustes (sin tocar la página: se puede probar como texto).
export function htmlAjustes(a) {
  const campeones = a.campeones || [];
  const nombre = (id) => (campeones.find((c) => String(c.id) === String(id)) || {}).nombre || id;
  const notas = Object.entries(a.notas || {}).map(([id, txt]) => filaNota(nombre(id), txt)).join("");
  const refs = Object.entries(a.referencias || {})
    .map(([id, rid]) => {
      const n = (a.referencias_partidas || {})[id];
      return filaReferencia(nombre(id), rid, n == null ? "" : n ? `${n} partidas suyas con ese campeón` : "buscando sus partidas…");
    })
    .join("");
  const opciones = Object.entries(a.opciones_comparar || {})
    .map(([k, v]) => `<option value="${esc(k)}" ${k === a.comparar_con ? "selected" : ""}>${esc(v)}</option>`)
    .join("");
  const opacidad = Math.round((a.overlay_opacidad || 0.94) * 100);
  return `<div class="ajustes">
    ${grupo("Panel encima del juego", "Sale solo en la pantalla de carga y, ya jugando, mientras mantienes el atajo. Durante la partida solo enseña datos de antes de empezar, como permite Riot. El juego tiene que estar en ventana sin bordes.", `
      ${interruptor("a-overlay", a.overlay, "Enseñarlo en la pantalla de carga y al mantener el atajo")}
      <label>Atajo (mantener) <input type="text" id="a-atajo" value="${esc(a.atajo_overlay)}" placeholder="ctrl+tab"></label>
      <label>Opacidad <span class="rango-fila"><input type="range" id="a-opacidad" min="40" max="100" value="${opacidad}"><span class="num" id="opacidad-valor">${opacidad}%</span></span></label>`)}
    ${grupo("Siempre en marcha", "Así el recolector sigue llenando tus duelos de Master+ y el overlay está listo al jugar. Gasta muy poco: en torno al 2% de un núcleo y 130 MB de memoria.", `
      ${interruptor("a-siempre", a.siempre_en_marcha, "Arrancar con Windows y seguir con el LoL cerrado")}
      <div><button id="salir-app">Cerrar Deep Prep del todo</button></div>`)}
    ${grupo("Grabación", "Cada partida en la Grieta se graba en Vídeos\\LoL-coach y la revisión apunta el minuto de cada muerte en el vídeo.", `
      ${interruptor("a-grabar", a.grabar, "Grabar cada partida en la Grieta")}
      <label>Grabar con <select id="a-codificador">
        <option value="auto" ${a.grabacion_codificador !== "cpu" ? "selected" : ""}>La gráfica si se puede (gasta menos procesador)</option>
        <option value="cpu" ${a.grabacion_codificador === "cpu" ? "selected" : ""}>El procesador</option></select></label>
      <label>Espacio máximo, en GB <input type="text" id="a-max-gb" value="${esc(String(a.grabacion_max_gb ?? 0))}" inputmode="numeric" class="corto"><span class="ayuda">0 = sin límite; al pasarlo se borran las más viejas.</span></label>`)}
    ${grupo("Tus cuentas", "Una por línea, como Nombre#TAG. Las partidas de todas cuentan para tu historial y tus revisiones.", `
      <textarea id="a-cuentas" rows="3" aria-label="Tus cuentas">${esc((a.cuentas || []).join("\n"))}</textarea>`)}
    ${grupo("Tus reglas", "Salen en cada partida, una por línea. Escríbelas como hábitos que puedas comprobar.", `
      <textarea id="a-reglas" rows="4" aria-label="Tus reglas">${esc((a.recordatorios || []).join("\n"))}</textarea>`)}
    ${grupo("Con quién compararte", "Se usa en tu duelo y en cada revisión. Con un perfil de base te comparas con ese jugador en todo: con tu campeón si lo juega y, si no, en tu posición. Un jugador por campeón manda cuando juegas ese campeón. Sus partidas se recogen solas.", `
      <label>Referencia de base <select id="a-comparar">${opciones}</select></label>
      <label id="caja-perfil" ${a.comparar_con === "perfil" ? "" : "hidden"}>Tu perfil de referencia (Nombre#TAG, de cualquier servidor)
        <input type="text" id="a-perfil" value="${esc(a.perfil_base || "")}" placeholder="p. ej. un jugador de Challenger al que quieras parecerte">
        ${a.perfil_partidas == null ? "" : `<span class="ayuda">${a.perfil_partidas ? `${esc(a.perfil_partidas)} partidas suyas guardadas` : "buscando sus partidas…"}</span>`}</label>
      <div class="sub-campos"><span class="etiqueta-cab">Por campeón</span><div id="referencias">${refs}</div><div><button id="nueva-ref">Añadir jugador de referencia</button></div></div>`)}
    ${grupo("Notas por campeón", "Salen cuando ese campeón está en tu partida, en el panel y encima del juego.", `
      <div id="notas">${notas}</div><div><button id="nueva-nota">Añadir nota</button></div>`)}
    <datalist id="lista-campeones">${campeones.map((c) => `<option value="${esc(c.nombre)}">`).join("")}</datalist>
    <div class="guardar"><button class="primario" id="guardar-ajustes">Guardar cambios</button><span id="ajustes-estado" class="linea2"></span>
      <span class="linea2 version">Deep Prep ${esc(a.version.version)}${a.version.lista ? ` · la ${esc(a.version.nueva)} se instala sola cuando cierres esta ventana, fuera de partida` : ""}</span></div>
  </div>`;
}

export async function pintarAjustes() {
  let a;
  try {
    a = await pedir("/api/ajustes");
  } catch (e) {
    if (!(e instanceof ErrorApi)) throw e;
    if (estado.vista === "ajustes") $("principal").innerHTML = cajaVacia(`${e.message}: no se han podido cargar los ajustes.`);
    return;
  }
  if (estado.vista !== "ajustes") return;
  estado.campeones = a.campeones;
  $("principal").innerHTML = htmlAjustes(a);
}

// Notas y referencias por campeón de las filas del formulario: {id del campeón: texto}. Las filas sin
// campeón conocido o sin texto no cuentan.
export function leerFilas(filas, campeones) {
  const out = {};
  for (const [nombre, texto] of filas) {
    const c = campeones.find((x) => x.nombre.toLowerCase() === nombre.trim().toLowerCase());
    if (c && texto.trim()) out[c.id] = texto.trim();
  }
  return out;
}

const valores = (selector, campo, otro) =>
  [...document.querySelectorAll(selector)].map((fila) => [fila.querySelector(campo).value, fila.querySelector(otro).value]);

export async function guardarAjustes() {
  const notas = leerFilas(valores(".nota-edit:not(.ref-edit)", ".campeon-nota", ".texto-nota"), estado.campeones);
  const referencias = leerFilas(valores(".ref-edit", ".campeon-ref", ".rid-ref"), estado.campeones);
  $("ajustes-estado").textContent = "Guardando…";
  const lineas = (id) => $(id).value.split("\n").map((x) => x.trim()).filter(Boolean);
  const r = await enviar("/api/ajustes", {
    overlay: $("a-overlay").checked,
    atajo_overlay: $("a-atajo").value,
    overlay_opacidad: Number($("a-opacidad").value) / 100,
    grabar: $("a-grabar").checked,
    grabacion_codificador: $("a-codificador").value,
    grabacion_max_gb: $("a-max-gb").value,
    siempre_en_marcha: $("a-siempre").checked,
    comparar_con: $("a-comparar").value,
    perfil_base: $("a-perfil").value,
    referencias,
    cuentas: lineas("a-cuentas"),
    recordatorios: lineas("a-reglas"),
    notas,
  });
  if (r.ok) await pintarAjustes(); // así se ve el estado de las referencias nuevas
  const aviso = $("ajustes-estado");
  if (!aviso) return; // la pestaña ya no está (o los ajustes no se han podido volver a cargar)
  aviso.textContent = r.ok ? "Guardado." : r.error;
  aviso.className = r.ok ? "bien" : "mal";
}

export async function salirApp() {
  const r = await enviar("/api/salir", {});
  $("ajustes-estado").textContent = r.ok ? "Cerrando…" : r.error;
}

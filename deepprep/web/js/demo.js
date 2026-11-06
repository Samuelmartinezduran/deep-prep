// Modo demo (py -m deepprep --demo): la barra de arriba que cambia de escena. Solo sale si el estado trae «demo».
import { enviar } from "./api.js";
import { estado } from "./estado.js";
import { $, esc } from "./util.js";

// En el orden de una partida. Las tres primeras son de la partida de ejemplo (las cambia la app, y con ellas el
// overlay); Revisiones y Ajustes son pestañas del panel. overlay: la escena también sale encima del juego.
export const ESCENAS = [
  {
    id: "seleccion",
    nombre: "Selección de campeón",
    vista: "partida",
    txt: "Antes de elegir: tu duelo en partidas de Master+, tu pool contra el rival y tu historial contra lo que van eligiendo.",
  },
  {
    id: "carga",
    nombre: "Pantalla de carga",
    vista: "partida",
    overlay: true,
    txt: "Mientras carga: los diez jugadores, el jungla rival y su mapa, y dónde va a haber errores. También sale encima del juego.",
  },
  {
    id: "juego",
    nombre: "En partida",
    vista: "partida",
    overlay: true,
    txt: "Ya jugando, solo datos de antes de empezar: sin plan, sin veredictos ni mapa del jungla, como piden las normas de Riot.",
  },
  {
    id: "revisiones",
    nombre: "Revisiones",
    vista: "revisiones",
    txt: "Al acabar: la línea de tiempo de la partida, dónde mueres y qué acertó o falló el panel.",
  },
  {
    id: "ajustes",
    nombre: "Ajustes",
    vista: "ajustes",
    txt: "Se pueden cambiar y guardar: en la demo van a una carpeta temporal que se borra al cerrar.",
  },
];

// La escena que se está viendo: la pestaña abierta o, en Partida, la de la partida de ejemplo.
export const escenaActual = (demo, vista) => (vista === "partida" ? demo.escena : vista);

export function htmlDemo(demo, vista) {
  const actual = escenaActual(demo, vista);
  const escena = ESCENAS.find((x) => x.id === actual) || ESCENAS[0];
  const botones = ESCENAS.map(
    (x) => `<button class="${x.id === escena.id ? "activa" : ""}" data-escena="${x.id}" aria-pressed="${x.id === escena.id}">${esc(x.nombre)}</button>`
  ).join("");
  const overlay = escena.overlay ? `<a class="demo-overlay" href="/?vista=overlay" target="_blank" rel="noopener">Ver el overlay ↗</a>` : "";
  return `<div class="demo" role="region" aria-label="Modo demo">
      <span class="demo-marca"><span class="punto"></span>Modo demo</span>
      <div class="selector" role="group" aria-label="Escena de la demo">${botones}</div>
      <p class="demo-txt" id="demo-txt">${esc(escena.txt)}</p>${overlay}
    </div>`;
}

// Pinta la barra (o la quita, fuera de la demo); solo si ha cambiado la escena que se ve.
export function pintarDemo(e) {
  const caja = $("demo");
  if (!caja) return;
  const actual = e && e.demo ? escenaActual(e.demo, estado.vista) : "";
  if (caja.dataset.escena === actual) return;
  caja.dataset.escena = actual;
  caja.innerHTML = actual ? htmlDemo(e.demo, estado.vista) : "";
}

// Botón de una escena: las de la partida se piden a la app. Devuelve la pestaña que hay que abrir (o null si no se
// puede: el error sale en la barra, en lugar de la explicación).
export async function elegirEscena(id) {
  const escena = ESCENAS.find((x) => x.id === id);
  if (!escena) return null;
  if (escena.vista === "partida") {
    const r = await enviar("/api/demo", { escena: id });
    if (!r.ok) {
      $("demo-txt").textContent = r.error;
      return null;
    }
    if (estado.actual && estado.actual.demo) estado.actual.demo.escena = id;
  }
  return escena.vista;
}

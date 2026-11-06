// Qué se pinta y cuándo: el bucle que pide el estado a la app, las pestañas y el reloj de la partida.
import { pintarAjustes } from "./ajustes.js";
import { chip, pintarCabecera } from "./cabecera.js";
import { pintarEspera } from "./espera.js";
import { estado } from "./estado.js";
import { pintarOverlay } from "./overlay.js";
import { pintarPanel } from "./panel.js";
import { pintarRevisiones } from "./revisiones.js";
import { pintarSeleccion } from "./seleccion.js";
import { $, TITULOS } from "./util.js";

export function cambiarVista(v) {
  estado.vista = v;
  document.querySelectorAll("#pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.vista === v));
  $("titulo-vista").textContent = TITULOS[v];
  estado.ultimo = "";
  if (v === "revisiones") pintarRevisiones();
  else if (v === "ajustes") pintarAjustes();
  else refrescar();
}

function pintar(e) {
  const anterior = estado.actual;
  estado.actual = e;
  const p = e.panel;
  if (e.reloj) estado.inicioPartida = Date.now() - e.reloj * 1000;
  else estado.inicioPartida = p && !p.terminada && e.modo === "juego" ? p.inicio : 0;
  if (estado.overlay) {
    $("principal").innerHTML = pintarOverlay(e);
  } else {
    pintarCabecera(e);
    if (estado.vista === "partida") {
      $("principal").innerHTML = p && (!e.seleccion || !p.terminada) ? pintarPanel(e) : e.seleccion ? pintarSeleccion(e.seleccion) : pintarEspera(e);
    } else if (estado.vista === "revisiones" && e.ultima_revision && e.ultima_revision !== (anterior || {}).ultima_revision) {
      pintarRevisiones();
    }
  }
  reloj();
}

export function reloj() {
  const el = $("reloj");
  if (!el) return;
  if (!estado.inicioPartida) return void (el.textContent = estado.overlay ? "" : "—");
  const s = Math.max(0, Math.floor((Date.now() - estado.inicioPartida) / 1000));
  el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// Pide el estado y repinta solo si ha cambiado. Sin respuesta, lo dice el chip de estado.
export async function refrescar() {
  try {
    const texto = await (await fetch(estado.overlay ? "/api/estado?vista=overlay" : "/api/estado")).text();
    if (texto === estado.ultimo) return;
    estado.ultimo = texto;
    pintar(JSON.parse(texto));
  } catch {
    if (!estado.overlay) $("fase").innerHTML = chip("Sin conexión con la app");
  }
}

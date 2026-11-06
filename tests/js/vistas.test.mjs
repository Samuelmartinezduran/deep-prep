// Las vistas como texto: el panel, la selección, la espera y el overlay con el estado de la maqueta
// (herramientas/maquetas/partida.json), y lo que cambia en cada modo.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { beforeEach, describe, test } from "node:test";

import { pintarEspera } from "../../deepprep/web/js/espera.js";
import { estado } from "../../deepprep/web/js/estado.js";
import { pintarOverlay } from "../../deepprep/web/js/overlay.js";
import { estadoCarga, fila, mapaJungla, pintarPanel } from "../../deepprep/web/js/panel.js";
import { cajaPool, pintarSeleccion } from "../../deepprep/web/js/seleccion.js";
import { textoDe } from "./ayuda.mjs";

const MAQUETA = JSON.parse(readFileSync(new URL("../../herramientas/maquetas/partida.json", import.meta.url), "utf8"));
const copia = () => structuredClone(MAQUETA);
const MALO = `<img src=x onerror=alert(1)>`;
const sinImgMala = (html) => assert.doesNotMatch(html, /<img src=x/);

beforeEach(() => {
  estado.minutoMapa = "3";
});

describe("panel de la partida", () => {
  test("pantalla de carga con la maqueta", () => {
    const e = copia();
    const html = pintarPanel(e);
    assert.match(html, /<h1>Diana<span class="hero-rol">Jungla<\/span><\/h1>/);
    assert.match(html, /Clasificatoria solo\/dúo · Pantalla de carga/);
    assert.match(html, /Cargando 245 de 270 consultas/);
    assert.match(html, /<span class="num">91%<\/span>/);
    assert.match(html, /Antes de empezar/);
    assert.match(html, /Tus reglas/);
    assert.equal((html.match(/class="fila (yo)?"/g) || []).length, 10);
  });

  test("en juego no sale el plan", () => {
    const e = copia();
    e.modo = "juego";
    const html = pintarPanel(e);
    assert.match(html, /· En partida/);
    assert.doesNotMatch(html, /Antes de empezar/);
    assert.match(html, /<h2><span class="etiqueta-cab">Líneas<\/span>/);
  });

  test("partida ajena: sin reglas propias sale el botón de volver", () => {
    const e = copia();
    e.panel.recordatorios = [];
    assert.match(pintarPanel(e), /<button id="volver">Volver a mis partidas<\/button>/);
  });

  test("estado de la carga", () => {
    assert.deepEqual(estadoCarga({ progreso: { hechas: 5, total: 10 } }, { espera: 3.2 }), {
      cargando: true,
      txt: "Cargando 5 de 10 consultas · Riot deja seguir en 4 s",
      ancho: 50,
    });
    assert.deepEqual(estadoCarga({ progreso: { hechas: 0, total: 0 } }, { espera: 0 }), { cargando: false, txt: "Datos completos", ancho: 0 });
  });

  test("una fila escapa nombre, etiqueta y campeón", () => {
    const f = copia().panel.equipos.aliado[0];
    Object.assign(f, { nombre: MALO, tag: MALO, campeon: MALO });
    const html = fila(f);
    sinImgMala(html);
    assert.ok(textoDe(html).includes(MALO));
  });

  test("mapa del jungla: el minuto que no existe pasa al 3 o al primero", () => {
    const j = { campeon: "Talon", mapa: { 2: [[0, 0]], 3: [[1, 1], [2, 2]], 10: [] } };
    estado.minutoMapa = "7";
    let html = mapaJungla(j);
    assert.equal(estado.minutoMapa, "3");
    assert.match(html, /<button class="activa" data-minuto="3">3:00<\/button>/);
    assert.match(html, /al minuto 3 en 2 partidas/);
    // Los minutos van en orden numérico, no de texto.
    assert.ok(html.indexOf('data-minuto="2"') < html.indexOf('data-minuto="10"'));
    estado.minutoMapa = "9";
    html = mapaJungla({ campeon: "Talon", mapa: { 5: [[0, 0]], 6: [] } });
    assert.equal(estado.minutoMapa, "5");
  });
});

describe("selección de campeón", () => {
  const seleccion = () => ({
    historial: copia().panel.historial,
    mio: { nombre: "Diana", icono: "/ddragon/campeon/Diana.png" },
    pos: "Jungla",
    pool: null,
    duelo: null,
    notas: [],
  });

  test("con tu campeón y su historial", () => {
    const html = pintarSeleccion(seleccion());
    assert.match(html, /<h1>Diana<\/h1>/);
    assert.match(html, /36V 23D<\/span> con Diana esta temporada/);
    assert.match(html, /Tu pool<\/span><\/h2><p class="vacio">Cuando el rival elija a alguien de Jungla/);
    assert.match(html, /Tu duelo de Jungla sale cuando el rival elija/);
  });

  test("sin campeón elegido", () => {
    const s = seleccion();
    s.mio = null;
    s.historial.vs = [];
    const html = pintarSeleccion(s);
    assert.match(html, /Aún no has elegido/);
    assert.match(html, /El rival aún no ha elegido\./);
  });

  test("pool contra el rival", () => {
    const pool = {
      rival: "Talon",
      pos: "Jungla",
      filas: [
        { nombre: "Diana", icono: "", wr: 55, v: 11, n: 20, yo_n: 3, yo_v: 2, vs_n: 0, vs_v: 0 },
        { nombre: MALO, icono: "", wr: null, n: 3, v: 1, yo_n: 0, vs_n: 1, vs_v: 1 },
      ],
    };
    const html = cajaPool(pool, "Jungla");
    assert.match(html, /<span class="num bien">55%<\/span>/);
    assert.match(html, /3 partidas, pocas/);
    sinImgMala(html);
    assert.match(cajaPool({ ...pool, filas: [] }), /No tienes campeones de Jungla con 5 partidas o más/);
    assert.equal(cajaPool(null, ""), "");
  });
});

describe("espera", () => {
  test("con el cliente abierto y descargando el historial", () => {
    const html = pintarEspera({ fase: "Lobby", fase_txt: "En el lobby", sync: { hechas: 40, total: 138 }, overlay: { activo: true, atajo: "ctrl+tab", aviso: MALO } });
    assert.match(html, /<h1>En el lobby<\/h1><p>En cuanto entres en partida/);
    assert.match(html, /40 de 138/);
    assert.match(html, /Mantén <kbd>CTRL<\/kbd><kbd>TAB<\/kbd> para verlo/);
    sinImgMala(html);
  });

  test("con el cliente cerrado y el overlay apagado", () => {
    const html = pintarEspera({ fase: null, fase_txt: "Cliente cerrado", sync: { hechas: 0, total: 0 }, overlay: { activo: false } });
    assert.match(html, /Abre el cliente del LoL/);
    assert.doesNotMatch(html, /pasos|sync|aviso-ventana/);
  });
});

describe("overlay", () => {
  test("esperando la partida", () => {
    const html = pintarOverlay({ panel: null });
    assert.match(html, /<svg width="18" height="18" viewBox="0 0 32 32"/);
    assert.match(html, /Esperando la partida…/);
  });

  test("pantalla de carga: plan y dos avisos", () => {
    const e = copia();
    const html = pintarOverlay(e);
    assert.match(html, /<span class="titulo">Pantalla de carga<\/span>/);
    assert.match(html, /En partida, mantén <kbd>CTRL<\/kbd><kbd>TAB<\/kbd>/);
    assert.match(html, /<ol class="limpia plan">/);
    assert.equal((html.match(/<div class="aviso ojo">/g) || []).length, 2);
    assert.equal((html.match(/class="ov-fila /g) || []).length, 10);
  });

  test("en juego: sin plan ni duelo, y las notas restan avisos", () => {
    const e = copia();
    e.modo = "juego";
    e.panel.duelo = { a: "Diana", b: "Talon", pos: "Jungla", n: 0, poco: true };
    e.panel.notas = [{ campeon: MALO, texto: MALO, rival: true }];
    const html = pintarOverlay(e);
    assert.match(html, /Suelta <kbd>/);
    assert.doesNotMatch(html, /plan|caja duelo|con-duelo/);
    assert.equal((html.match(/<div class="aviso">/g) || []).length, 2);
    sinImgMala(html);
  });
});

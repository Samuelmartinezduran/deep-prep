// Revisiones: lo de hoy, filtros del mapa de muertes, línea de tiempo y detalle de una partida.
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { estado } from "../../deepprep/web/js/estado.js";
import { detalleRevision, filtrar, lineaTiempo, mapaMuertes, resumenHoy, tablaTendencia } from "../../deepprep/web/js/revisiones.js";
import { atributos } from "./ayuda.mjs";

const hora = (d, h, m = 0) => new Date(2026, 9, d, h, m).getTime(); // octubre de 2026, hora local

describe("lo de hoy", () => {
  const lista = [
    { fecha: hora(12, 22), gana: true, lp: 18 },
    { fecha: hora(12, 7), gana: false, lp: -19 },
    { fecha: hora(12, 5, 59), gana: true, lp: null },
    { fecha: hora(11, 23), gana: true, lp: 20 },
  ];

  test("cuenta desde las 6:00", () => {
    const html = resumenHoy(lista, new Date(2026, 9, 12, 23, 0));
    assert.match(html, /<span class="num grande-m">1V 1D<\/span>/);
    assert.match(html, /<span class="num lp grande-m mal">−1 LP<\/span>/);
    // La más reciente a la derecha.
    assert.match(html, /<span class="res mal">D<\/span><span class="res bien">V<\/span><\/span>/);
  });

  test("de madrugada sigue contando el día anterior", () => {
    const html = resumenHoy(lista, new Date(2026, 9, 13, 3, 0));
    assert.match(html, /1V 1D/);
    assert.equal(resumenHoy(lista, new Date(2026, 9, 14, 12, 0)), "");
  });

  test("sin LP no sale la cifra de LP", () => {
    const html = resumenHoy([{ fecha: hora(12, 8), gana: true, lp: null }], new Date(2026, 9, 12, 9, 0));
    assert.match(html, /1V 0D/);
    assert.doesNotMatch(html, /LP/);
  });
});

describe("mapa de muertes", () => {
  const muertes = [
    { id: "a", x: 0, y: 0, ms: 5 * 60000, gana: true, campeon: "Diana", t: "5:00", asesino: "Yi" },
    { id: "b", x: 0, y: 0, ms: 15 * 60000, gana: false, campeon: "Diana", t: "15:00", asesino: "Yi" },
    { id: "c", x: 0, y: 0, ms: 20 * 60000, gana: true, campeon: "Diana", t: "20:00", asesino: "Yi" },
  ];
  const ids = (l) => l.map((m) => m.id).join("");

  test("filtros", () => {
    assert.equal(ids(filtrar(muertes, "todas")), "abc");
    assert.equal(ids(filtrar(muertes, "antes")), "a");
    assert.equal(ids(filtrar(muertes, "despues")), "bc");
    assert.equal(ids(filtrar(muertes, "derrotas")), "b");
  });

  test("pinta el filtro del estado y enlaza cada punto con su revisión", () => {
    estado.filtroMuertes = "despues";
    const html = mapaMuertes(muertes);
    assert.match(html, /<button class="activa" data-filtro="despues">15\+ min<\/button>/);
    assert.deepEqual(atributos(html, "data-revision"), ["b", "c"]);
    assert.match(html, /<span class="num">2<\/span> muertes\./);
    estado.filtroMuertes = "todas";
  });
});

describe("revisión de una partida", () => {
  const r = {
    duracion: "30:00",
    fecha: hora(12, 10),
    gana: false,
    campeon: "Diana",
    icono: "",
    kda: [4, 8, 6],
    cs_min: 7.8,
    kp: 31,
    dano_pct: 13,
    vision: 33,
    wards: 4,
    control: 2,
    lp: { nivel: "emerald", rank: "I", lp: 53, cambio: -19 },
    carpeta: "C:\\Videos\\x",
    objetivos: [
      { t: "6:41", nombre: "Dragón", tuyo: true, participaste: true },
      { t: "15:00", nombre: "Barón", tuyo: false },
    ],
    muertes: [
      { t: "9:45", asesino: "Maestro Yi", ayudas: ["Volibear"], donde: "en top", rivales: 2, perdido: "", clip: "x.mp4" },
      { t: "45:00", asesino: "Yi", ayudas: [], donde: "en mid", rivales: 1, perdido: "Barón", video: { archivo: "r.mkv", en: "4:59" } },
    ],
    comparacion: { rival: "Talon", minutos: { 10: { oro: [3000, 3200], cs: [60, 50], xp: [4000, 4000], nivel: [7, 6] } } },
    prevision: [{ tema: "Gank", acierto: true, dijo: "top", paso: "top" }],
  };

  test("línea de tiempo: posiciones, marcas cada 5 minutos y nada fuera del 100 %", () => {
    const html = lineaTiempo(r);
    assert.match(html, /class="lt-obj aliado" style="left:22\.28%"/);
    assert.match(html, /class="lt-muerte cara" style="left:100\.00%"/);
    assert.equal((html.match(/class="lt-marca"/g) || []).length, 7);
    assert.match(html, /2 objetivos y 2 muertes/);
  });

  test("detalle", () => {
    const html = detalleRevision(r);
    assert.match(html, /<span class="resultado mal">Derrota<\/span>/);
    assert.match(html, /Esmeralda I · 53 LP · <span class="num lp mal">−19 LP<\/span>/);
    assert.match(html, /<button class="con-icono clip" data-clip="0">/);
    assert.match(html, /r\.mkv · 4:59/);
    assert.match(html, /<div class="etiqueta-cab">Min 10<\/div><div class="num"><span class="mal">−200<\/span>/);
    assert.match(html, /4<span class='suave'> \/ <\/span>8/);
    assert.match(html, /<span class="suave">tu equipo, contigo<\/span>/);
    assert.match(html, /id="abrir-carpeta"/);
    assert.match(html, /<span class="veredicto bien">Acertó<\/span>/);
  });

  test("sin revisión elegida y sin datos", () => {
    assert.match(detalleRevision(null), /Elige una partida de la lista\./);
    const vacia = { ...r, muertes: [], objetivos: [], comparacion: null, prevision: [], carpeta: "", lp: null };
    const html = detalleRevision(vacia);
    assert.match(html, /No moriste ni una vez\./);
    assert.match(html, /Nadie hizo objetivos épicos\./);
    assert.match(html, /Sin jungla rival con el que comparar\./);
    assert.doesNotMatch(html, /abrir-carpeta/);
  });

  test("tendencias", () => {
    assert.equal(tablaTendencia("Hora", []), "");
    const html = tablaTendencia("Hora", [{ nombre: "Tarde", v: 14, n: 24 }]);
    assert.match(html, /<span class="num bien">58%<\/span><span class="num suave">24<\/span>/);
  });
});

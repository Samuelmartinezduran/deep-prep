// Tooltip: el texto va como JSON en data-tip y se pinta con nodos, nunca con innerHTML.
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { estado } from "../../deepprep/web/js/estado.js";
import { graficoGank } from "../../deepprep/web/js/piezas.js";
import { lineaTiempo, mapaMuertes, tablaTendencia } from "../../deepprep/web/js/revisiones.js";
import { leerTip, pintarTip, tip, tipLineas } from "../../deepprep/web/js/tooltip.js";
import { atributos, caja, documento, htmlDe } from "./ayuda.mjs";

const MALO = `<img src=x onerror="alert('xss')">`;

// Lo que acaba dentro del tooltip al pasar el ratón por el primer data-tip de un trozo de HTML.
function pasarRaton(html, i = 0) {
  const doc = documento();
  const tipCaja = caja();
  pintarTip(tipCaja, atributos(html, "data-tip")[i], doc);
  return { html: htmlDe(tipCaja), texto: tipCaja.textContent, creados: doc.creados };
}

describe("atributo data-tip", () => {
  test("es JSON escapado: no corta el atributo ni mete etiquetas", () => {
    const attr = tip(["b", `Nombre "raro" & <cosas>`], " · 3 de 7");
    const valor = attr.slice('data-tip="'.length, -1);
    assert.ok(attr.startsWith('data-tip="') && attr.endsWith('"'));
    assert.doesNotMatch(valor, /[<>"]/);
    assert.deepEqual(JSON.parse(atributos(`<i ${attr}>`, "data-tip")[0]), [[["b", `Nombre "raro" & <cosas>`], " · 3 de 7"]]);
  });

  test("varias líneas", () => {
    const attr = tipLineas([["num", "9:45"], " · ", ["b", "Yi"]], ["en top"]);
    assert.deepEqual(JSON.parse(atributos(`<i ${attr}>`, "data-tip")[0]), [[["num", "9:45"], " · ", ["b", "Yi"]], ["en top"]]);
  });
});

describe("leerTip", () => {
  test("trozos con estilo y de texto", () => {
    assert.deepEqual(leerTip(JSON.stringify([[["b", "top"], " · 4 de 7"], [["num", 3]]])), [
      [{ etiqueta: "b", clase: "", texto: "top" }, { texto: " · 4 de 7" }],
      [{ etiqueta: "span", clase: "num", texto: "3" }],
    ]);
  });

  test("lo que no es el JSON esperado sale como texto, sin interpretar", () => {
    assert.deepEqual(leerTip(`<b>hola</b>`), [[{ texto: "<b>hola</b>" }]]);
    assert.deepEqual(leerTip(`{"a": 1}`), [[{ texto: `{"a": 1}` }]]);
    assert.deepEqual(leerTip(undefined), [[{ texto: "" }]]);
  });

  test("un estilo desconocido no crea etiquetas", () => {
    assert.deepEqual(leerTip(JSON.stringify([[["script", "x"], ["img", "y"]]])), [[{ texto: "script,x" }, { texto: "img,y" }]]);
  });
});

describe("pintarTip", () => {
  test("pinta lo mismo que el HTML de antes con nodos", () => {
    const { html } = pasarRaton(`<i ${tipLineas([["num", "9:45"], " · muerte ante ", ["b", "Maestro Yi"]], ["en top"], ["Dragón"])}>`);
    assert.equal(html, `<span class="num">9:45</span> · muerte ante <b>Maestro Yi</b><br>en top<br>Dragón`);
  });

  test("solo crea <b>, <span> y <br>, y nunca usa innerHTML", () => {
    const { creados } = pasarRaton(`<i ${tipLineas([["b", MALO], MALO], [["num", MALO]])}>`);
    assert.deepEqual(creados, ["B", "BR", "SPAN"]);
  });
});

// La prueba del fallo: un nombre con HTML en cada gráfico con tooltip sale como texto, sin crear etiquetas.
describe("el tooltip ya no mete HTML", () => {
  const comprobar = (html, i = 0) => {
    const r = pasarRaton(html, i);
    assert.ok(r.texto.includes(MALO), `el nombre sale tal cual: ${r.texto}`);
    assert.ok(!r.creados.includes("IMG"), "no se crea ninguna imagen");
    assert.ok(r.html.includes("&lt;img src=x"), r.html);
    assert.ok(r.creados.every((e) => ["B", "SPAN", "BR"].includes(e)), r.creados.join());
  };

  test("tendencias", () => comprobar(tablaTendencia("Sesión", [{ nombre: MALO, v: 3, n: 5 }])));

  test("mapa de muertes", () => {
    estado.filtroMuertes = "todas";
    comprobar(mapaMuertes([{ id: "EUW1_1", x: 100, y: 200, ms: 1000, gana: false, campeon: MALO, t: "1:00", asesino: MALO }]));
  });

  test("línea de tiempo: objetivos y muertes", () => {
    const r = {
      duracion: "30:00",
      objetivos: [{ t: "6:41", nombre: MALO, tuyo: true, participaste: false }],
      muertes: [{ t: "9:45", asesino: MALO, donde: MALO, perdido: MALO }],
    };
    const html = lineaTiempo(r);
    comprobar(html, 0);
    comprobar(html, 1);
    assert.equal(pasarRaton(html, 0).html, `<span class="num">6:41</span> · <b>${MALO.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</b><br>tu equipo, sin ti`);
  });

  test("gráfico del primer gank", () => {
    const html = graficoGank("min 4:33 · top 4 · mid 1 · bot 2");
    assert.equal(pasarRaton(html).html, "<b>top</b> · 4 de 7");
    assert.equal(atributos(html, "data-tip").length, 3);
  });
});

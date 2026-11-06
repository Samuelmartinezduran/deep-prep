// La barra del modo demo como texto (y lo poco que toca de la página).
import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";

import { elegirEscena, ESCENAS, escenaActual, htmlDemo, pintarDemo } from "../../deepprep/web/js/demo.js";
import { estado } from "../../deepprep/web/js/estado.js";
import { atributos, textoDe } from "./ayuda.mjs";

const activas = (html) => [...html.matchAll(/<button class="activa" data-escena="([a-z]+)" aria-pressed="true">/g)].map((m) => m[1]);

// Una página de mentira con lo que usa la barra: la caja #demo y la explicación #demo-txt.
let caja, explicacion;
const fetchOriginal = globalThis.fetch;
const pedidas = [];
beforeEach(() => {
  caja = { dataset: {}, innerHTML: "" };
  explicacion = { textContent: "" };
  globalThis.document = { getElementById: (id) => ({ demo: caja, "demo-txt": explicacion })[id] || null };
  estado.vista = "partida";
  estado.actual = null;
});
afterEach(() => {
  delete globalThis.document;
  globalThis.fetch = fetchOriginal;
  pedidas.length = 0;
});
function simular(respuesta) {
  globalThis.fetch = async (ruta, opciones) => {
    pedidas.push({ ruta, cuerpo: JSON.parse(opciones.body) });
    return new Response(JSON.stringify(respuesta), { status: 200, headers: { "Content-Type": "application/json" } });
  };
}

describe("barra del modo demo", () => {
  test("las cinco escenas, en el orden de una partida, cada una con su explicación", () => {
    assert.deepEqual(
      ESCENAS.map((e) => [e.id, e.vista]),
      [
        ["seleccion", "partida"],
        ["carga", "partida"],
        ["juego", "partida"],
        ["revisiones", "revisiones"],
        ["ajustes", "ajustes"],
      ]
    );
    for (const e of ESCENAS) assert.ok(e.nombre && e.txt.length > 40, e.id);
  });

  test("en Partida manda la escena de la app; en las otras pestañas, la pestaña", () => {
    assert.equal(escenaActual({ escena: "juego" }, "partida"), "juego");
    assert.equal(escenaActual({ escena: "juego" }, "revisiones"), "revisiones");
    assert.equal(escenaActual({ escena: "carga" }, "ajustes"), "ajustes");
  });

  test("una sola escena activa, con su explicación", () => {
    for (const e of ESCENAS) {
      const html = e.vista === "partida" ? htmlDemo({ escena: e.id }, "partida") : htmlDemo({ escena: "carga" }, e.vista);
      assert.deepEqual(activas(html), [e.id]);
      assert.deepEqual(atributos(html, "data-escena"), ESCENAS.map((x) => x.id));
      assert.equal((html.match(/aria-pressed="true"/g) || []).length, 1);
      assert.ok(textoDe(html).includes(e.txt), e.id);
      assert.match(html, /Modo demo/);
    }
  });

  test("el enlace al overlay solo en la pantalla de carga y en partida", () => {
    for (const e of ESCENAS) {
      const html = e.vista === "partida" ? htmlDemo({ escena: e.id }, "partida") : htmlDemo({ escena: "carga" }, e.vista);
      const enlaces = atributos(html, "href");
      assert.deepEqual(enlaces, ["carga", "juego"].includes(e.id) ? ["/?vista=overlay"] : [], e.id);
    }
  });

  test("una escena que no conoce no rompe la barra", () => {
    const html = htmlDemo({ escena: "<b>rara</b>" }, "partida");
    assert.deepEqual(activas(html), ["seleccion"]);
    assert.doesNotMatch(html, /<b>rara/);
  });

  test("se pinta solo si cambia lo que se ve y se quita fuera de la demo", () => {
    pintarDemo({ demo: { escena: "carga" } });
    assert.deepEqual(activas(caja.innerHTML), ["carga"]);
    caja.innerHTML = "sin tocar";
    pintarDemo({ demo: { escena: "carga" } });
    assert.equal(caja.innerHTML, "sin tocar");
    estado.vista = "revisiones";
    pintarDemo({ demo: { escena: "carga" } });
    assert.deepEqual(activas(caja.innerHTML), ["revisiones"]);
    pintarDemo({ fase: null });
    assert.equal(caja.innerHTML, "");
    pintarDemo(null);
    assert.equal(caja.innerHTML, "");
  });

  test("las escenas de la partida se piden a la app; las pestañas, no", async () => {
    estado.actual = { demo: { escena: "carga" } };
    simular({ ok: true });
    assert.equal(await elegirEscena("juego"), "partida");
    assert.deepEqual(pedidas, [{ ruta: "/api/demo", cuerpo: { escena: "juego" } }]);
    assert.equal(estado.actual.demo.escena, "juego"); // la barra cambia ya, sin esperar al siguiente estado
    assert.equal(await elegirEscena("revisiones"), "revisiones");
    assert.equal(await elegirEscena("ajustes"), "ajustes");
    assert.equal(await elegirEscena("otra"), null);
    assert.equal(pedidas.length, 1);
  });

  test("si la app dice que no, el error sale en la barra y no se cambia de pestaña", async () => {
    estado.actual = { demo: { escena: "carga" } };
    simular({ ok: false, error: "Esa escena no existe." });
    assert.equal(await elegirEscena("seleccion"), null);
    assert.equal(explicacion.textContent, "Esa escena no existe.");
    assert.equal(estado.actual.demo.escena, "carga");
  });
});

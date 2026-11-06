// Llamadas a la app: los fallos de red, los errores HTTP y las respuestas raras no se pierden.
import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";

import { enviar, ErrorApi, pedir, pedirTexto, RESPUESTA_RARA, SIN_CONEXION } from "../../deepprep/web/js/api.js";

const fetchOriginal = globalThis.fetch;
const pedidas = [];
// fetch de mentira: cada llamada devuelve lo que diga `respuesta` (una Response, o un error que lanzar).
function simular(respuesta) {
  globalThis.fetch = async (ruta, opciones) => {
    pedidas.push({ ruta, opciones });
    if (respuesta instanceof Error) throw respuesta;
    return respuesta;
  };
}
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  globalThis.fetch = fetchOriginal;
  pedidas.length = 0;
});

describe("enviar", () => {
  test("manda JSON por POST y devuelve la respuesta de la app", async () => {
    simular(json({ ok: false, error: "No encuentro esa cuenta." }));
    assert.deepEqual(await enviar("/api/buscar", { riot_id: "x#y" }), { ok: false, error: "No encuentro esa cuenta." });
    assert.equal(pedidas[0].ruta, "/api/buscar");
    assert.equal(pedidas[0].opciones.method, "POST");
    assert.equal(pedidas[0].opciones.body, '{"riot_id":"x#y"}');
    assert.equal(pedidas[0].opciones.headers["Content-Type"], "application/json");
  });

  test("sin cuerpo manda un objeto vacío", async () => {
    simular(json({ ok: true }));
    assert.deepEqual(await enviar("/api/volver"), { ok: true });
    assert.equal(pedidas[0].opciones.body, "{}");
  });

  test("sin conexión: {ok: false} con el aviso de siempre", async () => {
    simular(new TypeError("Failed to fetch"));
    assert.deepEqual(await enviar("/api/clip", { id: "x", i: 0 }), { ok: false, error: SIN_CONEXION });
  });

  test("error HTTP con el texto de la app", async () => {
    simular(json({ error: "origen no permitido" }, 403));
    assert.deepEqual(await enviar("/api/clave", {}), { ok: false, error: "origen no permitido" });
  });

  test("error HTTP sin JSON: el código", async () => {
    simular(new Response("<html>fallo</html>", { status: 500 }));
    assert.deepEqual(await enviar("/api/ajustes", {}), { ok: false, error: "La app ha respondido con un error (500)" });
  });

  test("respuesta 200 que no es JSON, o que no es un objeto", async () => {
    simular(new Response("hola", { status: 200 }));
    assert.deepEqual(await enviar("/api/salir"), { ok: false, error: RESPUESTA_RARA });
    simular(new Response("null", { status: 200 }));
    assert.deepEqual(await enviar("/api/salir"), { ok: false, error: RESPUESTA_RARA });
  });
});

describe("pedir y pedirTexto", () => {
  test("devuelven el cuerpo", async () => {
    simular(json({ lista: [] }));
    assert.deepEqual(await pedir("/api/revisiones"), { lista: [] });
    simular(new Response('{"fase": null}'));
    assert.equal(await pedirTexto("/api/estado"), '{"fase": null}');
  });

  test("lanzan ErrorApi con un texto para el jugador", async () => {
    simular(new TypeError("Failed to fetch"));
    await assert.rejects(pedir("/api/ajustes"), (e) => e instanceof ErrorApi && e.message === SIN_CONEXION);
    simular(json({ error: "no existe" }, 404));
    await assert.rejects(pedirTexto("/api/estado"), (e) => e instanceof ErrorApi && e.message === "no existe");
    simular(new Response("{roto", { status: 200 }));
    await assert.rejects(pedir("/api/revisiones"), (e) => e instanceof ErrorApi && e.message === RESPUESTA_RARA);
  });
});

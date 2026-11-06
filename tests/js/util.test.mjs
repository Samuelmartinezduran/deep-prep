// Utilidades sin estado: escapar y formatos.
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { claseWr, coma, enMapa, esc, ligaTxt, miles, minutos, numero, pct } from "../../deepprep/web/js/util.js";

describe("esc", () => {
  test("escapa los cinco caracteres de HTML", () => {
    assert.equal(esc(`<a href="x" title='y'>&</a>`), "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;");
  });

  test("null y undefined son texto vacío; los números, texto", () => {
    assert.equal(esc(null), "");
    assert.equal(esc(undefined), "");
    assert.equal(esc(0), "0");
    assert.equal(esc("Año · ñ"), "Año · ñ");
  });
});

describe("cifras", () => {
  test("pct redondea y no divide entre cero", () => {
    assert.equal(pct(1, 3), 33);
    assert.equal(pct(2, 3), 67);
    assert.equal(pct(5, 0), 0);
  });

  test("miles", () => {
    assert.equal(miles(999), "999");
    assert.equal(miles(1499), "1k");
    assert.equal(miles(2857696), "2858k");
  });

  test("coma: un decimal con coma", () => {
    assert.equal(coma(8.733), "8,7");
    assert.equal(coma(7), "7,0");
  });

  test("claseWr: color solo con 5 partidas o más", () => {
    assert.equal(claseWr(4, 4), "");
    assert.equal(claseWr(3, 5), "bien");
    assert.equal(claseWr(2, 5), "mal");
    assert.equal(claseWr(5, 10), "");
    assert.equal(claseWr(58, 100), "bien");
    assert.equal(claseWr(42, 100), "mal");
  });

  test("minutos de un tiempo m:ss", () => {
    assert.equal(minutos("29:30"), 29.5);
    assert.equal(minutos(""), 0);
    assert.equal(minutos(undefined), 0);
  });

  test("numero lee las cifras formateadas por la app", () => {
    assert.equal(numero("−150"), -150);
    assert.equal(numero("+210"), 210);
    assert.equal(numero("6,8"), 6.8);
    assert.equal(numero("64%"), 64);
    assert.equal(numero("—"), 0); // sin cifra: 0, y la comparación no dibuja barras
  });

  test("enMapa: coordenadas del juego a porcentajes del minimapa", () => {
    assert.equal(enMapa(-120, -120), "left:0.00%;top:100.00%");
    assert.equal(enMapa(14870, 14980), "left:100.00%;top:0.00%");
  });

  test("ligaTxt: sin división en Maestro y por encima", () => {
    assert.equal(ligaTxt({ nivel: "emerald", rank: "I", lp: 53 }), "Esmeralda I · 53 LP");
    assert.equal(ligaTxt({ nivel: "master", rank: "I", lp: 120 }), "Maestro · 120 LP");
  });
});

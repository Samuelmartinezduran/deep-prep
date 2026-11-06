// Los módulos del panel: los sirve el servidor (nombres de su lista blanca), se cargan desde index.html y
// se pueden importar sin navegador (nada toca la página al cargarse, salvo main.js).
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { describe, test } from "node:test";

const WEB = new URL("../../deepprep/web/", import.meta.url);
const JS = new URL("js/", WEB);
const modulos = readdirSync(JS).filter((n) => n.endsWith(".js"));
const fuente = (n) => readFileSync(new URL(n, JS), "utf8");

// La misma expresión que usa deepprep/servidor.py para los nombres que sirve.
const servidor = readFileSync(new URL("../../deepprep/servidor.py", import.meta.url), "utf8");
const NOMBRE_SEGURO = new RegExp(servidor.match(/NOMBRE_SEGURO = re\.compile\(r"([^"]+)"\)/)[1]);

describe("módulos", () => {
  test("hay módulos y todos tienen un nombre que sirve el servidor", () => {
    assert.ok(modulos.length > 10);
    for (const n of modulos) assert.match(n.slice(0, -3), NOMBRE_SEGURO, n);
  });

  test("cada import es otro módulo de la carpeta que existe", () => {
    for (const n of modulos) {
      for (const [, ruta] of fuente(n).matchAll(/^import .* from "([^"]+)";$/gm)) {
        assert.match(ruta, /^\.\/[A-Za-z0-9]+\.js$/, `${n}: ${ruta}`);
        assert.ok(existsSync(new URL(ruta, JS)), `${n}: no existe ${ruta}`);
      }
    }
  });

  test("index.html carga main.js como módulo y ya no app.js", () => {
    const html = readFileSync(new URL("index.html", WEB), "utf8");
    assert.match(html, /<script type="module" src="\/js\/main\.js"><\/script>/);
    assert.doesNotMatch(html, /app\.js/);
    assert.ok(!existsSync(new URL("app.js", WEB)));
  });

  test("se importan sin navegador", async () => {
    for (const n of modulos.filter((m) => m !== "main.js")) await import(new URL(n, JS));
  });

  test("ningún módulo pasa el texto de un atributo a innerHTML", () => {
    for (const n of modulos) assert.doesNotMatch(fuente(n), /innerHTML\s*=\s*[^;]*dataset/, n);
  });
});

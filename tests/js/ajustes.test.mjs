// Ajustes y novedades como texto.
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { filaNota, filaReferencia, htmlAjustes, leerFilas } from "../../deepprep/web/js/ajustes.js";
import { htmlNovedades } from "../../deepprep/web/js/novedades.js";
import { atributos } from "./ayuda.mjs";

const MALO = `"><img src=x onerror=alert(1)>`;

const ajustes = (extra = {}) => ({
  campeones: [
    { id: 131, nombre: "Diana" },
    { id: 91, nombre: "Talon" },
  ],
  notas: { 131: MALO },
  referencias: { 91: "Alguien#EUW", 7: "Otro#KR1" },
  referencias_partidas: { 91: 12, 7: 0 },
  opciones_comparar: { ganan: "Los que ganan", perfil: "Un perfil" },
  comparar_con: "ganan",
  overlay: true,
  atajo_overlay: "ctrl+tab",
  overlay_opacidad: 0.8,
  grabar: false,
  grabacion_codificador: "cpu",
  grabacion_max_gb: 50,
  siempre_en_marcha: true,
  cuentas: ["Yo#EUW", "Otra#EUW"],
  recordatorios: [],
  perfil_base: "",
  perfil_partidas: null,
  version: { version: "2.0.0", lista: false },
  ...extra,
});

describe("formulario de ajustes", () => {
  test("rellena cada campo con lo guardado", () => {
    const html = htmlAjustes(ajustes());
    assert.match(html, /<input type="checkbox" id="a-overlay" checked>/);
    assert.match(html, /<input type="checkbox" id="a-grabar" >/);
    assert.match(html, /id="a-opacidad" min="40" max="100" value="80"><span class="num" id="opacidad-valor">80%<\/span>/);
    assert.match(html, /<option value="cpu" selected>El procesador<\/option>/);
    assert.match(html, /<option value="ganan" selected>Los que ganan<\/option><option value="perfil" >/);
    assert.match(html, /<label id="caja-perfil" hidden>/);
    assert.match(html, />Yo#EUW\nOtra#EUW<\/textarea>/);
    assert.match(html, /12 partidas suyas con ese campeón/);
    // Un campeón que ya no está en la lista se queda con su id.
    assert.ok(atributos(html, "value").includes("7"));
    assert.match(html, /buscando sus partidas…/);
    assert.match(html, /Deep Prep 2\.0\.0<\/span>/);
  });

  test("los textos guardados no rompen los atributos", () => {
    const html = htmlAjustes(ajustes());
    assert.doesNotMatch(html, /<img src=x/);
    assert.ok(atributos(html, "value").includes(MALO));
  });

  test("perfil de referencia y versión nueva", () => {
    const html = htmlAjustes(ajustes({ comparar_con: "perfil", perfil_base: "Modelo#EUW", perfil_partidas: 37, version: { version: "2.0.0", lista: true, nueva: "2.0.1" } }));
    assert.match(html, /<label id="caja-perfil" >/);
    assert.match(html, /37 partidas suyas guardadas/);
    assert.match(html, /la 2\.0\.1 se instala sola/);
    assert.match(htmlAjustes(ajustes({ overlay_opacidad: undefined })), /value="94"/);
  });

  test("filas vacías para añadir", () => {
    assert.match(filaNota("", ""), /class="campeon-nota" value=""/);
    assert.match(filaReferencia("", "", ""), /class="rid-ref" value=""/);
    assert.doesNotMatch(filaReferencia("", "", ""), /estado-ref/);
  });

  test("leerFilas: por id del campeón, sin filas incompletas", () => {
    const campeones = [
      { id: 131, nombre: "Diana" },
      { id: 91, nombre: "Talon" },
    ];
    const filas = [
      [" diana ", "  Guarda la R  "],
      ["Talon", "   "],
      ["Nadie", "texto"],
      ["TALON", "Ward"],
    ];
    assert.deepEqual(leerFilas(filas, campeones), { 131: "Guarda la R", 91: "Ward" });
  });
});

describe("novedades", () => {
  test("párrafos y puntos", () => {
    const html = htmlNovedades({ version: "1.0.1", notas: "# Interfaz nueva\n- Tu pool\n* Mapa del jungla\n\n• Clips\nY más cosas" });
    assert.match(html, /<h2>Deep Prep 1\.0\.1<\/h2>/);
    assert.match(html, /<div class="nov-cuerpo"><p>Interfaz nueva<\/p><p>Y más cosas<\/p><ul><li>Tu pool<\/li><li>Mapa del jungla<\/li><li>Clips<\/li><\/ul><\/div>/);
  });

  test("sin puntos no hay lista, y el texto se escapa", () => {
    const html = htmlNovedades({ version: "<b>1</b>", notas: "<script>x</script>" });
    assert.doesNotMatch(html, /<ul>|<script>|<b>1/);
    assert.match(html, /<p>&lt;script&gt;x&lt;\/script&gt;<\/p>/);
  });
});

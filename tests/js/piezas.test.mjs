// Piezas de HTML compartidas: lo que pintan y que escapan lo que viene de la app.
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { cajaDuelo, tablaComparacion } from "../../deepprep/web/js/duelo.js";
import {
  barraWr,
  cajaNotas,
  diferencia,
  etapa,
  etiquetas,
  filasVs,
  graficoGank,
  lp,
  racha,
  rango,
  retrato,
  rol,
  tarjetas,
  teclas,
  titulo,
} from "../../deepprep/web/js/piezas.js";
import { atributos, textoDe } from "./ayuda.mjs";

const MALO = `<script>alert("x")</script>`;
const sinEtiquetas = (html) => assert.doesNotMatch(html, /<script/i);

describe("piezas", () => {
  test("retrato: imagen con la url escapada o hueco", () => {
    assert.equal(retrato("/ddragon/campeon/Diana.png"), `<img class="retrato" src="/ddragon/campeon/Diana.png" alt="">`);
    assert.equal(retrato("", "mini"), `<span class="mini"></span>`);
    assert.equal(atributos(retrato(`x" onerror="y`), "src")[0], `x" onerror="y`);
  });

  test("rol: icono de la posición o hueco", () => {
    assert.equal(rol("JUNGLE"), `<span class="rol" style="--icono:url('/img/rol/jungle.svg')" title="Jungla"></span>`);
    assert.equal(rol("NADA"), "<span></span>");
  });

  test("racha: la más reciente a la derecha", () => {
    assert.equal(racha([]), "");
    assert.equal(racha([true, false, false]), `<div class="racha" title="Últimas 3: 1V 2D, la más reciente a la derecha"><i class=""></i><i class=""></i><i class="v"></i></div>`);
  });

  test("barraWr", () => {
    assert.equal(barraWr(3, 4), `<span class="barra-wr" title="3 de 4"><i style="width:75%"></i></span>`);
  });

  test("rango: oculto, cargando, sin rango y con rango", () => {
    assert.equal(rango({ oculto: true }), `<div class="linea2">Perfil oculto</div>`);
    assert.equal(rango({ liga: null }), `<div class="cargando">…</div>`);
    assert.match(rango({ liga: { solo: null, flex: { txt: "Oro II" } } }), /Sin rango.*en solo\/dúo · Flex Oro II/s);
    const r = rango({ liga: { solo: { nivel: "master", txt: "Maestro", lp: 1557, v: 608, d: 550 }, flex: null } });
    assert.match(r, /\/img\/rango\/master\.svg/);
    assert.match(r, /1557 LP · <span class="">53%<\/span>/);
    assert.match(rango({ liga: { solo: { nivel: "gold", txt: "Oro", lp: 3, v: 1, d: 0 } } }, true), /3 LP<\/div>/);
  });

  test("etiquetas escapan texto, tono y detalle", () => {
    assert.equal(etiquetas([]), "");
    const html = etiquetas([{ t: MALO, tono: "fuerte", d: MALO }, { t: "b", tono: "", d: "" }], 1);
    sinEtiquetas(html);
    assert.equal(textoDe(html), MALO);
  });

  test("título con y sin subtítulo", () => {
    assert.equal(titulo("Jungla rival"), `<h2><span class="etiqueta-cab">Jungla rival</span></h2>`);
    assert.equal(titulo("A", "b"), `<h2><span class="etiqueta-cab">A</span><small>b</small></h2>`);
  });

  test("lp y diferencia con signo", () => {
    assert.equal(lp(19), `<span class="num lp bien">+19 LP</span>`);
    assert.equal(lp(-19), `<span class="num lp mal">−19 LP</span>`);
    assert.equal(lp(0), `<span class="num lp suave">±0 LP</span>`);
    assert.equal(diferencia(5, 8), `<span class="mal">−3</span>`);
    assert.equal(diferencia(8, 5, " g"), `<span class="bien">+3 g</span>`);
  });

  test("teclas del atajo", () => {
    assert.equal(teclas("ctrl + tab"), "<kbd>CTRL</kbd><kbd>TAB</kbd>");
    assert.equal(teclas(""), "");
    assert.equal(teclas(undefined), "");
    sinEtiquetas(teclas(MALO));
  });

  test("etapa de la partida", () => {
    assert.equal(etapa("juego", {}), "En partida");
    assert.equal(etapa("carga", {}), "Pantalla de carga");
    assert.equal(etapa("previa", {}), "En vivo");
    assert.equal(etapa("juego", { terminada: true }), "Partida terminada");
  });

  test("gráfico del gank: una barra por línea, o nada", () => {
    assert.equal(graficoGank("top 4"), "");
    assert.equal(graficoGank("sin datos"), "");
    const html = graficoGank("min 4:33 · top 4 · mid 1 · bot 2");
    assert.match(html, /aria-label="Primer gank por línea: top 4, mid 1, bot 2"/);
    assert.match(html, /<span>mid<\/span><span class="mb-pista"><i style="width:25%"><\/i>/);
  });

  test("tarjetas: el gráfico solo en la del gank y sin compacto", () => {
    const j = { tarjetas: [{ titulo: "Primer gank", valor: "top 4 · bot 3", detalle: "d", tono: "ojo" }, { titulo: MALO, valor: MALO, detalle: MALO, tono: "" }] };
    const html = tarjetas(j);
    assert.match(html, /mini-barras/);
    assert.doesNotMatch(tarjetas(j, true), /mini-barras|class="d"/);
    sinEtiquetas(html);
  });

  test("filasVs: con cruces y sin ellos", () => {
    const html = filasVs(
      [
        { nombre: "Talon", n: 7, v: 1, n_mio: 1, v_mio: 0, icono: "" },
        { nombre: MALO, n: 0, v: 0 },
      ],
      "Diana"
    );
    assert.match(html, /con Diana <b class="num">0V 1D<\/b>/);
    assert.match(html, /Sin cruces con &lt;script&gt;/);
  });

  test("cajaNotas", () => {
    assert.equal(cajaNotas([]), "");
    const html = cajaNotas([{ campeon: "Talon", texto: MALO, rival: true, icono: "" }]);
    assert.match(html, /<b class="rival-txt">Talon<\/b>/);
    sinEtiquetas(html);
  });
});

describe("duelo", () => {
  const tu = {
    n: 31,
    ref: "Los que ganan",
    n_ref: 120,
    filas: [
      { que: "Oro al 10", tu: "−150", ref: "+300", mejor: false },
      { que: "CS/min", tu: "6,8", ref: "7,4", mejor: true },
      { que: "Nada", tu: "—", ref: "—", mejor: null },
    ],
  };

  test("tablaComparacion: barras desde el centro si hay negativos", () => {
    const html = tablaComparacion(tu, "Tú: algo.");
    assert.match(html, /par-pista centro"><i class="tu" style="right:50%;width:25%"><\/i>/);
    assert.match(html, /par-pista centro"><i class="ref" style="left:50%;width:50%"><\/i>/);
    assert.match(html, /<span class="par-pista"><i class="tu" style="left:0;width:91\.\d+%"><\/i>/);
    assert.match(html, /<div class="par-val num ">—<\/div><span><\/span>/);
    assert.match(html, /Tú: algo\. Los que ganan: media de 120 partidas\./);
    assert.equal(tablaComparacion(null, ""), "");
    assert.equal(tablaComparacion({ filas: [] }, ""), "");
  });

  test("cajaDuelo con pocas partidas", () => {
    const d = { a: "Diana", b: "Talon", pos: "Jungla", n: 0, poco: true, en_pool: false, tu };
    const html = cajaDuelo(d);
    assert.match(html, /Diana en Jungla no está entre tus campeones más jugados/);
    assert.match(html, /comparativa/);
    assert.doesNotMatch(cajaDuelo(d, true), /comparativa/);
    assert.match(cajaDuelo({ ...d, en_pool: true }), /el recolector sigue buscando/);
    assert.equal(cajaDuelo(null), "");
  });

  test("cajaDuelo con datos: compacto deja dos datos y quita tablas y build", () => {
    const d = {
      a: "Diana",
      b: MALO,
      pos: "Jungla",
      n: 214,
      wr: 47,
      poco: false,
      datos: [1, 2, 3].map((i) => ({ texto: `dato ${i}`, detalle: `detalle ${i}` })),
      tu,
      build: { runa: "Electrocutar", secundaria: "Brujería", objeto: "Eco", minuto: "11:20", wr_objeto: 52, n_objeto: 160, maximiza: "" },
    };
    const html = cajaDuelo(d);
    assert.equal((html.match(/dato-duelo/g) || []).length, 3);
    assert.match(html, /Electrocutar \+ Brujería · Eco <span class="suave">\(min 11:20, gana 52% de 160\)<\/span><\/div>/);
    sinEtiquetas(html);
    const corto = cajaDuelo(d, true);
    assert.equal((corto.match(/dato-duelo/g) || []).length, 2);
    assert.doesNotMatch(corto, /build-duelo|comparativa|detalle 1/);
  });
});

"use strict";

// Una sola página para las dos ventanas: la principal y la que va encima del juego (?vista=overlay).
const OVERLAY = new URLSearchParams(location.search).get("vista") === "overlay";
const raiz = document.getElementById("app");
let ultimo = "";
let inicioPartida = 0;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v, n) => (n ? Math.round((100 * v) / n) : 0);
const miles = (n) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
const coma = (x) => x.toFixed(1).replace(".", ",");
// Verde o rojo solo con muestra suficiente; el color describe al jugador, no a ti.
const claseWr = (v, n) => (n < 5 ? "" : pct(v, n) >= 58 ? "bien" : pct(v, n) <= 42 ? "mal" : "");
const retrato = (url, clase = "retrato") => (url ? `<img class="${clase}" src="${esc(url)}" alt="">` : `<span class="${clase}"></span>`);
const ROLES = { TOP: "top", JUNGLE: "jungle", MIDDLE: "middle", BOTTOM: "bottom", UTILITY: "utility" };
const ROL_TXT = { TOP: "Top", JUNGLE: "Jungla", MIDDLE: "Mid", BOTTOM: "ADC", UTILITY: "Support" };
const rol = (r) => (ROLES[r] ? `<span class="rol" style="--icono:url('/img/rol/${ROLES[r]}.svg')" title="${esc(ROL_TXT[r] || r)}"></span>` : `<span></span>`);
const minutos = (t) => {
  const [m, s] = String(t || "0:0").split(":").map(Number);
  return (m || 0) + (s || 0) / 60;
};
// El logo es la Grieta en pequeño: líneas de top y bot, mid entre las dos bases, el río y tú en el centro.
// Es el mismo dibujo que el icono (herramientas/logo.py), sin el fondo.
const LOGO = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><defs><mask id="logo-hueco"><rect width="32" height="32" fill="#fff"/><circle cx="16" cy="16" r="3.4" fill="#000"/></mask></defs>
  <path d="M9 9 23 23" stroke="#8b7cf6" stroke-opacity=".4" stroke-width="1.4" stroke-linecap="round" mask="url(#logo-hueco)"/>
  <rect x="6.8" y="6.8" width="18.4" height="18.4" rx="2.5" stroke="#8b7cf6" stroke-width="1.8"/>
  <rect x="6" y="20.5" width="5.5" height="5.5" rx="2.5" fill="#8b7cf6"/><rect x="20.5" y="6" width="5.5" height="5.5" rx="2.5" fill="#8b7cf6"/>
  <path d="M8.75 23.25 23.25 8.75" stroke="#8b7cf6" stroke-width="1.8" mask="url(#logo-hueco)"/><circle cx="16" cy="16" r="2.4" fill="#8b7cf6"/></svg>`;
// Iconos de línea, trazo 1.5, retícula de 16.
const ICONO = {
  partida: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.75"/><circle cx="8" cy="8" r="2"/><path d="M8 .75v2.5M8 12.75v2.5M.75 8h2.5M12.75 8h2.5"/></svg>`,
  revisiones: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.75 3.25h10.5M2.75 8h10.5M2.75 12.75h6.5"/><path d="M11.5 11.25l1.25 1.5 2.25-3"/></svg>`,
  ajustes: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4h4.5M9.5 4H14M2 12h2.5M7.5 12H14"/><circle cx="8" cy="4" r="1.5"/><circle cx="6" cy="12" r="1.5"/></svg>`,
  buscar: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.75"/><path d="m10.5 10.5 3.75 3.75"/></svg>`,
  carpeta: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.75 4.25v8.5h12.5v-7H8L6.5 3.75H2.25z"/></svg>`,
  muerte: `<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7"/></svg>`,
  play: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.5v9l7-4.5z"/></svg>`,
};
// Minimapa de Data Dragon: cubre de (-120, -120) a (14870, 14980); el eje y de la imagen va hacia abajo.
const enMapa = (x, y) => `left:${(((x + 120) / 14990) * 100).toFixed(2)}%;top:${((1 - (y + 120) / 15100) * 100).toFixed(2)}%`;
let minutoMapa = "3"; // minuto del mapa del jungla rival
let filtroMuertes = "todas"; // mapa de tus muertes
let datosRevisiones = null;
let novedadesCerradas = false;
const TITULOS = { partida: "Partida", revisiones: "Revisiones", ajustes: "Ajustes" };

document.body.classList.toggle("overlay", OVERLAY);

// --- armazón fijo de la ventana principal: la barra lateral y la superior no se repintan ---
if (!OVERLAY) {
  raiz.innerHTML = `
    <div class="app">
      <aside class="barra">
        <div class="marca">${LOGO}<span>Porofesor</span></div>
        <nav class="pestanas" id="pestanas">
          <button data-vista="partida" class="activa">${ICONO.partida}<span>Partida</span></button>
          <button data-vista="revisiones">${ICONO.revisiones}<span>Revisiones</span></button>
          <button data-vista="ajustes">${ICONO.ajustes}<span>Ajustes</span></button>
        </nav>
        <button class="aviso-revision" id="revision-lista" hidden><span class="punto"></span><span>Revisión nueva lista</span></button>
        <span class="hueco"></span>
        <div class="aviso-version" id="aviso-version" hidden></div>
        <section class="estado">
          <div class="etiqueta-cab">Estado</div>
          <div class="chip" id="fase"></div>
          <div class="chip" id="grabacion" hidden></div>
          <div class="chip cuenta" id="cuenta" hidden></div>
          <div class="cuota" id="cuota" title="Consultas a Riot en los últimos 2 minutos"></div>
        </section>
      </aside>
      <div class="contenido">
        <header class="cab">
          <span class="titulo-vista" id="titulo-vista">Partida</span>
          <span class="hueco"></span>
          <span class="error-busqueda" id="error"></span>
          <form class="buscar" id="buscar">
            ${ICONO.buscar}
            <input type="text" id="rid" placeholder="Ver la partida de Nombre#TAG" autocomplete="off" spellcheck="false" aria-label="Ver la partida de un jugador">
            <button type="submit">Ver</button>
          </form>
        </header>
        <div id="banda"></div>
        <div id="novedades"></div>
        <main id="principal"></main>
      </div>
    </div>
    <div class="tip" id="tip" hidden></div>`;
} else {
  raiz.innerHTML = `<div id="principal"></div>`;
}
const $ = (id) => document.getElementById(id);
let vista = "partida";
let estadoActual = null;
let revisionVista = null; // id de la revisión abierta
let revisionAvisada = null; // última revisión que ya se ha visto

async function enviar(ruta, cuerpo) {
  const r = await fetch(ruta, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo || {}) });
  return r.json();
}

if (!OVERLAY) {
  $("buscar").addEventListener("submit", async (e) => {
    e.preventDefault();
    const rid = $("rid").value.trim();
    if (!rid) return;
    $("error").textContent = "Buscando…";
    const r = await enviar("/api/buscar", { riot_id: rid });
    $("error").textContent = r.ok ? "" : r.error;
    if (r.ok) {
      $("rid").value = "";
      if (vista !== "partida") cambiarVista("partida");
    }
    refrescar();
  });
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("button, [data-revision]");
    if (!b) return;
    if (b.id === "volver") {
      await enviar("/api/volver");
      refrescar();
    } else if (b.dataset.vista) {
      cambiarVista(b.dataset.vista);
    } else if (b.id === "revision-lista") {
      revisionAvisada = estadoActual && estadoActual.ultima_revision;
      revisionVista = revisionAvisada;
      cambiarVista("revisiones");
    } else if (b.dataset.revision) {
      revisionVista = b.dataset.revision;
      pintarRevisiones();
    } else if (b.id === "cerrar-novedades") {
      await enviar("/api/novedades");
      $("novedades").innerHTML = "";
      novedadesCerradas = true;
    } else if (b.dataset.minuto) {
      minutoMapa = b.dataset.minuto;
      const j = estadoActual && estadoActual.panel && estadoActual.panel.jungla;
      if (j) b.closest(".mapa-jungla").outerHTML = mapaJungla(j);
    } else if (b.dataset.filtro) {
      filtroMuertes = b.dataset.filtro;
      if (datosRevisiones) b.closest(".mapa-muertes").outerHTML = mapaMuertes(datosRevisiones.muertes);
    } else if (b.dataset.clip) {
      const r = await enviar("/api/clip", { id: revisionVista, i: Number(b.dataset.clip) });
      if (!r.ok) b.lastChild.textContent = r.error;
    } else if (b.id === "abrir-carpeta") {
      const r = await enviar("/api/carpeta", { id: revisionVista });
      if (!r.ok) b.lastChild.textContent = r.error;
    } else if (b.id === "salir-app") {
      const r = await enviar("/api/salir", {});
      $("ajustes-estado").textContent = r.ok ? "Cerrando…" : r.error;
    } else if (b.id === "guardar-ajustes") {
      guardarAjustes();
    } else if (b.id === "nueva-ref") {
      $("referencias").insertAdjacentHTML("beforeend", filaReferencia("", "", ""));
    } else if (b.id === "nueva-nota") {
      $("notas").insertAdjacentHTML("beforeend", filaNota("", ""));
    } else if (b.classList.contains("quitar-nota")) {
      b.closest(".nota-edit").remove();
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "a-comparar") $("caja-perfil").hidden = e.target.value !== "perfil";
    if (e.target.id === "a-opacidad") $("opacidad-valor").textContent = `${e.target.value}%`;
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "a-opacidad") $("opacidad-valor").textContent = `${e.target.value}%`;
  });
  document.addEventListener("submit", async (e) => {
    if (e.target.id !== "clave") return;
    e.preventDefault();
    const r = await enviar("/api/clave", { clave: $("clave-txt").value });
    if (!r.ok) $("clave-error").textContent = r.error;
    refrescar();
  });
  // Tooltip propio para los gráficos: sigue al ratón y no tapa la marca.
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest("[data-tip]");
    $("tip").hidden = !t;
    if (t) $("tip").innerHTML = t.dataset.tip;
  });
  document.addEventListener("mousemove", (e) => {
    const tip = $("tip");
    if (tip.hidden) return;
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    tip.style.transform = `translate(${x}px, ${e.clientY + 16}px)`;
  });
}

// --- piezas comunes ------------------------------------------------------------------------------
function racha(lista) {
  if (!lista || !lista.length) return "";
  // La más reciente a la derecha, como se lee una racha; victoria hacia arriba, derrota hacia abajo.
  const v = lista.filter(Boolean).length;
  return `<div class="racha" title="Últimas ${lista.length}: ${v}V ${lista.length - v}D, la más reciente a la derecha">${lista
    .slice()
    .reverse()
    .map((g) => `<i class="${g ? "v" : ""}"></i>`)
    .join("")}</div>`;
}

// Barra de porcentaje con la marca del 50 %. El color lo lleva la cifra, no la barra.
function barraWr(v, n) {
  const p = pct(v, n);
  return `<span class="barra-wr" title="${v} de ${n}"><i style="width:${p}%"></i></span>`;
}

function rango(f, compacto) {
  if (f.oculto) return `<div class="linea2">Perfil oculto</div>`;
  if (!f.liga) return `<div class="cargando">…</div>`;
  const s = f.liga.solo;
  const flex = f.liga.flex && !compacto ? ` · Flex ${esc(f.liga.flex.txt)}` : "";
  if (!s) return `<div class="rango"><img src="/img/rango/unranked.svg" alt=""><div><div class="txt">Sin rango</div><div class="linea2">en solo/dúo${flex}</div></div></div>`;
  const total = s.v + s.d;
  const detalle = compacto ? `${s.lp} LP` : `${s.lp} LP${total ? ` · <span class="${claseWr(s.v, total)}">${pct(s.v, total)}%</span>` : ""}`;
  return `<div class="rango"><img src="/img/rango/${esc(s.nivel)}.svg" alt="">
    <div style="min-width:0" title="${total ? `${s.v}V ${s.d}D en solo/dúo` : ""}"><div class="txt">${esc(s.txt)}</div><div class="linea2 num">${detalle}${flex}</div></div></div>`;
}

function etiquetas(lista, max) {
  const l = max ? lista.slice(0, max) : lista;
  return l.length ? `<div class="etiquetas">${l.map((e) => `<span class="etq ${esc(e.tono)}" title="${esc(e.d)}">${esc(e.t)}</span>`).join("")}</div>` : "";
}

const titulo = (txt, extra = "") => `<h2><span class="etiqueta-cab">${txt}</span>${extra ? `<small>${extra}</small>` : ""}</h2>`;

// --- ventana principal: partida ---------------------------------------------------------------------
function fila(f) {
  let forma = `<div class="cargando">${f.oculto ? "" : "cargando…"}</div>`;
  let conCampeon = "";
  if (f.muestra.n) {
    forma = `<div class="forma"><span class="num"><span class="${claseWr(f.muestra.v, f.muestra.n)}">${f.muestra.v}V</span> <span class="suave">${f.muestra.n - f.muestra.v}D</span></span>${racha(f.racha)}</div>`;
    const c = f.camp;
    const kda = c.kda ? `<div class="linea2 num">${c.kda.map(coma).join(" / ")}</div>` : "";
    conCampeon = c.n
      ? `<div><div class="num con-camp"><span class="${claseWr(c.v, c.n)}">${pct(c.v, c.n)}%</span> <span class="suave">${c.v}/${c.n}</span>${barraWr(c.v, c.n)}</div>${kda}</div>`
      : `<div class="linea2">Ninguna reciente</div>`;
  }
  const maestria = f.maestria == null ? "" : ` · ${miles(f.maestria)}`;
  const mains = f.mains.length ? `Más jugados: ${f.mains.map((m) => `${m.nombre} ${miles(m.puntos)}`).join(", ")}` : "";
  return `<div class="fila ${f.soy_yo ? "yo" : ""}">
      ${rol(f.rol)}
      ${retrato(f.icono)}
      <div style="min-width:0"><div class="nombre"><bdi>${esc(f.nombre)}</bdi>${f.tag ? `<span class="tag">#${esc(f.tag)}</span>` : ""}</div>
        <div class="linea2" title="${esc(mains)}">${esc(f.campeon)}${maestria}</div>${etiquetas(f.etiquetas)}</div>
      ${rango(f)}
      ${forma}
      ${conCampeon}
    </div>`;
}

function equipo(nombre, clase, filas) {
  return `<section class="equipo ${clase}">
      <div class="fila cabeza"><span></span><span></span><span class="equipo-nombre">${nombre}</span><span>Rango solo/dúo</span><span>Últimas partidas</span><span>Con su campeón</span></div>
      ${filas.map(fila).join("")}</section>`;
}

// "min 4:33 · top 4 · mid 1 · bot 2" -> barras por línea; si el texto no tiene ese formato, se deja tal cual.
function graficoGank(valor) {
  const lineas = [...String(valor).matchAll(/\b(top|mid|bot)\s+(\d+)/g)].map((m) => ({ l: m[1], n: Number(m[2]) }));
  if (lineas.length < 2) return "";
  const max = Math.max(...lineas.map((x) => x.n));
  const total = lineas.reduce((a, x) => a + x.n, 0);
  return `<div class="mini-barras" role="img" aria-label="Primer gank por línea: ${lineas.map((x) => `${x.l} ${x.n}`).join(", ")}">${lineas
    .map((x) => `<div class="mb-fila" data-tip="<b>${x.l}</b> · ${x.n} de ${total}"><span>${x.l}</span><span class="mb-pista"><i style="width:${(100 * x.n) / max}%"></i></span><span class="num">${x.n}</span></div>`)
    .join("")}</div>`;
}

function tarjetas(j, compacto) {
  return `<div class="tarjetas">${j.tarjetas
    .map((t) => {
      const grafico = !compacto && /gank/i.test(t.titulo) ? graficoGank(t.valor) : "";
      return `<div class="tarjeta ${esc(t.tono)}"><div class="etiqueta-cab">${esc(t.titulo)}</div><div class="v">${esc(t.valor)}</div>${grafico}${compacto ? "" : `<div class="d">${esc(t.detalle)}</div>`}</div>`;
    })
    .join("")}</div>`;
}

function cajaJungla(j) {
  if (!j) return `<section class="caja">${titulo("Jungla rival")}<p class="vacio">No identifico al jungla rival.</p></section>`;
  const nota = j.n
    ? `${j.n} partidas de jungla · ${j.n_campeon} con ${esc(j.campeon)} · ${j.n_lineas} líneas de tiempo${j.cargando ? " · cargando más" : ""}`
    : j.cargando
      ? "cargando sus partidas…"
      : "sin partidas de jungla recientes";
  const mapa = j.mapa && Object.keys(j.mapa).length ? mapaJungla(j) : "";
  return `<section class="caja jungla">${titulo("Jungla rival", "de sus partidas anteriores; posición una vez por minuto")}
      <div class="persona">${retrato(j.icono)}<div><div class="nombre grande">${esc(j.campeon)}</div><div class="linea2"><bdi>${esc(j.nombre)}</bdi> · ${nota}</div></div></div>
      <div class="${mapa ? "jungla-cuerpo" : ""}">${mapa}${tarjetas(j)}</div></section>`;
}

// Dónde estaba en sus partidas a cada minuto, llevado al lado del mapa que le toca hoy. Solo antes de jugar.
function mapaJungla(j) {
  const minutos = Object.keys(j.mapa).sort((a, b) => a - b);
  if (!j.mapa[minutoMapa]) minutoMapa = minutos.includes("3") ? "3" : minutos[0];
  const puntos = j.mapa[minutoMapa] || [];
  return `<div class="mapa-jungla">
      <div class="selector" role="group" aria-label="Minuto">${minutos
        .map((m) => `<button class="${m === minutoMapa ? "activa" : ""}" data-minuto="${m}">${m}:00</button>`)
        .join("")}</div>
      <div class="mapa" role="img" aria-label="Posición de ${esc(j.campeon)} al minuto ${minutoMapa} en ${puntos.length} partidas">
        ${puntos.map(([x, y]) => `<span class="punto-mapa rival" style="${enMapa(x, y)}"></span>`).join("")}
      </div>
      <div class="linea2 envuelve">Cada punto es una de sus ${puntos.length} partidas: dónde estaba al ${minutoMapa}:00, ya girado al lado en que juega hoy.</div>
    </div>`;
}

function cajaLineas(lineas, gank, modo) {
  const cuerpo = lineas.length
    ? lineas
        .map((l) => {
          const motivos = [...l.rival.map((m) => `<li>${esc(m)}</li>`), ...l.aliado.map((m) => `<li class="a">${esc(m)}</li>`)];
          const veredicto = l.veredicto ? `<span class="veredicto ${esc(l.tono)}">${esc(l.veredicto)}</span>` : "";
          return `<div class="linea"><div class="cab-linea"><b>${esc(l.linea)}</b>${veredicto}</div>
            ${motivos.length ? `<ul>${motivos.join("")}</ul>` : `<div class="linea2">Nada que destaque en sus últimas partidas.</div>`}</div>`;
        })
        .join("")
    : `<p class="vacio">Faltan datos de las líneas.</p>`;
  const pie = gank ? `<div class="pie">Su primer gank fue a <b>${esc(gank.linea)}</b> en ${gank.veces} de ${gank.n} partidas.</div>` : "";
  return `<section class="caja">${titulo(modo === "juego" ? "Líneas" : "Dónde va a haber errores", "rival en blanco, tu equipo en gris")}${cuerpo}${pie}</section>`;
}

function filasVs(vs, miCampeon) {
  const filas = vs
    .filter((f) => f.n)
    .map((f) => {
      const mio = f.n_mio ? `con ${esc(miCampeon)} <b class="num">${f.v_mio}V ${f.n_mio - f.v_mio}D</b>` : "";
      return `<div class="vs">${retrato(f.icono, "mini")}<span>${esc(f.nombre)}</span><span class="linea2">${mio}</span><span class="num"><span class="suave">total</span> <span class="${claseWr(f.v, f.n)}">${f.v}V ${f.n - f.v}D</span></span></div>`;
    })
    .join("");
  const sin = vs.filter((f) => !f.n).map((f) => esc(f.nombre));
  return filas + (sin.length ? `<div class="linea2 envuelve" style="margin-top:8px">Sin cruces con ${sin.join(", ")}.</div>` : "");
}

function cajaHistorial(h) {
  if (!h) return "";
  const alcance = h.alcance === "temporada" ? `tus ${h.n} clasificatorias${esc(h.cola_txt)} de la temporada` : `muestra de ${h.n} partidas`;
  if (!h.n) return `<section class="caja">${titulo("Tu historial")}<p class="vacio">Aún no hay partidas tuyas guardadas; se están descargando.</p></section>`;
  const c = h.campeon;
  const cab = c && c.n
    ? `<div class="cifra"><span class="num grande ${claseWr(c.v, c.n)}">${pct(c.v, c.n)}%</span><span class="linea2">con ${esc(h.mi_campeon)} · <span class="num">${c.v}V ${c.n - c.v}D</span></span></div>${racha(c.racha)}`
    : `<div class="linea2">Sin partidas con ${esc(h.mi_campeon)}.</div>`;
  const conocidos = h.conocidos.length
    ? `<div class="pie">${h.conocidos
        .map((k) => `Ya jugaste ${k.contigo ? "con" : "contra"} <b>${esc(k.nombre)}</b> ${k.dias ? `hace ${k.dias} d` : "hoy"} (${k.ganaste ? "ganaste" : "perdiste"})${k.veces > 1 ? `, ${k.veces} veces` : ""}.`)
        .join("<br>")}</div>`
    : "";
  return `<section class="caja">${titulo("Tu historial", alcance)}
      <div class="cabecera-historial">${cab}</div><div class="etiqueta-cab sub-cab">Contra estos campeones</div>${filasVs(h.vs, h.mi_campeon)}${conocidos}</section>`;
}

function estadoCarga(p, cuota) {
  const cargando = p.progreso.hechas < p.progreso.total;
  let txt = cargando ? `Cargando ${p.progreso.hechas} de ${p.progreso.total} consultas` : "Datos completos";
  if (cargando && cuota.espera > 1) txt += ` · Riot deja seguir en ${Math.ceil(cuota.espera)} s`;
  return { cargando, txt, ancho: p.progreso.total ? Math.round((100 * p.progreso.hechas) / p.progreso.total) : 0 };
}

function etapa(modo, p) {
  if (p.terminada) return "Partida terminada";
  return modo === "juego" ? "En partida" : modo === "carga" ? "Pantalla de carga" : "En vivo";
}

// --- tú contra tu referencia (la eliges en Ajustes) ---------------------------------------------------
// Barras emparejadas por fila, cada fila con su propia escala; tú en violeta, la referencia en gris.
const numero = (s) => Number(String(s).replace(/[^\d,.\-−+]/g, "").replace("−", "-").replace(",", "."));
function tablaComparacion(c, pie) {
  if (!c || !c.filas.length) return "";
  const clase = (m) => (m === true ? "bien" : m === false ? "mal" : "");
  const filas = c.filas
    .map((f) => {
      const a = numero(f.tu);
      const b = numero(f.ref);
      const barras = Number.isFinite(a) && Number.isFinite(b) && (a || b);
      const max = barras ? Math.max(Math.abs(a), Math.abs(b)) : 1;
      const signo = a < 0 || b < 0;
      const barra = (v, cl) => {
        const w = (50 * Math.abs(v)) / max;
        return signo
          ? `<span class="par-pista centro"><i class="${cl}" style="${v < 0 ? `right:50%` : `left:50%`};width:${w}%"></i></span>`
          : `<span class="par-pista"><i class="${cl}" style="left:0;width:${2 * w}%"></i></span>`;
      };
      return `<div class="par">
          <div class="par-que">${esc(f.que)}</div>
          <div class="par-val num ${clase(f.mejor)}">${esc(f.tu)}</div>${barras ? barra(a, "tu") : "<span></span>"}
          <div class="par-val num suave">${esc(f.ref)}</div>${barras ? barra(b, "ref") : "<span></span>"}
        </div>`;
    })
    .join("");
  return `<div class="comparativa">
      <div class="leyenda"><span><i class="tu"></i>Tú</span><span><i class="ref"></i>${esc(c.ref)}</span></div>
      ${filas}
      <div class="linea2 envuelve pie-tu">${pie} ${esc(c.ref)}: media de ${c.n_ref} partidas. Se cambia en Ajustes.</div>
    </div>`;
}

// --- tu duelo contra el rival directo (Master+), solo antes de empezar ---------------------------
function cajaDuelo(d, compacto) {
  if (!d) return "";
  const cab = `<div class="duelo-cab">
      <div class="duelista">${retrato(d.icono_a, "mini")}<b>${esc(d.a)}</b></div>
      <span class="vs-txt">vs</span>
      <div class="duelista">${retrato(d.icono_b, "mini")}<b class="rival-txt">${esc(d.b)}</b></div>
      ${d.poco ? "" : `<div class="duelo-wr"><span class="num">${d.wr}%</span><span class="linea2">gana ${esc(d.a)}</span></div>`}
    </div>`;
  const cabecera = titulo(`Tu duelo · ${esc(d.pos)}`, `${d.n} partidas de Master+`);
  if (d.poco) {
    const motivo = d.en_pool
      ? "Aún hay pocas partidas de este duelo; el recolector sigue buscando."
      : `${esc(d.a)} en ${esc(d.pos)} no está entre tus campeones más jugados, así que no se recogen sus partidas.`;
    const tuPoco = compacto ? "" : tablaComparacion(d.tu, `Tú: tus ${d.tu ? d.tu.n : 0} partidas con ${esc(d.a)} de ${esc(d.pos)}.`);
    return `<section class="caja duelo">${cabecera}${cab}<p class="vacio">${motivo}</p>${tuPoco}</section>`;
  }
  const datos = (compacto ? d.datos.slice(0, 2) : d.datos)
    .map((x) => `<li class="dato-duelo"><div>${esc(x.texto)}</div>${compacto ? "" : `<div class="linea2 envuelve">${esc(x.detalle)}</div>`}</li>`)
    .join("");
  const tu = compacto ? "" : tablaComparacion(d.tu, `Tú: tus ${d.tu ? d.tu.n : 0} partidas con ${esc(d.a)} de ${esc(d.pos)}, contra cualquiera.`);
  const b = d.build;
  const build = !compacto && b
    ? `<div class="build-duelo"><span class="etiqueta-cab">Lo más jugado</span><div>${esc(b.runa)} + ${esc(b.secundaria)} · ${esc(b.objeto)} <span class="suave">(min ${esc(b.minuto)}, gana ${b.wr_objeto}% de ${b.n_objeto})</span>${b.maximiza ? ` · ${esc(b.maximiza)}` : ""}</div></div>`
    : "";
  return `<section class="caja duelo">${cabecera}${cab}<ul class="limpia">${datos}</ul>${tu}${build}</section>`;
}

function pintarPanel(e) {
  const p = e.panel;
  const c = estadoCarga(p, e.cuota);
  const yo = p.yo || {};
  const miFila = p.equipos.aliado.find((f) => f.soy_yo);
  const bans = p.bans.length
    ? `<div class="dato dato-bans"><span class="etiqueta-cab">Baneos</span><span class="bans">${p.bans.map((b) => `<img src="${esc(b.icono)}" title="${esc(b.nombre)}" alt="${esc(b.nombre)}">`).join("")}</span></div>`
    : "";
  const carga = `<div class="dato"><span class="etiqueta-cab">${c.cargando ? `Datos · <span class="num">${c.ancho}%</span>` : "Datos"}</span>
      ${c.cargando ? `<span class="progreso"><i style="width:${c.ancho}%"></i></span>` : `<span class="listo"><span class="punto"></span>Completos</span>`}</div>`;
  // El plan es interpretación: solo antes de empezar a jugar (el servidor ya lo vacía en juego).
  const plan = e.modo !== "juego" && p.plan.length
    ? `<section class="caja">${titulo("Antes de empezar")}<ol class="limpia plan">${p.plan.map((x) => `<li>${esc(x)}</li>`).join("")}</ol></section>`
    : "";
  const avisos = p.avisos.length ? p.avisos.map((a) => `<div class="aviso ${esc(a.tono)}">${esc(a.texto)}</div>`).join("") : `<p class="vacio">${c.cargando ? "Esperando datos…" : "Nada que destacar."}</p>`;
  const reglas = p.recordatorios.length
    ? `<section class="caja">${titulo("Tus reglas")}${p.recordatorios.map((r) => `<div class="regla">${esc(r)}</div>`).join("")}</section>`
    : `<section class="caja ajena">${titulo("Partida ajena")}<p>Estás viendo la partida de otro jugador desde su punto de vista.</p><button id="volver">Volver a mis partidas</button></section>`;
  return `
    <section class="hero">
      ${miFila ? retrato(miFila.icono, "retrato hero-retrato") : ""}
      <div class="hero-txt">
        <div class="etiqueta-cab">${esc(p.cola)} · ${etapa(e.modo, p)}</div>
        <h1>${esc(yo.campeon || "Partida en vivo")}${miFila ? `<span class="hero-rol">${esc(ROL_TXT[miFila.rol] || "")}</span>` : ""}</h1>
        <div class="sub">${p.grieta ? "" : "Esta cola no es la Grieta del Invocador: jungla y líneas no aplican. "}${c.txt}</div>
      </div>
      <div class="derecha">${bans}${carga}<div class="dato"><span class="etiqueta-cab">Tiempo</span><span class="reloj" id="reloj">—</span></div></div>
    </section>
    <div class="cuerpo">
      <div class="principal-col">
        <div class="equipos caja sin-relleno">${equipo("Tu equipo", "aliado", p.equipos.aliado)}${equipo("Rival", "rival", p.equipos.rival)}</div>
        ${cajaJungla(p.jungla)}
        <div class="abajo">${cajaLineas(p.lineas, p.gank, e.modo)}${cajaHistorial(p.historial)}</div>
      </div>
      <aside class="lateral">
        ${cajaDuelo(p.duelo)}
        ${plan}
        <section class="caja">${titulo("Datos destacados")}${avisos}</section>
        ${cajaNotas(p.notas)}
        ${reglas}
      </aside>
    </div>`;
}

// Tus opciones contra el campeón rival de tu posición. Son datos para elegir tú: no se marca ninguno.
function cajaPool(pool, pos) {
  if (!pool) {
    return pos
      ? `<section class="caja">${titulo("Tu pool")}<p class="vacio">Cuando el rival elija a alguien de ${esc(pos)} verás aquí tus campeones contra él.</p></section>`
      : "";
  }
  const filas = pool.filas
    .map((f) => {
      const master = f.wr == null
        ? `<span class="linea2">${f.n ? `${f.n} partidas, pocas` : "sin partidas"}</span>`
        : `<span class="num ${f.wr >= 53 ? "bien" : f.wr <= 47 ? "mal" : ""}">${f.wr}%</span>${barraWr(f.v, f.n)}<span class="num suave">${f.n}</span>`;
      const yo = f.yo_n ? `<span class="num">${f.yo_v}V ${f.yo_n - f.yo_v}D</span>` : `<span class="suave">—</span>`;
      const vs = f.vs_n ? `<span class="num">${f.vs_v}V ${f.vs_n - f.vs_v}D</span>` : `<span class="suave">—</span>`;
      return `<div class="pool-fila"><span class="pool-camp">${retrato(f.icono, "mini")}<b>${esc(f.nombre)}</b></span><span class="pool-master">${master}</span>${yo}${vs}</div>`;
    })
    .join("");
  return `<section class="caja">${titulo(`Tu pool contra ${esc(pool.rival)}`, `${esc(pool.pos)} · partidas de Master+ y las tuyas de la temporada`)}
      <div class="pool-fila cabeza"><span>Campeón</span><span>Master+ contra ${esc(pool.rival)}</span><span>Tú con él</span><span>Tú contra ${esc(pool.rival)}</span></div>
      ${filas || `<p class="vacio">No tienes campeones de ${esc(pool.pos)} con 5 partidas o más esta temporada.</p>`}
      <div class="linea2 envuelve pie-tu">Ordenado por el % de Master+ (con 8 partidas o más). Son datos para decidir tú.</div></section>`;
}

function pintarSeleccion(s) {
  const h = s.historial;
  const mio = s.mio;
  const sub = mio
    ? h.campeon && h.campeon.n
      ? `<span class="num">${h.campeon.v}V ${h.campeon.n - h.campeon.v}D</span> con ${esc(mio.nombre)} esta temporada${esc(h.cola_txt)} · <span class="num ${claseWr(h.campeon.v, h.campeon.n)}">${pct(h.campeon.v, h.campeon.n)}%</span>`
      : `Sin partidas con ${esc(mio.nombre)} esta temporada`
    : "Cuando elijas campeón verás aquí tu historial con él.";
  return `<section class="hero">${mio ? retrato(mio.icono, "retrato hero-retrato") : ""}
      <div class="hero-txt"><div class="etiqueta-cab">Selección de campeón</div><h1>${mio ? esc(mio.nombre) : "Aún no has elegido"}</h1><div class="sub">${sub}</div></div>
      <div class="derecha">${h.campeon && h.campeon.racha ? `<div class="dato"><span class="etiqueta-cab">Últimas con él</span>${racha(h.campeon.racha)}</div>` : ""}</div></section>
    <div class="cuerpo">
      <div class="principal-col">
      ${cajaPool(s.pool, s.pos)}
      <section class="caja">${titulo("Contra lo que van eligiendo", `tus ${h.n} clasificatorias${esc(h.cola_txt)} de la temporada`)}
        ${h.vs.length ? filasVs(h.vs, mio ? mio.nombre : "") : `<p class="vacio">El rival aún no ha elegido.</p>`}</section>
      </div>
      <aside class="lateral">${cajaDuelo(s.duelo)}${cajaNotas(s.notas)}<section class="caja">${titulo("Qué se ve aquí")}
        <p class="envuelve">Solo campeones y tu historial contra ellos. En clasificatoria los nombres de tus aliados están ocultos y la app no intenta averiguarlos.${s.pos && !s.duelo ? ` Tu duelo de ${esc(s.pos)} sale cuando el rival elija a alguien de esa posición.` : ""}</p></section></aside>
    </div>`;
}

function pintarEspera(e) {
  const sync = e.sync.total && e.sync.hechas < e.sync.total
    ? `<div class="sync"><div class="linea2">Descargando tu historial de la temporada · <span class="num">${e.sync.hechas} de ${e.sync.total}</span></div><span class="progreso"><i style="width:${pct(e.sync.hechas, e.sync.total)}%"></i></span></div>`
    : "";
  const texto = e.fase
    ? "En cuanto entres en partida, el panel se rellena solo."
    : "Abre el cliente del LoL. Mientras tanto puedes ver la partida de cualquier jugador con el buscador de arriba.";
  const ov = e.overlay || {};
  const atajo = ov.atajo ? ov.atajo.split("+").map((k) => `<kbd>${esc(k.trim().toUpperCase())}</kbd>`).join("") : "";
  const pasos = ov.activo
    ? `<ol class="pasos limpia">
        <li><span class="n">01</span><div><b>Pantalla de carga</b><div class="linea2 envuelve">El panel sale solo encima del juego y se esconde al empezar.</div></div></li>
        <li><span class="n">02</span><div><b>Ya jugando</b><div class="linea2 envuelve">Mantén ${atajo} para verlo; al soltar, desaparece.</div></div></li>
        <li><span class="n">03</span><div><b>Dentro de las normas</b><div class="linea2 envuelve">Durante la partida solo enseña datos de antes de empezar, como permite Riot.</div></div></li>
      </ol>`
    : "";
  const aviso = ov.aviso ? `<div class="aviso-ventana">${esc(ov.aviso)}</div>` : "";
  return `<div class="espera">
      <div class="espera-icono">${LOGO}</div>
      <div class="etiqueta-cab">Porofesor</div><h1>${esc(e.fase_txt)}</h1><p>${texto}</p>${sync}${pasos}${aviso}</div>`;
}

// --- overlay: lo justo para leerlo en dos segundos ------------------------------------------------
function ovFila(f) {
  let wr = `<span class="cargando">…</span>`;
  if (f.muestra.n) {
    const c = f.camp;
    wr = c.n
      ? `<div class="num ${claseWr(c.v, c.n)}">${c.v}/${c.n}</div><div class="linea2">campeón</div>`
      : `<div class="num ${claseWr(f.muestra.v, f.muestra.n)}">${f.muestra.v}/${f.muestra.n}</div><div class="linea2">últimas</div>`;
  }
  return `<div class="ov-fila ${f.soy_yo ? "yo" : ""}">
      ${rol(f.rol)}
      ${retrato(f.icono)}
      <div style="min-width:0"><div class="nombre"><bdi>${esc(f.nombre)}</bdi></div>${etiquetas(f.etiquetas, 2) || `<div class="linea2">${esc(f.campeon)}</div>`}</div>
      ${rango(f, true)}
      <div class="wr">${wr}</div>
    </div>`;
}

function pintarOverlay(e) {
  const p = e.panel;
  if (!p) return `<div class="ov"><div class="ov-cab">${LOGO.replace("<svg", '<svg width="18" height="18"')}<span class="titulo">Porofesor</span><span class="linea2">Esperando la partida…</span></div></div>`;
  const j = p.jungla;
  const jungla = j
    ? `<section class="caja">${titulo(`Jungla rival · ${esc(j.campeon)}`, `${j.n} partidas · ${j.n_lineas} líneas de tiempo`)}${tarjetas(j, true)}</section>`
    : `<section class="caja">${titulo("Jungla rival")}<p class="vacio">Sin datos.</p></section>`;
  const notas = (p.notas || []).map((n) => `<div class="aviso nota-ov"><span><b class="${n.rival ? "rival-txt" : "aliado-txt"}">${esc(n.campeon)}</b> ${esc(n.texto)}</span></div>`).join("");
  const destacado =
    notas +
    (e.modo === "juego"
      ? p.avisos.slice(0, Math.max(1, 3 - (p.notas || []).length)).map((a) => `<div class="aviso">${esc(a.texto)}</div>`).join("")
      : (p.plan.length ? `<ol class="limpia plan">${p.plan.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : "") +
        p.avisos.slice(0, 2).map((a) => `<div class="aviso ${esc(a.tono)}">${esc(a.texto)}</div>`).join(""));
  const atajo = e.overlay && e.overlay.atajo ? e.overlay.atajo.split("+").map((k) => `<kbd>${esc(k.trim().toUpperCase())}</kbd>`).join("") : "";
  const duelo = e.modo !== "juego" && p.duelo ? cajaDuelo(p.duelo, true) : "";
  return `<div class="ov">
      <div class="ov-cab">${LOGO.replace("<svg", '<svg width="18" height="18"')}
        <span class="titulo">${etapa(e.modo, p)}</span><span class="etiqueta-cab">${esc(p.cola)}</span>
        <span class="hueco"></span><span class="linea2 atajo">${e.modo === "juego" ? "Suelta" : "En partida, mantén"} ${atajo}</span>
        <span class="reloj" id="reloj"></span>
      </div>
      <div class="ov-equipos">
        <div class="ov-equipo aliado"><span class="etiqueta-cab">Tu equipo</span>${p.equipos.aliado.map(ovFila).join("")}</div>
        <div class="ov-equipo rival"><span class="etiqueta-cab">Rival</span>${p.equipos.rival.map(ovFila).join("")}</div>
      </div>
      <div class="ov-pie ${duelo ? "con-duelo" : ""}">${jungla}${duelo}<section class="caja">${titulo(e.modo === "juego" ? "Datos destacados" : "Antes de empezar")}${destacado || `<p class="vacio">Nada que destacar.</p>`}</section></div>
    </div>`;
}

// --- notas por campeón ----------------------------------------------------------------------------
function cajaNotas(notas) {
  if (!notas || !notas.length) return "";
  return `<section class="caja">${titulo("Tus notas")}${notas
    .map((n) => `<div class="nota">${retrato(n.icono, "mini")}<div><b class="${n.rival ? "rival-txt" : "aliado-txt"}">${esc(n.campeon)}</b><div>${esc(n.texto)}</div></div></div>`)
    .join("")}</section>`;
}

// --- pestañas ---------------------------------------------------------------------------------------
function cambiarVista(v) {
  vista = v;
  document.querySelectorAll("#pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.vista === v));
  $("titulo-vista").textContent = TITULOS[v];
  ultimo = "";
  if (v === "revisiones") pintarRevisiones();
  else if (v === "ajustes") pintarAjustes();
  else refrescar();
}

// --- revisiones -------------------------------------------------------------------------------------
const fecha = (ms) => new Date(ms).toLocaleString("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const diferencia = (a, b, sufijo = "") => {
  const d = a - b;
  return `<span class="${d > 0 ? "bien" : d < 0 ? "mal" : "suave"}">${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d)}${sufijo}</span>`;
};

function tablaTendencia(nombre, filas) {
  if (!filas || !filas.length) return "";
  return `<div class="tendencia"><div class="etiqueta-cab">${nombre}</div>${filas
    .map(
      (f) => `<div class="fila-t" data-tip="<b>${esc(f.nombre)}</b> · ${f.v}V ${f.n - f.v}D">
        <span class="t-nombre">${esc(f.nombre)}</span>${barraWr(f.v, f.n)}<span class="num ${claseWr(f.v, f.n)}">${pct(f.v, f.n)}%</span><span class="num suave">${f.n}</span></div>`
    )
    .join("")}</div>`;
}

// Línea de tiempo de la partida: objetivos arriba (color del equipo que lo hizo), tus muertes abajo.
function lineaTiempo(r) {
  const fin = Math.max(minutos(r.duracion), 1);
  const x = (t) => `${Math.min(100, (100 * minutos(t)) / fin).toFixed(2)}%`;
  const marcas = [];
  for (let m = 0; m <= fin; m += 5) marcas.push(`<span class="lt-marca" style="left:${(100 * m) / fin}%"><span class="num">${m}</span></span>`);
  const objetivos = r.objetivos
    .map((o) => {
      const quien = o.tuyo ? (o.participaste ? "tu equipo, contigo" : "tu equipo, sin ti") : "rival";
      return `<span class="lt-obj ${o.tuyo ? "aliado" : "rival"}" style="left:${x(o.t)}" data-tip="<span class=num>${esc(o.t)}</span> · <b>${esc(o.nombre)}</b><br>${quien}"></span>`;
    })
    .join("");
  const muertes = r.muertes
    .map((m) => `<span class="lt-muerte ${m.perdido ? "cara" : ""}" style="left:${x(m.t)}" data-tip="<span class=num>${esc(m.t)}</span> · muerte ante <b>${esc(m.asesino)}</b><br>${esc(m.donde)}${m.perdido ? `<br>${esc(m.perdido)}` : ""}">${ICONO.muerte}</span>`)
    .join("");
  return `<div class="linea-tiempo" role="img" aria-label="Línea de tiempo: ${r.objetivos.length} objetivos y ${r.muertes.length} muertes; el detalle está en las listas de abajo">
      <div class="lt-carril"><span class="lt-rotulo">Objetivos</span><div class="lt-pista">${objetivos}</div></div>
      <div class="lt-carril"><span class="lt-rotulo">Tus muertes</span><div class="lt-pista">${muertes}</div></div>
      <div class="lt-carril eje"><span class="lt-rotulo">min</span><div class="lt-pista">${marcas.join("")}</div></div>
      <div class="leyenda"><span><i class="aliado"></i>Objetivo de tu equipo</span><span><i class="rival"></i>Objetivo rival</span><span>${ICONO.muerte}Tu muerte</span><span><i class="cara"></i>Muerte que costó un objetivo</span></div>
    </div>`;
}

function detalleRevision(r) {
  if (!r) return `<section class="caja"><p class="vacio">Elige una partida de la lista.</p></section>`;
  const resultado = r.gana ? `<span class="resultado bien">Victoria</span>` : `<span class="resultado mal">Derrota</span>`;
  const muertes = r.muertes.length
    ? r.muertes
        .map(
          (m, i) => `<div class="muerte"><span class="num t">${esc(m.t)}</span>
            <div><b>${esc(m.asesino)}</b>${m.ayudas.length ? ` <span class="suave">+ ${esc(m.ayudas.join(", "))}</span>` : ""}<div class="linea2">${esc(m.donde)} · ${m.rivales} rival${m.rivales === 1 ? "" : "es"}</div></div>
            <span class="${m.perdido ? "ojo" : "suave"}">${esc(m.perdido || "sin objetivo perdido")}</span>
            <span class="video">${m.clip ? `<button class="con-icono clip" data-clip="${i}">${ICONO.play}<span>Ver clip</span></button>` : m.video ? `<span class="num suave">${esc(m.video.archivo)} · ${esc(m.video.en)}</span>` : ""}</span></div>`
        )
        .join("")
    : `<p class="vacio">No moriste ni una vez.</p>`;
  const comp = r.comparacion
    ? `<div class="comparacion"><div></div><div class="etiqueta-cab">Oro</div><div class="etiqueta-cab">CS</div><div class="etiqueta-cab">Exp.</div><div class="etiqueta-cab">Nivel</div>${Object.entries(r.comparacion.minutos)
        .map(([m, d]) => `<div class="etiqueta-cab">Min ${m}</div><div class="num">${diferencia(d.oro[0], d.oro[1])}</div><div class="num">${diferencia(d.cs[0], d.cs[1])}</div><div class="num">${diferencia(d.xp[0], d.xp[1])}</div><div class="num">${diferencia(d.nivel[0], d.nivel[1])}</div>`)
        .join("")}</div>`
    : `<p class="vacio">Sin jungla rival con el que comparar.</p>`;
  const objetivos = r.objetivos.length
    ? r.objetivos.map((o) => `<div class="objetivo"><span class="num suave">${esc(o.t)}</span><span class="${o.tuyo ? "aliado-txt" : "rival-txt"}">${esc(o.nombre)}</span><span class="suave">${o.tuyo ? (o.participaste ? "tu equipo, contigo" : "tu equipo, sin ti") : "rival"}</span></div>`).join("")
    : `<p class="vacio">Nadie hizo objetivos épicos.</p>`;
  const prevision = r.prevision.length
    ? r.prevision
        .map((f) => `<div class="prevision"><div class="prev-cab"><b>${esc(f.tema)}</b><span class="veredicto ${f.acierto ? "bien" : "fallo"}">${f.acierto ? "Acertó" : "Falló"}</span></div><span class="suave">Decía: ${esc(f.dijo)}</span><span>Pasó: ${esc(f.paso)}</span></div>`)
        .join("")
    : `<p class="vacio">Sin datos del panel de esa partida.</p>`;
  return `<section class="caja revision">
      <div class="rev-cab">${retrato(r.icono, "retrato hero-retrato")}<div><div class="etiqueta-cab">${fecha(r.fecha)}${r.lp ? ` · ${esc(ligaTxt(r.lp))}` : ""}${r.lp && r.lp.cambio != null ? ` · ${lp(r.lp.cambio)}` : ""}</div>
        <h1>${resultado}<span class="sep">·</span>${esc(r.campeon)}<span class="sep">·</span><span class="num">${esc(r.duracion)}</span></h1></div>
        ${r.carpeta ? `<button id="abrir-carpeta" class="con-icono">${ICONO.carpeta}<span>Abrir la grabación</span></button>` : ""}</div>
      <div class="metricas">
        <div><div class="etiqueta-cab">KDA</div><div class="num v">${r.kda.join("<span class='suave'> / </span>")}</div></div>
        <div><div class="etiqueta-cab">CS/min</div><div class="num v">${coma(r.cs_min)}</div></div>
        <div><div class="etiqueta-cab">Part. en kills</div><div class="num v">${r.kp}%</div></div>
        <div><div class="etiqueta-cab">Daño del equipo</div><div class="num v">${r.dano_pct}%</div></div>
        <div><div class="etiqueta-cab">Visión</div><div class="num v">${r.vision}</div><div class="linea2">${r.wards} wards · ${r.control} de control</div></div>
      </div>
      <h3 class="etiqueta-cab">La partida</h3>${lineaTiempo(r)}
      <h3 class="etiqueta-cab">Tus muertes <span class="cuenta-h">${r.muertes.length}</span></h3>${muertes}
      <div class="dos">
        <div><h3 class="etiqueta-cab">Contra ${esc(r.comparacion ? r.comparacion.rival : "el jungla rival")}</h3>${comp}</div>
        <div><h3 class="etiqueta-cab">Lo que preveía el panel</h3>${prevision}</div>
      </div>
      ${r.referencia ? `<h3 class="etiqueta-cab">Comparado con ${esc(r.referencia.ref)}</h3>${tablaComparacion(r.referencia, "Tú: esta partida.")}` : ""}
      <h3 class="etiqueta-cab">Objetivos</h3><div class="objetivos">${objetivos}</div>
    </section>`;
}

async function pintarRevisiones() {
  if (vista !== "revisiones") return;
  const datos = await (await fetch("/api/revisiones")).json();
  if (!revisionVista && datos.lista.length) revisionVista = datos.lista[0].id;
  const r = revisionVista ? await (await fetch(`/api/revision?id=${encodeURIComponent(revisionVista)}`)).json() : null;
  if (vista !== "revisiones") return;
  const lista = datos.lista.length
    ? datos.lista
        .map(
          (x) => `<button class="item-revision ${x.id === revisionVista ? "activa" : ""}" data-revision="${esc(x.id)}">
            <span class="res ${x.gana ? "bien" : "mal"}">${x.gana ? "V" : "D"}</span>${retrato(x.icono, "mini")}
            <span class="item-txt"><span><b>${esc(x.campeon)}</b> <span class="num suave">${x.kda.join("/")}</span></span><span class="linea2">${fecha(x.fecha)} · ${esc(x.duracion)}</span></span>
            ${x.lp != null ? lp(x.lp) : "<span></span>"}</button>`
        )
        .join("")
    : `<p class="vacio envuelve">Aún no hay revisiones. Se hacen solas al acabar cada partida tuya en la Grieta.</p>`;
  const t = datos.tendencias;
  const tendencias = t
    ? `<section class="caja">${titulo("Tus tendencias", `${t.n} clasificatorias de la temporada · barra = % de victorias, la marca es el 50%`)}
        <div class="tendencias">${tablaTendencia("Sesión", t.sesion)}${tablaTendencia("Hora", t.franjas)}${tablaTendencia("Duración", t.duracion)}${tablaTendencia("Contra tu rival de posición", t.rivales)}</div></section>`
    : "";
  const v = datos.lista.filter((x) => x.gana).length;
  datosRevisiones = datos;
  const muertes = datos.muertes && datos.muertes.length
    ? `<section class="caja">${titulo("Dónde mueres", `${datos.muertes.length} muertes de tus partidas revisadas, todas vistas desde la base azul`)}${mapaMuertes(datos.muertes)}</section>`
    : "";
  $("principal").innerHTML = `${resumenHoy(datos.lista)}<div class="fila-dos">${tendencias}${muertes}</div><div class="revisiones">
      <aside class="caja lista-revisiones">${titulo("Partidas revisadas", datos.lista.length ? `<span class="num">${v}V ${datos.lista.length - v}D</span>` : "")}${lista}</aside>
      ${detalleRevision(r)}</div>`;
}

const NIVEL_TXT = { iron: "Hierro", bronze: "Bronce", silver: "Plata", gold: "Oro", platinum: "Platino", emerald: "Esmeralda", diamond: "Diamante", master: "Maestro", grandmaster: "Gran Maestro", challenger: "Aspirante" };
const ligaTxt = (l) => `${NIVEL_TXT[l.nivel] || l.nivel}${["master", "grandmaster", "challenger"].includes(l.nivel) ? "" : ` ${l.rank}`} · ${l.lp} LP`;
const lp = (c) => `<span class="num lp ${c > 0 ? "bien" : c < 0 ? "mal" : "suave"}">${c > 0 ? "+" : c < 0 ? "−" : "±"}${Math.abs(c)} LP</span>`;

// Lo de hoy: partidas revisadas desde las 6:00 (una sesión de madrugada cuenta para el día anterior).
function resumenHoy(lista) {
  const corte = new Date();
  if (corte.getHours() < 6) corte.setDate(corte.getDate() - 1);
  corte.setHours(6, 0, 0, 0);
  const hoy = lista.filter((x) => x.fecha >= corte.getTime());
  if (!hoy.length) return "";
  const v = hoy.filter((x) => x.gana).length;
  const con = hoy.filter((x) => x.lp != null);
  const total = con.reduce((a, x) => a + x.lp, 0);
  return `<section class="hoy">
      <div><span class="etiqueta-cab">Hoy</span><span class="num grande-m">${v}V ${hoy.length - v}D</span></div>
      ${con.length ? `<div><span class="etiqueta-cab">LP</span>${lp(total).replace("num lp", "num lp grande-m")}</div>` : ""}
      <div><span class="etiqueta-cab">Partidas</span><span class="racha-hoy">${hoy
        .slice()
        .reverse()
        .map((x) => `<span class="res ${x.gana ? "bien" : "mal"}">${x.gana ? "V" : "D"}</span>`)
        .join("")}</span></div>
    </section>`;
}

// Mapa de tus muertes; cada punto lleva a su revisión.
function mapaMuertes(lista) {
  const filtros = { todas: "Todas", antes: "<15 min", despues: "15+ min", derrotas: "Derrotas" };
  const ver = lista.filter((m) =>
    filtroMuertes === "antes" ? m.ms < 15 * 60000 : filtroMuertes === "despues" ? m.ms >= 15 * 60000 : filtroMuertes === "derrotas" ? !m.gana : true
  );
  return `<div class="mapa-muertes">
      <div class="selector" role="group" aria-label="Qué muertes">${Object.entries(filtros)
        .map(([k, txt]) => `<button class="${k === filtroMuertes ? "activa" : ""}" data-filtro="${k}">${txt}</button>`)
        .join("")}</div>
      <div class="mapa" role="img" aria-label="${ver.length} muertes en el mapa">
        ${ver
          .map((m) => `<span class="punto-mapa muerte-mapa" data-revision="${esc(m.id)}" style="${enMapa(m.x, m.y)}" data-tip="<b>${esc(m.campeon)}</b> · <span class=num>${esc(m.t)}</span><br>ante ${esc(m.asesino)} · ${m.gana ? "victoria" : "derrota"}"></span>`)
          .join("")}
      </div>
      <div class="linea2 envuelve"><span class="num">${ver.length}</span> muertes. Pulsa una para abrir su partida.</div>
    </div>`;
}

// --- ajustes -----------------------------------------------------------------------------------------
let campeones = [];

function filaReferencia(nombre, rid, estado) {
  return `<div class="nota-edit ref-edit"><input type="text" list="lista-campeones" class="campeon-ref" value="${esc(nombre)}" placeholder="Campeón">
    <input type="text" class="rid-ref" value="${esc(rid)}" placeholder="Jugador (Nombre#TAG), de cualquier servidor"><button class="quitar-nota" title="Quitar">Quitar</button>
    ${estado ? `<span class="linea2 estado-ref">${esc(estado)}</span>` : ""}</div>`;
}

function filaNota(nombre, texto) {
  return `<div class="nota-edit"><input type="text" list="lista-campeones" class="campeon-nota" value="${esc(nombre)}" placeholder="Campeón">
    <input type="text" class="texto-nota" value="${esc(texto)}" placeholder="Tu nota (sale cuando está en la partida)"><button class="quitar-nota" title="Quitar">Quitar</button></div>`;
}

const grupo = (nombre, desc, cuerpo) =>
  `<section class="grupo"><div class="grupo-txt"><h2>${nombre}</h2><p>${desc}</p></div><div class="grupo-campos">${cuerpo}</div></section>`;
const interruptor = (id, activo, texto) =>
  `<label class="interruptor"><input type="checkbox" id="${id}" ${activo ? "checked" : ""}><span class="pista" aria-hidden="true"></span><span>${texto}</span></label>`;

async function pintarAjustes() {
  const a = await (await fetch("/api/ajustes")).json();
  if (vista !== "ajustes") return;
  campeones = a.campeones;
  const nombre = (id) => (campeones.find((c) => String(c.id) === String(id)) || {}).nombre || id;
  const notas = Object.entries(a.notas || {}).map(([id, txt]) => filaNota(nombre(id), txt)).join("");
  const refs = Object.entries(a.referencias || {})
    .map(([id, rid]) => {
      const n = (a.referencias_partidas || {})[id];
      return filaReferencia(nombre(id), rid, n == null ? "" : n ? `${n} partidas suyas con ese campeón` : "buscando sus partidas…");
    })
    .join("");
  const opciones = Object.entries(a.opciones_comparar || {})
    .map(([k, v]) => `<option value="${esc(k)}" ${k === a.comparar_con ? "selected" : ""}>${esc(v)}</option>`)
    .join("");
  const opacidad = Math.round((a.overlay_opacidad || 0.94) * 100);
  $("principal").innerHTML = `<div class="ajustes">
    ${grupo("Panel encima del juego", "Sale solo en la pantalla de carga y, ya jugando, mientras mantienes el atajo. Durante la partida solo enseña datos de antes de empezar, como permite Riot. El juego tiene que estar en ventana sin bordes.", `
      ${interruptor("a-overlay", a.overlay, "Enseñarlo en la pantalla de carga y al mantener el atajo")}
      <label>Atajo (mantener) <input type="text" id="a-atajo" value="${esc(a.atajo_overlay)}" placeholder="ctrl+tab"></label>
      <label>Opacidad <span class="rango-fila"><input type="range" id="a-opacidad" min="40" max="100" value="${opacidad}"><span class="num" id="opacidad-valor">${opacidad}%</span></span></label>`)}
    ${grupo("Siempre en marcha", "Así el recolector sigue llenando tus duelos de Master+ y el overlay está listo al jugar. Gasta muy poco: en torno al 2% de un núcleo y 130 MB de memoria.", `
      ${interruptor("a-siempre", a.siempre_en_marcha, "Arrancar con Windows y seguir con el LoL cerrado")}
      <div><button id="salir-app">Cerrar Porofesor del todo</button></div>`)}
    ${grupo("Grabación", "Cada partida en la Grieta se graba en Vídeos\\LoL-coach y la revisión apunta el minuto de cada muerte en el vídeo.", `
      ${interruptor("a-grabar", a.grabar, "Grabar cada partida en la Grieta")}
      <label>Grabar con <select id="a-codificador">
        <option value="auto" ${a.grabacion_codificador !== "cpu" ? "selected" : ""}>La gráfica si se puede (gasta menos procesador)</option>
        <option value="cpu" ${a.grabacion_codificador === "cpu" ? "selected" : ""}>El procesador</option></select></label>
      <label>Espacio máximo, en GB <input type="text" id="a-max-gb" value="${esc(String(a.grabacion_max_gb ?? 0))}" inputmode="numeric" class="corto"><span class="ayuda">0 = sin límite; al pasarlo se borran las más viejas.</span></label>`)}
    ${grupo("Tus cuentas", "Una por línea, como Nombre#TAG. Las partidas de todas cuentan para tu historial y tus revisiones.", `
      <textarea id="a-cuentas" rows="3" aria-label="Tus cuentas">${esc((a.cuentas || []).join("\n"))}</textarea>`)}
    ${grupo("Tus reglas", "Salen en cada partida, una por línea. Escríbelas como hábitos que puedas comprobar.", `
      <textarea id="a-reglas" rows="4" aria-label="Tus reglas">${esc((a.recordatorios || []).join("\n"))}</textarea>`)}
    ${grupo("Con quién compararte", "Se usa en tu duelo y en cada revisión. Con un perfil de base te comparas con ese jugador en todo: con tu campeón si lo juega y, si no, en tu posición. Un jugador por campeón manda cuando juegas ese campeón. Sus partidas se recogen solas.", `
      <label>Referencia de base <select id="a-comparar">${opciones}</select></label>
      <label id="caja-perfil" ${a.comparar_con === "perfil" ? "" : "hidden"}>Tu perfil de referencia (Nombre#TAG, de cualquier servidor)
        <input type="text" id="a-perfil" value="${esc(a.perfil_base || "")}" placeholder="p. ej. un jugador de Challenger al que quieras parecerte">
        ${a.perfil_partidas == null ? "" : `<span class="ayuda">${a.perfil_partidas ? `${a.perfil_partidas} partidas suyas guardadas` : "buscando sus partidas…"}</span>`}</label>
      <div class="sub-campos"><span class="etiqueta-cab">Por campeón</span><div id="referencias">${refs}</div><div><button id="nueva-ref">Añadir jugador de referencia</button></div></div>`)}
    ${grupo("Notas por campeón", "Salen cuando ese campeón está en tu partida, en el panel y encima del juego.", `
      <div id="notas">${notas}</div><div><button id="nueva-nota">Añadir nota</button></div>`)}
    <datalist id="lista-campeones">${campeones.map((c) => `<option value="${esc(c.nombre)}">`).join("")}</datalist>
    <div class="guardar"><button class="primario" id="guardar-ajustes">Guardar cambios</button><span id="ajustes-estado" class="linea2"></span>
      <span class="linea2 version">Porofesor ${esc(a.version.version)}${a.version.lista ? ` · la ${esc(a.version.nueva)} se instala sola cuando cierres esta ventana, fuera de partida` : ""}</span></div>
  </div>`;
}

async function guardarAjustes() {
  const notas = {};
  for (const fila of document.querySelectorAll(".nota-edit:not(.ref-edit)")) {
    const nombre = fila.querySelector(".campeon-nota").value.trim().toLowerCase();
    const texto = fila.querySelector(".texto-nota").value.trim();
    const c = campeones.find((x) => x.nombre.toLowerCase() === nombre);
    if (c && texto) notas[c.id] = texto;
  }
  const referencias = {};
  for (const fila of document.querySelectorAll(".ref-edit")) {
    const nombre = fila.querySelector(".campeon-ref").value.trim().toLowerCase();
    const rid = fila.querySelector(".rid-ref").value.trim();
    const c = campeones.find((x) => x.nombre.toLowerCase() === nombre);
    if (c && rid) referencias[c.id] = rid;
  }
  $("ajustes-estado").textContent = "Guardando…";
  const lineas = (id) => $(id).value.split("\n").map((x) => x.trim()).filter(Boolean);
  const r = await enviar("/api/ajustes", {
    overlay: $("a-overlay").checked,
    atajo_overlay: $("a-atajo").value,
    overlay_opacidad: Number($("a-opacidad").value) / 100,
    grabar: $("a-grabar").checked,
    grabacion_codificador: $("a-codificador").value,
    grabacion_max_gb: $("a-max-gb").value,
    siempre_en_marcha: $("a-siempre").checked,
    comparar_con: $("a-comparar").value,
    perfil_base: $("a-perfil").value,
    referencias,
    cuentas: lineas("a-cuentas"),
    recordatorios: lineas("a-reglas"),
    notas,
  });
  if (r.ok) await pintarAjustes(); // así se ve el estado de las referencias nuevas
  $("ajustes-estado").textContent = r.ok ? "Guardado." : r.error;
  $("ajustes-estado").className = r.ok ? "bien" : "mal";
}

// --- bucle ---------------------------------------------------------------------------------------
function pintarCabecera(e) {
  $("fase").innerHTML = `<span class="punto"></span><span>${esc(e.fase_txt)}</span>`;
  $("fase").className = `chip ${e.fase === "InProgress" ? "vivo" : e.fase ? "activo" : ""}`;
  $("cuenta").hidden = !e.cuenta;
  $("cuenta").textContent = e.cuenta;
  const usadas = pct(e.cuota.usadas, e.cuota.tope);
  $("cuota").innerHTML = `<div class="cuota-txt"><span>Consultas a Riot</span><span class="num">${e.cuota.usadas}/${e.cuota.tope}</span></div>
    <span class="medidor ${usadas >= 90 ? "lleno" : ""}"><i style="width:${usadas}%"></i></span>`;
  const g = e.grabacion;
  $("grabacion").hidden = !g;
  if (g) {
    $("grabacion").innerHTML = `<span class="punto"></span><span>${g.parada ? "Grabación parada" : g.carpeta ? "Grabando" : "Grabación lista"}</span>`;
    $("grabacion").className = `chip ${g.parada ? "parada" : g.carpeta ? "rec" : ""}`;
    $("grabacion").title = g.parada ? "El vídeo ha dejado de crecer" : g.carpeta || "Esperando a que arranque el juego";
  }
  const banda = $("banda");
  if (e.clave.ok) banda.innerHTML = "";
  else if (banda.dataset.error !== e.clave.error || !banda.innerHTML) {
    banda.innerHTML = `<div class="banda"><span class="punto"></span><span>${esc(e.clave.error)}</span>
      <form id="clave"><input type="text" id="clave-txt" placeholder="Pega aquí la clave nueva (RGAPI-…)" autocomplete="off"> <button type="submit" class="primario">Guardar</button></form>
      <a href="https://developer.riotgames.com/" target="_blank" rel="noopener">developer.riotgames.com</a>
      <span class="error-busqueda" id="clave-error"></span></div>`;
  }
  banda.dataset.error = e.clave.error;
  const nueva = e.ultima_revision && e.ultima_revision !== revisionAvisada && vista !== "revisiones";
  $("revision-lista").hidden = !nueva;
  pintarVersion(e.version, e.novedades);
}

// Versión nueva descargada (se instala sola cuando no estás en cola ni en partida) y, ya instalada, sus novedades.
function pintarVersion(v, n) {
  const aviso = $("aviso-version");
  aviso.hidden = !(v && v.lista);
  if (v && v.lista) {
    aviso.innerHTML = `<span class="punto"></span><span><b>Versión ${esc(v.nueva)} lista</b><span class="linea2 envuelve">Se instala sola cuando cierres esta ventana, fuera de partida.</span></span>`;
  }
  if (!n || novedadesCerradas) return;
  if ($("novedades").dataset.version === n.version) return;
  $("novedades").dataset.version = n.version;
  const lineas = String(n.notas || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const puntos = lineas.filter((l) => /^[-*•]/.test(l)).map((l) => `<li>${esc(l.replace(/^[-*•]\s*/, ""))}</li>`);
  const texto = lineas.filter((l) => !/^[-*•]/.test(l)).map((l) => `<p>${esc(l.replace(/^#+\s*/, ""))}</p>`);
  $("novedades").innerHTML = `<section class="novedades">
      <div class="nov-cab"><span class="etiqueta-cab">Novedades</span><h2>Porofesor ${esc(n.version)}</h2></div>
      <div class="nov-cuerpo">${texto.join("")}${puntos.length ? `<ul>${puntos.join("")}</ul>` : ""}</div>
      <button id="cerrar-novedades">Entendido</button>
    </section>`;
}

function pintar(e) {
  const anterior = estadoActual;
  estadoActual = e;
  const p = e.panel;
  if (e.reloj) inicioPartida = Date.now() - e.reloj * 1000;
  else inicioPartida = p && !p.terminada && e.modo === "juego" ? p.inicio : 0;
  if (OVERLAY) {
    $("principal").innerHTML = pintarOverlay(e);
  } else {
    pintarCabecera(e);
    if (vista === "partida") {
      $("principal").innerHTML = p && (!e.seleccion || !p.terminada) ? pintarPanel(e) : e.seleccion ? pintarSeleccion(e.seleccion) : pintarEspera(e);
    } else if (vista === "revisiones" && e.ultima_revision && e.ultima_revision !== (anterior || {}).ultima_revision) {
      pintarRevisiones();
    }
  }
  reloj();
}

function reloj() {
  const el = $("reloj");
  if (!el) return;
  if (!inicioPartida) return void (el.textContent = OVERLAY ? "" : "—");
  const s = Math.max(0, Math.floor((Date.now() - inicioPartida) / 1000));
  el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

async function refrescar() {
  try {
    const texto = await (await fetch(OVERLAY ? "/api/estado?vista=overlay" : "/api/estado")).text();
    if (texto === ultimo) return;
    ultimo = texto;
    pintar(JSON.parse(texto));
  } catch {
    if (!OVERLAY) $("fase").innerHTML = `<span class="punto"></span><span>Sin conexión con la app</span>`;
  }
}

// Se puede abrir directamente en una pestaña: /#revisiones o /#ajustes.
if (!OVERLAY && ["revisiones", "ajustes"].includes(location.hash.slice(1))) cambiarVista(location.hash.slice(1));
refrescar();
setInterval(refrescar, 1500);
setInterval(reloj, 1000);

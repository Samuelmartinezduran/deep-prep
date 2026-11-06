// Ventana principal, pestaña Revisiones: lo de hoy, tendencias, mapa de muertes y la revisión de cada partida.
import { enviar } from "./api.js";
import { tablaComparacion } from "./duelo.js";
import { estado } from "./estado.js";
import { ICONO } from "./iconos.js";
import { barraWr, diferencia, lp, retrato, titulo } from "./piezas.js";
import { $, claseWr, coma, enMapa, esc, fecha, ligaTxt, minutos, pct } from "./util.js";

export function tablaTendencia(nombre, filas) {
  if (!filas || !filas.length) return "";
  return `<div class="tendencia"><div class="etiqueta-cab">${nombre}</div>${filas
    .map(
      (f) => `<div class="fila-t" data-tip="<b>${esc(f.nombre)}</b> · ${f.v}V ${f.n - f.v}D">
        <span class="t-nombre">${esc(f.nombre)}</span>${barraWr(f.v, f.n)}<span class="num ${claseWr(f.v, f.n)}">${pct(f.v, f.n)}%</span><span class="num suave">${f.n}</span></div>`
    )
    .join("")}</div>`;
}

const quien = (o) => (o.tuyo ? (o.participaste ? "tu equipo, contigo" : "tu equipo, sin ti") : "rival");

// Línea de tiempo de la partida: objetivos arriba (color del equipo que lo hizo), tus muertes abajo.
export function lineaTiempo(r) {
  const fin = Math.max(minutos(r.duracion), 1);
  const x = (t) => `${Math.min(100, (100 * minutos(t)) / fin).toFixed(2)}%`;
  const marcas = [];
  for (let m = 0; m <= fin; m += 5) marcas.push(`<span class="lt-marca" style="left:${(100 * m) / fin}%"><span class="num">${m}</span></span>`);
  const objetivos = r.objetivos
    .map((o) => `<span class="lt-obj ${o.tuyo ? "aliado" : "rival"}" style="left:${x(o.t)}" data-tip="<span class=num>${esc(o.t)}</span> · <b>${esc(o.nombre)}</b><br>${quien(o)}"></span>`)
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

export function detalleRevision(r) {
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
    ? r.objetivos.map((o) => `<div class="objetivo"><span class="num suave">${esc(o.t)}</span><span class="${o.tuyo ? "aliado-txt" : "rival-txt"}">${esc(o.nombre)}</span><span class="suave">${quien(o)}</span></div>`).join("")
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

// Lo de hoy: partidas revisadas desde las 6:00 (una sesión de madrugada cuenta para el día anterior).
export function resumenHoy(lista, ahora = new Date()) {
  const corte = new Date(ahora.getTime());
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

const FILTROS = { todas: "Todas", antes: "<15 min", despues: "15+ min", derrotas: "Derrotas" };
export const filtrar = (lista, filtro) =>
  lista.filter((m) => (filtro === "antes" ? m.ms < 15 * 60000 : filtro === "despues" ? m.ms >= 15 * 60000 : filtro === "derrotas" ? !m.gana : true));

// Mapa de tus muertes (con el filtro del estado); cada punto lleva a su revisión.
export function mapaMuertes(lista) {
  const ver = filtrar(lista, estado.filtroMuertes);
  return `<div class="mapa-muertes">
      <div class="selector" role="group" aria-label="Qué muertes">${Object.entries(FILTROS)
        .map(([k, txt]) => `<button class="${k === estado.filtroMuertes ? "activa" : ""}" data-filtro="${k}">${txt}</button>`)
        .join("")}</div>
      <div class="mapa" role="img" aria-label="${ver.length} muertes en el mapa">
        ${ver
          .map((m) => `<span class="punto-mapa muerte-mapa" data-revision="${esc(m.id)}" style="${enMapa(m.x, m.y)}" data-tip="<b>${esc(m.campeon)}</b> · <span class=num>${esc(m.t)}</span><br>ante ${esc(m.asesino)} · ${m.gana ? "victoria" : "derrota"}"></span>`)
          .join("")}
      </div>
      <div class="linea2 envuelve"><span class="num">${ver.length}</span> muertes. Pulsa una para abrir su partida.</div>
    </div>`;
}

// Botón de filtro del mapa de muertes: repinta solo el mapa.
export function filtrarMuertes(b) {
  estado.filtroMuertes = b.dataset.filtro;
  if (estado.datosRevisiones) b.closest(".mapa-muertes").outerHTML = mapaMuertes(estado.datosRevisiones.muertes);
}

export async function pintarRevisiones() {
  if (estado.vista !== "revisiones") return;
  const datos = await (await fetch("/api/revisiones")).json();
  if (!estado.revisionVista && datos.lista.length) estado.revisionVista = datos.lista[0].id;
  const r = estado.revisionVista ? await (await fetch(`/api/revision?id=${encodeURIComponent(estado.revisionVista)}`)).json() : null;
  if (estado.vista !== "revisiones") return;
  const lista = datos.lista.length
    ? datos.lista
        .map(
          (x) => `<button class="item-revision ${x.id === estado.revisionVista ? "activa" : ""}" data-revision="${esc(x.id)}">
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
  estado.datosRevisiones = datos;
  const muertes = datos.muertes && datos.muertes.length
    ? `<section class="caja">${titulo("Dónde mueres", `${datos.muertes.length} muertes de tus partidas revisadas, todas vistas desde la base azul`)}${mapaMuertes(datos.muertes)}</section>`
    : "";
  $("principal").innerHTML = `${resumenHoy(datos.lista)}<div class="fila-dos">${tendencias}${muertes}</div><div class="revisiones">
      <aside class="caja lista-revisiones">${titulo("Partidas revisadas", datos.lista.length ? `<span class="num">${v}V ${datos.lista.length - v}D</span>` : "")}${lista}</aside>
      ${detalleRevision(r)}</div>`;
}

// Botones de la revisión abierta: el clip de una muerte y la carpeta de la grabación. El error sale en el botón.
export async function abrirClip(b) {
  const r = await enviar("/api/clip", { id: estado.revisionVista, i: Number(b.dataset.clip) });
  if (!r.ok) b.lastChild.textContent = r.error;
}

export async function abrirCarpeta(b) {
  const r = await enviar("/api/carpeta", { id: estado.revisionVista });
  if (!r.ok) b.lastChild.textContent = r.error;
}

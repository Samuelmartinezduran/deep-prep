// Ventana principal, pestaña Partida: el panel de la partida (pantalla de carga, en juego o ya terminada).
import { cajaDuelo } from "./duelo.js";
import { estado } from "./estado.js";
import { barraWr, cajaNotas, etapa, etiquetas, filasVs, racha, rango, retrato, rol, tarjetas, titulo } from "./piezas.js";
import { claseWr, coma, enMapa, esc, miles, pct, ROL_TXT } from "./util.js";

export function fila(f) {
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
// Si el minuto elegido no está en el mapa, pasa al 3 (o al primero que haya) y lo guarda en el estado.
export function mapaJungla(j) {
  const minutos = Object.keys(j.mapa).sort((a, b) => a - b);
  if (!j.mapa[estado.minutoMapa]) estado.minutoMapa = minutos.includes("3") ? "3" : minutos[0];
  const minuto = estado.minutoMapa;
  const puntos = j.mapa[minuto] || [];
  return `<div class="mapa-jungla">
      <div class="selector" role="group" aria-label="Minuto">${minutos
        .map((m) => `<button class="${m === minuto ? "activa" : ""}" data-minuto="${esc(m)}">${esc(m)}:00</button>`)
        .join("")}</div>
      <div class="mapa" role="img" aria-label="Posición de ${esc(j.campeon)} al minuto ${esc(minuto)} en ${puntos.length} partidas">
        ${puntos.map(([x, y]) => `<span class="punto-mapa rival" style="${enMapa(x, y)}"></span>`).join("")}
      </div>
      <div class="linea2 envuelve">Cada punto es una de sus ${puntos.length} partidas: dónde estaba al ${esc(minuto)}:00, ya girado al lado en que juega hoy.</div>
    </div>`;
}

// Botón de minuto del mapa del jungla: repinta solo el mapa.
export function elegirMinuto(b) {
  estado.minutoMapa = b.dataset.minuto;
  const j = estado.actual && estado.actual.panel && estado.actual.panel.jungla;
  if (j) b.closest(".mapa-jungla").outerHTML = mapaJungla(j);
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

export function estadoCarga(p, cuota) {
  const cargando = p.progreso.hechas < p.progreso.total;
  let txt = cargando ? `Cargando ${p.progreso.hechas} de ${p.progreso.total} consultas` : "Datos completos";
  if (cargando && cuota.espera > 1) txt += ` · Riot deja seguir en ${Math.ceil(cuota.espera)} s`;
  return { cargando, txt, ancho: p.progreso.total ? Math.round((100 * p.progreso.hechas) / p.progreso.total) : 0 };
}

export function pintarPanel(e) {
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

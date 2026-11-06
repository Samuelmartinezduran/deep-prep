// Armazón fijo de la ventana principal (la barra lateral y la superior no se repintan) y lo que cambia en él:
// estado del cliente, cuenta, consultas a Riot, grabación, aviso de la clave y de la revisión nueva.
import { estado } from "./estado.js";
import { ICONO, LOGO } from "./iconos.js";
import { pintarVersion } from "./novedades.js";
import { $, esc, pct } from "./util.js";

export const ARMAZON = `
    <div class="app">
      <aside class="barra">
        <div class="marca">${LOGO}<span>Deep Prep</span></div>
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

// Chip de estado con su punto de color.
export const chip = (texto) => `<span class="punto"></span><span>${esc(texto)}</span>`;

export function pintarCabecera(e) {
  $("fase").innerHTML = chip(e.fase_txt);
  $("fase").className = `chip ${e.fase === "InProgress" ? "vivo" : e.fase ? "activo" : ""}`;
  $("cuenta").hidden = !e.cuenta;
  $("cuenta").textContent = e.cuenta;
  const usadas = pct(e.cuota.usadas, e.cuota.tope);
  $("cuota").innerHTML = `<div class="cuota-txt"><span>Consultas a Riot</span><span class="num">${e.cuota.usadas}/${e.cuota.tope}</span></div>
    <span class="medidor ${usadas >= 90 ? "lleno" : ""}"><i style="width:${usadas}%"></i></span>`;
  const g = e.grabacion;
  $("grabacion").hidden = !g;
  if (g) {
    $("grabacion").innerHTML = chip(g.parada ? "Grabación parada" : g.carpeta ? "Grabando" : "Grabación lista");
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
  const nueva = e.ultima_revision && e.ultima_revision !== estado.revisionAvisada && estado.vista !== "revisiones";
  $("revision-lista").hidden = !nueva;
  pintarVersion(e.version, e.novedades);
}

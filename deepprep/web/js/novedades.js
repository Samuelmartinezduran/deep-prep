// Versión nueva descargada (se instala sola cuando no estás en cola ni en partida) y, ya instalada, sus novedades.
import { enviar } from "./api.js";
import { estado } from "./estado.js";
import { $, esc } from "./util.js";

// Notas de la versión: las líneas que empiezan por "-", "*" o "•" son puntos; el resto, párrafos.
export function htmlNovedades(n) {
  const lineas = String(n.notas || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const puntos = lineas.filter((l) => /^[-*•]/.test(l)).map((l) => `<li>${esc(l.replace(/^[-*•]\s*/, ""))}</li>`);
  const texto = lineas.filter((l) => !/^[-*•]/.test(l)).map((l) => `<p>${esc(l.replace(/^#+\s*/, ""))}</p>`);
  return `<section class="novedades">
      <div class="nov-cab"><span class="etiqueta-cab">Novedades</span><h2>Deep Prep ${esc(n.version)}</h2></div>
      <div class="nov-cuerpo">${texto.join("")}${puntos.length ? `<ul>${puntos.join("")}</ul>` : ""}</div>
      <button id="cerrar-novedades">Entendido</button>
    </section>`;
}

export function pintarVersion(v, n) {
  const aviso = $("aviso-version");
  aviso.hidden = !(v && v.lista);
  if (v && v.lista) {
    aviso.innerHTML = `<span class="punto"></span><span><b>Versión ${esc(v.nueva)} lista</b><span class="linea2 envuelve">Se instala sola cuando cierres esta ventana, fuera de partida.</span></span>`;
  }
  if (!n || estado.novedadesCerradas) return;
  if ($("novedades").dataset.version === n.version) return;
  $("novedades").dataset.version = n.version;
  $("novedades").innerHTML = htmlNovedades(n);
}

// «Entendido»: la app apunta que ya se han visto. Si no puede, el error sale en el botón y las novedades siguen.
export async function cerrarNovedades(b) {
  const r = await enviar("/api/novedades");
  if (!r.ok) {
    b.lastChild.textContent = r.error;
    return;
  }
  $("novedades").innerHTML = "";
  estado.novedadesCerradas = true;
}

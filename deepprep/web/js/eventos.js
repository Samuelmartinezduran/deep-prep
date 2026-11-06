// Lo que hace cada botón y formulario de la ventana principal. Un solo oyente por tipo de evento en el
// documento: así vale también para lo que se pinta después.
import { filaNota, filaReferencia, guardarAjustes, salirApp } from "./ajustes.js";
import { enviar } from "./api.js";
import { estado } from "./estado.js";
import { cerrarNovedades } from "./novedades.js";
import { elegirMinuto } from "./panel.js";
import { abrirCarpeta, abrirClip, filtrarMuertes, pintarRevisiones } from "./revisiones.js";
import { $ } from "./util.js";
import { cambiarVista, refrescar } from "./vistas.js";

export function activarEventos() {
  $("buscar").addEventListener("submit", async (e) => {
    e.preventDefault();
    const rid = $("rid").value.trim();
    if (!rid) return;
    $("error").textContent = "Buscando…";
    const r = await enviar("/api/buscar", { riot_id: rid });
    $("error").textContent = r.ok ? "" : r.error;
    if (r.ok) {
      $("rid").value = "";
      if (estado.vista !== "partida") cambiarVista("partida");
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
      estado.revisionAvisada = estado.actual && estado.actual.ultima_revision;
      estado.revisionVista = estado.revisionAvisada;
      cambiarVista("revisiones");
    } else if (b.dataset.revision) {
      estado.revisionVista = b.dataset.revision;
      pintarRevisiones();
    } else if (b.id === "cerrar-novedades") {
      await cerrarNovedades();
    } else if (b.dataset.minuto) {
      elegirMinuto(b);
    } else if (b.dataset.filtro) {
      filtrarMuertes(b);
    } else if (b.dataset.clip) {
      await abrirClip(b);
    } else if (b.id === "abrir-carpeta") {
      await abrirCarpeta(b);
    } else if (b.id === "salir-app") {
      await salirApp();
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
}

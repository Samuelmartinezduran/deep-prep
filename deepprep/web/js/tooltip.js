// Tooltip propio para los gráficos: sigue al ratón y no tapa la marca.
//
// El texto va en el atributo data-tip como JSON, nunca como HTML: una lista de líneas y cada línea una
// lista de trozos. Un trozo es un texto, o [estilo, texto] con estilo "b" (negrita) o "num" (cifra).
// Se pinta creando nodos con textContent, así que un nombre con "<" o "&" sale tal cual y no puede
// meter HTML en la página (antes el atributo, ya desescapado por el navegador, iba a innerHTML).
import { $, esc } from "./util.js";

const ESTILOS = { b: ["b", ""], num: ["span", "num"] };

// Atributo data-tip listo para una plantilla HTML: tip(["b", "top"], " · 4 de 7") o varias líneas con
// tipLineas([...], [...]).
export const tipLineas = (...lineas) => `data-tip="${esc(JSON.stringify(lineas))}"`;
export const tip = (...trozos) => tipLineas(trozos);

const trozo = (t) => {
  if (Array.isArray(t) && t.length === 2 && ESTILOS[t[0]]) {
    const [etiqueta, clase] = ESTILOS[t[0]];
    return { etiqueta, clase, texto: String(t[1] ?? "") };
  }
  return { texto: String(t ?? "") };
};

// Texto del atributo (ya desescapado, como lo da dataset.tip) -> líneas de trozos {etiqueta?, clase?, texto}.
// Si no es el JSON esperado, se enseña tal cual, como texto.
export function leerTip(texto) {
  let lineas = null;
  try {
    lineas = JSON.parse(texto);
  } catch {
    // texto suelto
  }
  if (!Array.isArray(lineas)) return [[{ texto: String(texto ?? "") }]];
  return lineas.map((linea) => (Array.isArray(linea) ? linea : [linea]).map(trozo));
}

// Pinta el tooltip en la caja solo con nodos: <b>, <span class="num">, <br> y texto.
export function pintarTip(caja, texto, doc = caja.ownerDocument) {
  const nodos = [];
  leerTip(texto).forEach((linea, i) => {
    if (i) nodos.push(doc.createElement("br"));
    for (const t of linea) {
      if (!t.etiqueta) {
        nodos.push(doc.createTextNode(t.texto));
        continue;
      }
      const el = doc.createElement(t.etiqueta);
      if (t.clase) el.className = t.clase;
      el.textContent = t.texto;
      nodos.push(el);
    }
  });
  caja.replaceChildren(...nodos);
}

export function activarTooltip() {
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest("[data-tip]");
    $("tip").hidden = !t;
    if (t) pintarTip($("tip"), t.dataset.tip);
  });
  document.addEventListener("mousemove", (e) => {
    const tip = $("tip");
    if (tip.hidden) return;
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    tip.style.transform = `translate(${x}px, ${e.clientY + 16}px)`;
  });
}

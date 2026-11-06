// Ayudas para las pruebas del panel: leer atributos de una plantilla HTML y un DOM mínimo para el tooltip.

// Lo que hace el navegador con las entidades de un atributo (solo las que usa esc()).
export const desescapar = (s) =>
  s.replace(/&(amp|lt|gt|quot|#39);/g, (_, e) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" })[e]);

// Valores (ya desescapados) de un atributo en un trozo de HTML, en orden.
export function atributos(html, nombre) {
  return [...html.matchAll(new RegExp(`\\s${nombre}="([^"]*)"`, "g"))].map((m) => desescapar(m[1]));
}

// Texto visible aproximado: sin etiquetas y con las entidades resueltas.
export const textoDe = (html) => desescapar(html.replace(/<[^>]*>/g, ""));

// DOM mínimo: elementos y nodos de texto que se pueden volcar a HTML (escapando el texto) para comparar.
// innerHTML y outerHTML revientan: el tooltip no los puede usar.
class Elemento {
  constructor(etiqueta) {
    this.tagName = etiqueta.toUpperCase();
    this.className = "";
    this.childNodes = [];
  }
  set textContent(v) {
    this.childNodes = [new Texto(String(v))];
  }
  get textContent() {
    return this.childNodes.map((n) => n.textContent).join("");
  }
  set innerHTML(_) {
    throw new Error("innerHTML no se puede usar en el tooltip");
  }
  set outerHTML(_) {
    throw new Error("outerHTML no se puede usar en el tooltip");
  }
  insertAdjacentHTML() {
    throw new Error("insertAdjacentHTML no se puede usar en el tooltip");
  }
  replaceChildren(...nodos) {
    this.childNodes = nodos;
  }
  get html() {
    const etiqueta = this.tagName.toLowerCase();
    const clase = this.className ? ` class="${this.className}"` : "";
    if (etiqueta === "br") return "<br>";
    return `<${etiqueta}${clase}>${this.childNodes.map((n) => n.html).join("")}</${etiqueta}>`;
  }
}

class Texto {
  constructor(datos) {
    this.data = datos;
  }
  get textContent() {
    return this.data;
  }
  get html() {
    return this.data.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}

export function documento() {
  const creados = [];
  return {
    creados,
    createElement(etiqueta) {
      const el = new Elemento(etiqueta);
      creados.push(el.tagName);
      return el;
    },
    createTextNode: (s) => new Texto(s),
  };
}

// Contenido de una caja como HTML (sin la propia caja).
export const htmlDe = (caja) => caja.childNodes.map((n) => n.html).join("");
export const caja = () => new Elemento("div");

// El logo es la Grieta en pequeño: líneas de top y bot, mid entre las dos bases, el río y tú en el centro.
// Es el mismo dibujo que el icono (herramientas/logo.py), sin el fondo.
export const LOGO = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><defs><mask id="logo-hueco"><rect width="32" height="32" fill="#fff"/><circle cx="16" cy="16" r="3.4" fill="#000"/></mask></defs>
  <path d="M9 9 23 23" stroke="#8b7cf6" stroke-opacity=".4" stroke-width="1.4" stroke-linecap="round" mask="url(#logo-hueco)"/>
  <rect x="6.8" y="6.8" width="18.4" height="18.4" rx="2.5" stroke="#8b7cf6" stroke-width="1.8"/>
  <rect x="6" y="20.5" width="5.5" height="5.5" rx="2.5" fill="#8b7cf6"/><rect x="20.5" y="6" width="5.5" height="5.5" rx="2.5" fill="#8b7cf6"/>
  <path d="M8.75 23.25 23.25 8.75" stroke="#8b7cf6" stroke-width="1.8" mask="url(#logo-hueco)"/><circle cx="16" cy="16" r="2.4" fill="#8b7cf6"/></svg>`;
// Iconos de línea, trazo 1.5, retícula de 16.
export const ICONO = {
  partida: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.75"/><circle cx="8" cy="8" r="2"/><path d="M8 .75v2.5M8 12.75v2.5M.75 8h2.5M12.75 8h2.5"/></svg>`,
  revisiones: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.75 3.25h10.5M2.75 8h10.5M2.75 12.75h6.5"/><path d="M11.5 11.25l1.25 1.5 2.25-3"/></svg>`,
  ajustes: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4h4.5M9.5 4H14M2 12h2.5M7.5 12H14"/><circle cx="8" cy="4" r="1.5"/><circle cx="6" cy="12" r="1.5"/></svg>`,
  buscar: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.75"/><path d="m10.5 10.5 3.75 3.75"/></svg>`,
  carpeta: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.75 4.25v8.5h12.5v-7H8L6.5 3.75H2.25z"/></svg>`,
  muerte: `<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7"/></svg>`,
  play: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.5v9l7-4.5z"/></svg>`,
};
// El logo pequeño de la cabecera del overlay.
export const LOGO_PEQUENO = LOGO.replace("<svg", '<svg width="18" height="18"');

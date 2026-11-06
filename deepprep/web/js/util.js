// Utilidades sin estado: escapar texto para HTML, formatos de cifras y fechas, nombres fijos.

// Todo texto que venga de la app (nombres de jugadores, de campeones...) pasa por aquí antes de ir a HTML.
export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const pct = (v, n) => (n ? Math.round((100 * v) / n) : 0);
export const miles = (n) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
export const coma = (x) => x.toFixed(1).replace(".", ",");
// Verde o rojo solo con muestra suficiente; el color describe al jugador, no a ti.
export const claseWr = (v, n) => (n < 5 ? "" : pct(v, n) >= 58 ? "bien" : pct(v, n) <= 42 ? "mal" : "");
export const minutos = (t) => {
  const [m, s] = String(t || "0:0").split(":").map(Number);
  return (m || 0) + (s || 0) / 60;
};
// Cifra ya formateada por la app -> número, para dibujar barras: "−150" -> -150, "6,8" -> 6.8, "64%" -> 64.
export const numero = (s) => Number(String(s).replace(/[^\d,.\-−+]/g, "").replace("−", "-").replace(",", "."));
// Minimapa de Data Dragon: cubre de (-120, -120) a (14870, 14980); el eje y de la imagen va hacia abajo.
export const enMapa = (x, y) => `left:${(((x + 120) / 14990) * 100).toFixed(2)}%;top:${((1 - (y + 120) / 15100) * 100).toFixed(2)}%`;
export const fecha = (ms) => new Date(ms).toLocaleString("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export const ROLES = { TOP: "top", JUNGLE: "jungle", MIDDLE: "middle", BOTTOM: "bottom", UTILITY: "utility" };
export const ROL_TXT = { TOP: "Top", JUNGLE: "Jungla", MIDDLE: "Mid", BOTTOM: "ADC", UTILITY: "Support" };
export const TITULOS = { partida: "Partida", revisiones: "Revisiones", ajustes: "Ajustes" };
export const NIVEL_TXT = { iron: "Hierro", bronze: "Bronce", silver: "Plata", gold: "Oro", platinum: "Platino", emerald: "Esmeralda", diamond: "Diamante", master: "Maestro", grandmaster: "Gran Maestro", challenger: "Aspirante" };
export const ligaTxt = (l) => `${NIVEL_TXT[l.nivel] || l.nivel}${["master", "grandmaster", "challenger"].includes(l.nivel) ? "" : ` ${l.rank}`} · ${l.lp} LP`;

// Elemento de la página por id (solo en el navegador).
export const $ = (id) => document.getElementById(id);

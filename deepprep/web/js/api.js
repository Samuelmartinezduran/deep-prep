// Llamadas a la app (el servidor local de deepprep/servidor.py).
//
// Ningún fallo se pierde: si no hay conexión, la app responde con un error HTTP o la respuesta no se
// entiende, pedir() y pedirTexto() lanzan un ErrorApi con un texto para el jugador, y enviar() devuelve
// {ok: false, error} como cualquier otro error de la app, para que cada pantalla lo enseñe donde ya
// enseña los suyos.

export const SIN_CONEXION = "Sin conexión con la app";
export const RESPUESTA_RARA = "La app ha mandado una respuesta que no se entiende";

export class ErrorApi extends Error {}

// Texto de una respuesta que no es 2xx: el error que manda la app ({"error": ...}) o el código HTTP.
async function motivo(r) {
  try {
    const datos = await r.json();
    if (datos && datos.error) return String(datos.error);
  } catch {
    // sin cuerpo JSON: vale el código
  }
  return `La app ha respondido con un error (${r.status})`;
}

// Cuerpo de la respuesta como texto; lanza ErrorApi si no llega o no es 2xx.
export async function pedirTexto(ruta, opciones) {
  let r;
  try {
    r = await fetch(ruta, opciones);
  } catch {
    throw new ErrorApi(SIN_CONEXION);
  }
  if (!r.ok) throw new ErrorApi(await motivo(r));
  try {
    return await r.text();
  } catch {
    throw new ErrorApi(SIN_CONEXION);
  }
}

// Respuesta JSON de la app; lanza ErrorApi si algo falla.
export async function pedir(ruta, opciones) {
  const texto = await pedirTexto(ruta, opciones);
  try {
    return JSON.parse(texto);
  } catch {
    throw new ErrorApi(RESPUESTA_RARA);
  }
}

// POST con JSON. Nunca lanza: los fallos vuelven como {ok: false, error}.
export async function enviar(ruta, cuerpo) {
  try {
    const r = await pedir(ruta, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo || {}) });
    return r && typeof r === "object" ? r : { ok: false, error: RESPUESTA_RARA };
  } catch (e) {
    if (!(e instanceof ErrorApi)) throw e;
    return { ok: false, error: e.message };
  }
}

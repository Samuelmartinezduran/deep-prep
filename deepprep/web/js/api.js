// Llamadas a la app (el servidor local de deepprep/servidor.py).

// POST con JSON; devuelve la respuesta de la app.
export async function enviar(ruta, cuerpo) {
  const r = await fetch(ruta, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo || {}) });
  return r.json();
}

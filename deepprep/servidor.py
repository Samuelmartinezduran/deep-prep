"""Canal de control local entre copias de la app. Solo escucha en 127.0.0.1.

Desde la 2.1 la interfaz no pasa por aquí (habla con la app en el mismo proceso, nativa/puente.py). Lo que queda:
- POST /api/mostrar: otra copia arrancada con el acceso directo pide que esta enseñe su ventana (y el puerto ocupado
  es lo que le dice que ya hay una en marcha).
- POST /api/salir: el instalador pide que se cierre la copia instalada antes de copiar encima.
- GET /api/estado: el estado de la app, solo para leerlo (diagnóstico; ?vista=overlay no cuenta como mirar el panel).
"""

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .tipos import AppDelPanel, Json, Resultado


def _mostrar(app: AppDelPanel, cuerpo: Json) -> Resultado:
    """Otra copia de la app arrancada con el acceso directo pide que esta enseñe su ventana."""
    mostrar = getattr(app, "al_mostrar", None)
    if mostrar:
        mostrar()
    return {"ok": bool(mostrar)}


# Ruta -> qué hace (con la URL de la petición en GET y con el cuerpo JSON ya leído en POST).
Accion = Callable[[AppDelPanel, Any], Any]
API_GET: dict[str, Accion] = {
    "/api/estado": lambda app, url: app.estado(contar="vista=overlay" not in url.query),
}
API_POST: dict[str, Accion] = {
    "/api/salir": lambda app, cuerpo: app.salir(),
    "/api/mostrar": _mostrar,
}


class _Respuestas(BaseHTTPRequestHandler):
    """Lo común a todas las peticiones: cómo se responde y cuáles vienen de fuera de la app."""

    permitidos: frozenset[str] = frozenset()  # Host (y Origin) de la propia app

    def log_message(self, *args: Any) -> None:
        pass

    def _json(self, obj: Any, codigo: int = 200) -> None:
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _ajena(self) -> bool:
        """Peticiones que no vienen de la propia app (otra web abierta en el navegador, DNS rebinding)."""
        if self.headers.get("Host") not in self.permitidos:
            return True
        origen = self.headers.get("Origin")
        return bool(origen) and urlparse(origen).netloc not in self.permitidos


class Servidor(ThreadingHTTPServer):
    # En Windows, reutilizar la dirección dejaría arrancar dos copias en el mismo puerto.
    allow_reuse_address = False
    daemon_threads = True


def crear(app: AppDelPanel, puerto: int) -> Servidor:
    """El canal de control en 127.0.0.1:puerto (con 0, el puerto libre que dé Windows: srv.server_address[1])."""

    class Manejador(_Respuestas):
        def do_GET(self) -> None:
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            url = urlparse(self.path)
            if url.path in API_GET:
                return self._json(API_GET[url.path](app, url))
            self._json({"error": "no existe"}, 404)

        def do_POST(self) -> None:
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = json.loads(self.rfile.read(largo) or b"{}")
            except ValueError:
                return self._json({"error": "petición mal formada"}, 400)
            accion = API_POST.get(urlparse(self.path).path)
            if accion:
                return self._json(accion(app, cuerpo))
            self._json({"error": "no existe"}, 404)

    srv = Servidor(("127.0.0.1", puerto), Manejador)
    puerto = srv.server_address[1]
    Manejador.permitidos = frozenset({f"127.0.0.1:{puerto}", f"localhost:{puerto}"})
    return srv

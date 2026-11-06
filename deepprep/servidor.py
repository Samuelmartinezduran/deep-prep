"""Servidor web local del panel. Solo escucha en 127.0.0.1."""

import json
import re
import urllib.request
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import config
from .riot import USER_AGENT
from .tipos import AppDelPanel, Json, Resultado

ARCHIVOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/estilo.css": ("estilo.css", "text/css; charset=utf-8"),
}
TIPOS = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".woff2": "font/woff2",
    ".css": "text/css; charset=utf-8",
    ".ico": "image/x-icon",
}
# Imágenes de campeones de Data Dragon: se bajan una vez y se sirven desde disco (el overlay no espera a la red).
URL_DDRAGON = {
    "campeon": "https://ddragon.leagueoflegends.com/cdn/{v}/img/champion/{n}.png",
    "splash": "https://ddragon.leagueoflegends.com/cdn/img/champion/centered/{n}_0.jpg",
    # El minimapa no cambia con los parches; esta es la última versión que Data Dragon publicó.
    "mapa": "https://ddragon.leagueoflegends.com/cdn/6.8.1/img/map/{n}.png",
}
EXT_DDRAGON = {"campeon": ".png", "splash": ".jpg", "mapa": ".png"}
RUTA_IMAGENES = config.DATOS / "imagenes"
NOMBRE_SEGURO = re.compile(r"^[A-Za-z0-9]+$")


def imagen_ddragon(tipo, clave, version):
    """Bytes de la imagen (de disco o recién bajada), o None."""
    if tipo not in URL_DDRAGON or not NOMBRE_SEGURO.match(clave):
        return None
    ext = EXT_DDRAGON[tipo]
    destino = RUTA_IMAGENES / tipo / (version if tipo == "campeon" else "") / (clave + ext)
    if destino.is_file():
        return destino.read_bytes()
    try:
        pet = urllib.request.Request(URL_DDRAGON[tipo].format(v=version, n=clave), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(pet, timeout=10) as r:
            datos = r.read()
    except OSError:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return datos


def _mostrar(app: AppDelPanel, cuerpo: Json) -> Resultado:
    """Otra copia de la app arrancada con el acceso directo pide que esta enseñe su ventana."""
    mostrar = getattr(app, "al_mostrar", None)
    if mostrar:
        mostrar()
    return {"ok": bool(mostrar)}


# La API del panel: ruta -> qué hace (con la URL de la petición en GET y con el cuerpo JSON ya leído en POST).
Accion = Callable[[AppDelPanel, Any], Any]
API_GET: dict[str, Accion] = {
    "/api/estado": lambda app, url: app.estado(contar="vista=overlay" not in url.query),
    "/api/revisiones": lambda app, url: app.revisiones(),
    "/api/revision": lambda app, url: app.revision(parse_qs(url.query).get("id", [""])[0]),
    "/api/ajustes": lambda app, url: app.ajustes(),
}
API_POST: dict[str, Accion] = {
    "/api/buscar": lambda app, cuerpo: app.buscar(str(cuerpo.get("riot_id", ""))),
    "/api/volver": lambda app, cuerpo: app.volver(),
    "/api/clave": lambda app, cuerpo: app.poner_clave(str(cuerpo.get("clave", ""))),
    "/api/carpeta": lambda app, cuerpo: app.abrir_carpeta(str(cuerpo.get("id", ""))),
    "/api/novedades": lambda app, cuerpo: app.actualizador.novedades_vistas(),
    "/api/clip": lambda app, cuerpo: app.abrir_clip(str(cuerpo.get("id", "")), cuerpo.get("i")),
    "/api/ajustes": lambda app, cuerpo: app.guardar_ajustes(cuerpo),
    "/api/salir": lambda app, cuerpo: app.salir(),
    "/api/mostrar": _mostrar,
}


class _Respuestas(BaseHTTPRequestHandler):
    """Lo común a todas las peticiones: cómo se responde y cuáles vienen de fuera del panel."""

    permitidos: frozenset[str] = frozenset()  # Host (y Origin) del propio panel

    def log_message(self, *args: Any) -> None:
        pass

    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, guardar: bool = False) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "max-age=86400" if guardar else "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj: Any, codigo: int = 200) -> None:
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _ajena(self) -> bool:
        """Peticiones que no vienen del propio panel (otra web abierta en el navegador, DNS rebinding)."""
        if self.headers.get("Host") not in self.permitidos:
            return True
        origen = self.headers.get("Origin")
        return bool(origen) and urlparse(origen).netloc not in self.permitidos


class Servidor(ThreadingHTTPServer):
    # En Windows, reutilizar la dirección dejaría arrancar dos copias en el mismo puerto.
    allow_reuse_address = False
    daemon_threads = True


def crear(app: AppDelPanel, puerto: int, post: Mapping[str, Accion] | None = None) -> Servidor:
    """El servidor del panel en 127.0.0.1:puerto (con 0, el puerto libre que dé Windows: srv.server_address[1]).

    post: acciones de más, además de las de API_POST (las de la barra de la demo).
    """
    acciones = {**API_POST, **(post or {})}

    class Manejador(_Respuestas):
        def do_GET(self) -> None:
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            url = urlparse(self.path)
            ruta = url.path
            if ruta in API_GET:
                return self._json(API_GET[ruta](app, url))
            if ruta in ARCHIVOS:
                nombre, tipo = ARCHIVOS[ruta]
                return self._enviar(200, (config.RUTA_WEB / nombre).read_bytes(), tipo)
            # Módulos del panel (web/js/): solo nombres de letras y números, sin carpetas ni otras extensiones.
            if ruta.startswith("/js/") and ruta.endswith(".js") and NOMBRE_SEGURO.fullmatch(ruta[4:-3]):
                archivo = config.RUTA_WEB / "js" / ruta[4:]
                if archivo.is_file():
                    return self._enviar(200, archivo.read_bytes(), "text/javascript; charset=utf-8")
            if ruta.startswith(("/fuentes/", "/img/")):
                archivo = (config.RUTA_WEB / ruta.lstrip("/")).resolve()
                if archivo.is_relative_to(config.RUTA_WEB) and archivo.is_file() and archivo.suffix in TIPOS:
                    return self._enviar(200, archivo.read_bytes(), TIPOS[archivo.suffix], guardar=True)
            partes = ruta.split("/")
            if len(partes) == 4 and partes[1] == "ddragon":
                datos = imagen_ddragon(partes[2], partes[3].rsplit(".", 1)[0], app.datos.version)
                if datos:
                    return self._enviar(200, datos, TIPOS[EXT_DDRAGON[partes[2]]], guardar=True)
            self._json({"error": "no existe"}, 404)

        def do_POST(self) -> None:
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = json.loads(self.rfile.read(largo) or b"{}")
            except ValueError:
                return self._json({"error": "petición mal formada"}, 400)
            accion = acciones.get(urlparse(self.path).path)
            if accion:
                return self._json(accion(app, cuerpo))
            self._json({"error": "no existe"}, 404)

    srv = Servidor(("127.0.0.1", puerto), Manejador)
    puerto = srv.server_address[1]
    Manejador.permitidos = frozenset({f"127.0.0.1:{puerto}", f"localhost:{puerto}"})
    return srv

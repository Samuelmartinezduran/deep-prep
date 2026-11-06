"""Servidor web local del panel. Solo escucha en 127.0.0.1."""

import json
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config
from .riot import USER_AGENT

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


def crear(app, puerto):
    permitidos = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _enviar(self, codigo, cuerpo, tipo, guardar=False):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "max-age=86400" if guardar else "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, obj, codigo=200):
            self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _ajena(self):
            """Peticiones que no vienen del propio panel (otra web abierta en el navegador, DNS rebinding)."""
            if self.headers.get("Host") not in permitidos:
                return True
            origen = self.headers.get("Origin")
            return bool(origen) and urlparse(origen).netloc not in permitidos

        def do_GET(self):
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            url = urlparse(self.path)
            ruta = url.path
            if ruta == "/api/estado":
                return self._json(app.estado(contar="vista=overlay" not in url.query))
            if ruta == "/api/revisiones":
                return self._json(app.revisiones())
            if ruta == "/api/revision":
                return self._json(app.revision(parse_qs(url.query).get("id", [""])[0]))
            if ruta == "/api/ajustes":
                return self._json(app.ajustes())
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

        def do_POST(self):
            if self._ajena():
                return self._json({"error": "origen no permitido"}, 403)
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = json.loads(self.rfile.read(largo) or b"{}")
            except ValueError:
                return self._json({"error": "petición mal formada"}, 400)
            ruta = urlparse(self.path).path
            if ruta == "/api/buscar":
                return self._json(app.buscar(str(cuerpo.get("riot_id", ""))))
            if ruta == "/api/volver":
                return self._json(app.volver())
            if ruta == "/api/clave":
                return self._json(app.poner_clave(str(cuerpo.get("clave", ""))))
            if ruta == "/api/carpeta":
                return self._json(app.abrir_carpeta(str(cuerpo.get("id", ""))))
            if ruta == "/api/novedades":
                return self._json(app.actualizador.novedades_vistas())
            if ruta == "/api/clip":
                return self._json(app.abrir_clip(str(cuerpo.get("id", "")), cuerpo.get("i")))
            if ruta == "/api/ajustes":
                return self._json(app.guardar_ajustes(cuerpo))
            if ruta == "/api/salir":
                return self._json(app.salir())
            if ruta == "/api/mostrar":
                # Otra copia de la app arrancada con el acceso directo pide que esta enseñe su ventana.
                mostrar = getattr(app, "al_mostrar", None)
                if mostrar:
                    mostrar()
                return self._json({"ok": bool(mostrar)})
            self._json({"error": "no existe"}, 404)

    class Servidor(ThreadingHTTPServer):
        # En Windows, reutilizar la dirección dejaría arrancar dos copias en el mismo puerto.
        allow_reuse_address = False
        daemon_threads = True

    return Servidor(("127.0.0.1", puerto), Manejador)

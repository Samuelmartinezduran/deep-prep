"""Sirve el panel con un estado guardado, para diseñarlo y revisarlo sin partida.

Uso: py herramientas/maqueta.py [maquetas/partida.json] [--modo previa|seleccion|carga|juego] [--puerto 5252]
El estado sale de herramientas/simular_propia.py (lo guarda en herramientas/maquetas/partida.json).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gzip  # noqa: E402

from porofesor import analisis as an  # noqa: E402
from porofesor import config, servidor  # noqa: E402
from porofesor import revision as rv  # noqa: E402
from porofesor.app import App  # noqa: E402
from porofesor import duelos as du  # noqa: E402
from porofesor.recolector import BaseDuelos  # noqa: E402


AQUI = Path(__file__).parent
DATOS_PRUEBA = AQUI.parent / "tests" / "datos"


def opcion(nombre, defecto):
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv else defecto


def _gz(nombre):
    with gzip.open(DATOS_PRUEBA / nombre, "rt", encoding="utf-8") as f:
        return json.load(f)


class AppMaqueta:
    """Estado fijo para el panel; revisiones, tendencias y ajustes salen de la app real (solo lectura)."""

    def __init__(self, estado, modo):
        self.base = estado
        self.modo = modo
        self.real = App(cfg=config.cargar(), grabador=False, duelos=BaseDuelos())  # con cfg pasada no escribe config.json
        self.real._comprobar_clave()
        self.datos = self.real.datos
        # Una revisión de ejemplo con la partida real de las pruebas (Diana contra Master Yi).
        partida = an.reducir_partida(_gz("partida.json.gz"))
        yo = next(j for j in partida["jug"] if j["campeon"] == 131)
        prevision = {"gank": {"linea": "top", "veces": 3, "n": 5}, "lineas": [{"linea": "bot", "veredicto": "Aquí se equivocan"}]}
        self.ejemplo = rv.revisar(partida, rv.reducir_linea_completa(_gz("linea.json.gz")), yo["puuid"], self.datos.nombre, prevision, 14)
        self.ejemplo.update(carpeta=str(Path.home() / "Videos" / "LoL-coach" / "2026-10-12_partida1"), icono=self.datos.icono(131),
                            lp={"lp": 53, "nivel": "emerald", "rank": "I", "cambio": -19})
        for m in self.ejemplo["muertes"][:3]:
            m["clip"] = "maqueta.mp4"

    def duelo_maqueta(self):
        """Tu duelo de la maqueta. Si ese duelo aún tiene pocas partidas, para diseñar se usan las de tu
        campeón contra cualquier rival de su posición (solo en la maqueta)."""
        p = self.base["panel"]
        por_nombre = {v["nombre"]: k for k, v in self.datos.campeones.items()}
        yo = next(f for f in p["equipos"]["aliado"] if f["soy_yo"])
        rival = next((f for f in p["equipos"]["rival"] if f["rol"] == yo["rol"]), None)
        a, b = por_nombre.get(yo["campeon"]), por_nombre.get(rival["campeon"]) if rival else None
        d = self.real.duelo(a, yo["rol"], b)
        if d and d["poco"] and "--duelo-real" not in sys.argv:
            base = self.real.duelos
            todos = [r for rb in base.cuantos(a, yo["rol"]) for r in base.duelo(a, yo["rol"], rb, excluir=set(self.real.cuentas))]
            d = dict(d, **du.analizar(todos, base.de(set(self.real.cuentas), a, yo["rol"]), yo["campeon"], rival["campeon"], yo["rol"],
                                      self.datos.objeto, self.datos.runa))
        return d

    def revisiones(self):
        r = self.real.revisiones()
        claves = ("id", "fecha", "cola", "duracion", "gana", "campeon", "campeon_id", "kda", "icono")
        r["lista"] = [dict({k: self.ejemplo[k] for k in claves}, lp=-19)] + r["lista"]
        r["muertes"] = rv.mapa_muertes([self.ejemplo]) + r["muertes"]
        return r

    def revision(self, id_):
        return self.ejemplo if id_ == self.ejemplo["id"] else self.real.revision(id_)

    def ajustes(self):
        return self.real.ajustes()

    def guardar_ajustes(self, cambios):
        return {"ok": True}

    def abrir_carpeta(self, id_):
        return {"ok": False, "error": "Maqueta: no abre carpetas"}

    def mapa_jungla(self):
        """La maqueta se guardó antes del mapa del jungla rival: se calcula con sus partidas de la caché (una vez)."""
        if hasattr(self, "_mapa"):
            return self._mapa
        self._mapa = {}
        try:
            p = self.base["panel"]
            jr = next(f for f in p["equipos"]["rival"] if f["rol"] == "JUNGLE")
            puuid = self.real.cliente.cuenta_por_riot_id(jr["nombre"], jr["tag"])["puuid"]
            partidas = self.real.cache.partidas_de(puuid)
            lineas = {m["id"]: self.real.cache.linea(m["id"]) for m in partidas if self.real.cache.linea(m["id"])}
            campeon = {v["nombre"]: k for k, v in self.datos.campeones.items()}[jr["campeon"]]
            self._mapa = an.perfil_jungla(puuid, partidas, lineas, campeon, 200).get("mapa") or {}
        except Exception as e:  # noqa: BLE001 - la maqueta sigue sin mapa
            print(f"Maqueta sin mapa del jungla: {e!r}")
        return self._mapa

    def seleccion(self):
        """Selección de campeón a partir de la maqueta: tú con tu campeón y el rival de tu posición ya elegido."""
        p = self.base["panel"]
        por_nombre = {v["nombre"]: k for k, v in self.datos.campeones.items()}
        yo = next(f for f in p["equipos"]["aliado"] if f["soy_yo"])
        rival = next(f for f in p["equipos"]["rival"] if f["rol"] == yo["rol"])
        a, b = por_nombre[yo["campeon"]], por_nombre[rival["campeon"]]
        return {
            "duelo": self.duelo_maqueta(),
            "pool": self.real.pool_contra(yo["rol"], b, 420),
            "pos": an.NOMBRE_POS[yo["rol"]],
            "mio": {"nombre": yo["campeon"], "icono": self.datos.icono(a), "splash": ""},
            "historial": p["historial"],
            "notas": [],
        }

    def estado(self, contar=True):
        if self.modo == "seleccion":
            return dict(self.base, modo="previa", fase="ChampSelect", fase_txt="Selección de campeón", panel=None, seleccion=self.seleccion())
        e = dict(self.base, modo=self.modo)
        if "--novedades" in sys.argv:
            # Cómo lo ven los amigos: una versión nueva ya descargada y las novedades de la que acaban de instalar.
            e["version"] = {"version": "1.0.0", "nueva": "1.0.1", "lista": True, "error": ""}
            e["novedades"] = {"version": "1.0.0", "notas": "Interfaz nueva y más datos para jugar mejor.\n"
                              "- Tu pool contra el rival en la selección de campeón\n"
                              "- Mapa de dónde está el jungla rival en sus primeros minutos\n"
                              "- Clips de cada muerte en la revisión"}
        if e.get("panel"):
            jungla = e["panel"].get("jungla")
            if jungla and "mapa" not in jungla:
                jungla = dict(jungla, mapa=self.mapa_jungla())
            e["panel"] = dict(e["panel"], duelo=self.duelo_maqueta(), jungla=jungla)
            e["panel"] = App._para_el_modo(self, e["panel"])
        return e

    def buscar(self, rid):
        return {"ok": False, "error": "Maqueta: sin búsquedas"}

    def volver(self):
        return {"ok": True}

    def poner_clave(self, clave):
        return {"ok": False, "error": "Maqueta"}


def main():
    libres = [a for a in sys.argv[1:] if not a.startswith("--") and a not in (opcion("--modo", ""), opcion("--puerto", ""))]
    archivo = Path(libres[0]) if libres else AQUI / "maquetas" / "partida.json"
    if not archivo.is_absolute() and not archivo.exists():
        archivo = AQUI / archivo
    estado = json.loads(archivo.read_text(encoding="utf-8"))
    puerto = int(opcion("--puerto", "5252"))
    app = AppMaqueta(estado, opcion("--modo", estado.get("modo") or "carga"))
    srv = servidor.crear(app, puerto)
    print(f"Maqueta en http://127.0.0.1:{puerto}/ (modo {app.modo})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

"""Lo que se cambia desde los ajustes del panel: qué se puede tocar, cómo se comprueba y tus notas por campeón."""

from typing import Any

from .comparador import COMPARAR_CON
from .overlay import parsear_atajo

# Lo que el panel puede leer y cambiar de config.json.
EDITABLES = (
    "cuentas",
    "recordatorios",
    "notas",
    "grabar",
    "overlay",
    "atajo_overlay",
    "overlay_opacidad",
    "siempre_en_marcha",
    "comparar_con",
    "referencias",
    "perfil_base",
    "grabacion_codificador",
    "grabacion_max_gb",
)


class Ajustes:
    """Lee y guarda los ajustes del panel.

    arranque_windows(encendido) pone o quita el arranque con Windows y devuelve un texto de error o ''.
    al_guardar(nuevo) se llama con lo que ha cambiado, ya guardado, para que la app lo aplique.
    """

    def __init__(self, configuracion, datos, comparador, actualizador, arranque_windows, al_guardar):
        self.configuracion = configuracion
        self.cfg = configuracion.valores
        self.datos = datos
        self.comparador = comparador
        self.actualizador = actualizador
        self.arranque_windows = arranque_windows
        self._al_guardar = al_guardar

    def leer(self):
        campeones = sorted(({"id": i, "nombre": c["nombre"]} for i, c in self.datos.campeones.items()), key=lambda c: c["nombre"])
        partidas, perfil_partidas = self.comparador.partidas_de_referencias()
        return {
            **{k: self.cfg.get(k) for k in EDITABLES},
            "campeones": campeones,
            "opciones_comparar": COMPARAR_CON,
            "referencias_partidas": partidas,
            "perfil_partidas": perfil_partidas,
            "version": self.actualizador.estado,
        }

    def guardar(self, cambios):
        nuevo: dict[str, Any] = {}
        try:
            if "cuentas" in cambios:
                cuentas = [str(c).strip() for c in cambios["cuentas"] if str(c).strip()]
                if not cuentas or any("#" not in c for c in cuentas):
                    return {"ok": False, "error": "Las cuentas van como Nombre#TAG, y al menos una."}
                nuevo["cuentas"] = cuentas
            if "recordatorios" in cambios:
                nuevo["recordatorios"] = [str(r).strip()[:160] for r in cambios["recordatorios"] if str(r).strip()][:8]
            if "notas" in cambios:
                nuevo["notas"] = {str(int(k)): str(v).strip()[:300] for k, v in dict(cambios["notas"]).items() if str(v).strip()}
            for k in ("grabar", "overlay", "siempre_en_marcha"):
                if k in cambios:
                    nuevo[k] = bool(cambios[k])
            if "comparar_con" in cambios:
                if cambios["comparar_con"] not in COMPARAR_CON:
                    return {"ok": False, "error": "Esa referencia no existe."}
                nuevo["comparar_con"] = cambios["comparar_con"]
            if "perfil_base" in cambios:
                nuevo["perfil_base"] = str(cambios["perfil_base"]).strip()
                if nuevo["perfil_base"]:
                    error = self.comparador.resolver_referencia(nuevo["perfil_base"])
                    if error:
                        return {"ok": False, "error": error}
            if (nuevo.get("comparar_con") or self.cfg.get("comparar_con")) == "perfil" and not nuevo.get(
                "perfil_base", self.cfg.get("perfil_base")
            ):
                return {"ok": False, "error": "Para compararte con un jugador, escribe su Nombre#TAG en el perfil de referencia."}
            if "referencias" in cambios:
                refs = {}
                for campeon, rid in dict(cambios["referencias"]).items():
                    rid = str(rid).strip()
                    if not rid:
                        continue
                    error = self.comparador.resolver_referencia(rid)
                    if error:
                        return {"ok": False, "error": error}
                    refs[str(int(campeon))] = rid
                nuevo["referencias"] = refs
            if "grabacion_codificador" in cambios:
                if cambios["grabacion_codificador"] not in ("auto", "cpu"):
                    return {"ok": False, "error": "Codificador desconocido."}
                nuevo["grabacion_codificador"] = cambios["grabacion_codificador"]
            if "grabacion_max_gb" in cambios:
                nuevo["grabacion_max_gb"] = max(0, int(float(cambios["grabacion_max_gb"] or 0)))
            if "atajo_overlay" in cambios:
                if not parsear_atajo(str(cambios["atajo_overlay"])):
                    return {"ok": False, "error": "No entiendo ese atajo. Ejemplos: ctrl+tab, alt+x, f9."}
                nuevo["atajo_overlay"] = str(cambios["atajo_overlay"]).strip().lower()
            if "overlay_opacidad" in cambios:
                nuevo["overlay_opacidad"] = min(1.0, max(0.4, float(cambios["overlay_opacidad"])))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Algún valor no tiene el formato esperado."}
        if "siempre_en_marcha" in nuevo and nuevo["siempre_en_marcha"] != self.cfg.get("siempre_en_marcha"):
            error = self.arranque_windows(nuevo["siempre_en_marcha"])
            if error:
                return {"ok": False, "error": error}
        self.cfg.update(nuevo)
        self.configuracion.guardar()
        self._al_guardar(nuevo)
        return {"ok": True}

    def notas_de(self, campeones, rivales=()):
        """Tus notas de los campeones que hay en la partida (las escribiste tú antes de jugar)."""
        notas = self.cfg.get("notas") or {}
        vistos, out = set(), []
        for c in campeones:
            if c and c not in vistos and notas.get(str(c)):
                vistos.add(c)
                out.append(
                    {"campeon": self.datos.nombre(c), "icono": self.datos.icono(c), "texto": notas[str(c)], "rival": c in rivales}
                )
        return out

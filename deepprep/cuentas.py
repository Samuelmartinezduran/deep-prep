"""Tu clave de la API de Riot y tus cuentas: cuáles son, su PUUID y si la clave vale."""

import time

from . import config
from .riot import ClaveInvalida, ErrorRiot

# Con la clave rechazada, cada cuánto se vuelve a probar (Riot tarda un par de minutos en activar una nueva).
REINTENTO_CLAVE_S = 20


class Cuentas:
    """Tus cuentas (puuid -> 'Nombre#TAG' en propias) y si la clave vale (error_clave vacío).

    El PUUID depende de la clave de aplicación: si al probar la clave cambia el de tu cuenta principal, la caché ya
    no vale y se vacía. al_recuperar_clave se llama cuando una clave rechazada vuelve a valer.
    """

    def __init__(self, configuracion, cache, cliente, al_recuperar_clave=lambda: None):
        self.configuracion = configuracion
        self.cfg = configuracion.valores
        self.cache = cache
        self.cliente = cliente
        self.propias = {}  # puuid -> "Nombre#TAG" de las cuentas propias
        self.error_clave = ""
        self.ultima_prueba = 0.0  # última vez que se probó la clave
        self._al_recuperar = al_recuperar_clave

    def comprobar_clave(self):
        """Prueba la clave con la cuenta principal. Si el PUUID ha cambiado, la caché ya no vale."""
        self.ultima_prueba = time.time()
        if not self.cfg["cuentas"]:
            # Primera vez: las cuentas salen del cliente al abrirlo. De momento basta con saber que la clave vale.
            self.cliente.comprobar()
            return
        principal = self.cfg["cuentas"][0]
        nombre, _, tag = principal.partition("#")
        cuenta = self.cliente.cuenta_por_riot_id(nombre, tag)
        if cuenta:
            guardada = self.cache.kv_get(f"cuenta:{principal.lower()}")
            if guardada and guardada["puuid"] != cuenta["puuid"]:
                print("La clave pertenece a otra aplicación: los PUUID han cambiado y se vacía la caché")
                self.cache.vaciar()
                self.propias.clear()
            puuid, visible = self._registrar(principal, cuenta)
            self.propias[puuid] = visible
        for rid in self.cfg["cuentas"][1:]:
            self.apuntar(rid)

    def reprobar_clave(self, ahora):
        """Con la clave rechazada, la vuelve a probar si ya toca. False si aún no toca; si sigue sin valer, lanza."""
        if ahora - self.ultima_prueba < REINTENTO_CLAVE_S:
            return False
        self.comprobar_clave()
        self.clave_recuperada()
        return True

    def clave_recuperada(self):
        self.error_clave = ""
        self._al_recuperar()

    def poner_clave(self, clave):
        clave = clave.strip()
        if not clave.startswith("RGAPI-"):
            return {"ok": False, "error": "Eso no parece una clave de Riot (empiezan por RGAPI-)."}
        config.guardar_clave(clave)
        try:
            self.comprobar_clave()
        except ClaveInvalida:
            self.error_clave = "Clave guardada. Riot tarda un par de minutos en activar las nuevas; se reintenta sola."
            return {"ok": True, "pendiente": True}
        except ErrorRiot as e:
            return {"ok": False, "error": str(e)}
        self.clave_recuperada()
        return {"ok": True}

    def _registrar(self, rid, cuenta):
        visible = f"{cuenta.get('gameName', rid.partition('#')[0])}#{cuenta.get('tagLine', rid.partition('#')[2])}"
        self.cache.kv_set(f"cuenta:{rid.lower()}", {"puuid": cuenta["puuid"], "rid": visible})
        return cuenta["puuid"], visible

    def resolver(self, rid):
        """Riot ID -> (puuid, 'Nombre#TAG') o None si no existe."""
        guardada = self.cache.kv_get(f"cuenta:{rid.lower()}")
        if guardada:
            return guardada["puuid"], guardada["rid"]
        nombre, _, tag = rid.partition("#")
        if not nombre or not tag:
            return None
        cuenta = self.cliente.cuenta_por_riot_id(nombre.strip(), tag.strip())
        return self._registrar(rid, cuenta) if cuenta else None

    def apuntar(self, rid, recordar=False):
        """Resuelve una cuenta propia y la apunta como tal; con recordar, también en config.json. Devuelve su PUUID."""
        r = self.resolver(rid)
        if not r:
            return None
        self.propias[r[0]] = r[1]
        if recordar and r[1].lower() not in {c.lower() for c in self.cfg["cuentas"]}:
            self.cfg["cuentas"] = [*self.cfg["cuentas"], r[1]]
            self.configuracion.guardar()
        return r[0]

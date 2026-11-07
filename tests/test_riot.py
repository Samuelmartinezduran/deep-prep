"""Pruebas del control de cuota, con un reloj falso que avanza al 'dormir', y de los reintentos ante fallos de red."""

import gzip
import http.client
import json
import unittest
from unittest import mock

from deepprep.riot import Cliente, ErrorRiot, Limitador


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def ahora(self):
        return self.t

    def dormir(self, s):
        self.t += s


def limitador():
    reloj = Reloj()
    return Limitador(reloj=reloj.ahora, dormir=reloj.dormir), reloj


class Cuota(unittest.TestCase):
    def test_rafaga_por_segundo(self):
        lim, reloj = limitador()
        for _ in range(18):
            lim.adquirir("h")
        self.assertEqual(reloj.t, 1000.0)
        lim.adquirir("h")
        self.assertGreaterEqual(reloj.t, 1001.0)

    def test_ventana_de_dos_minutos(self):
        lim, reloj = limitador()
        for _ in range(96):
            lim.adquirir("h")
        antes = reloj.t
        self.assertLess(antes - 1000.0, 10)  # las 96 primeras salen en pocos segundos
        lim.adquirir("h")
        self.assertGreaterEqual(reloj.t, 1120.0)  # la 97 espera a que caduque la primera
        self.assertEqual(lim.estado("h")["tope"], 96)

    def test_hosts_independientes(self):
        lim, reloj = limitador()
        for _ in range(18):
            lim.adquirir("euw1")
        lim.adquirir("europe")
        self.assertEqual(reloj.t, 1000.0)

    def test_el_fondo_deja_hueco_y_se_puede_pausar(self):
        lim, reloj = limitador()
        for _ in range(40):
            lim.adquirir("h", fondo=True)
        self.assertLess(reloj.t - 1000.0, 5)
        lim.adquirir("h")  # una tarea normal sigue pasando al momento
        self.assertLess(reloj.t - 1000.0, 5)
        lim.adquirir("h", fondo=True)
        self.assertGreaterEqual(reloj.t, 1120.0)

        lim, reloj = limitador()
        lim.tope_fondo = 0
        vueltas = []

        def cancelada():
            vueltas.append(1)
            return len(vueltas) > 3

        self.assertFalse(lim.adquirir("h", fondo=True, cancelada=cancelada))
        self.assertEqual(lim.estado("h")["usadas"], 0)

    def test_cancelar_mientras_espera(self):
        lim, _ = limitador()
        for _ in range(96):
            lim.adquirir("h")
        self.assertFalse(lim.adquirir("h", cancelada=lambda: True))

    def test_sincroniza_con_la_cuenta_de_riot(self):
        lim, _reloj = limitador()
        lim.adquirir("h")
        lim.sincronizar("h", "90:120,3:1")  # Riot ha visto 90: la app se reinició y perdió la cuenta
        self.assertEqual(lim.estado("h")["usadas"], 90)
        lim.sincronizar("h", "5:120,1:1")  # nunca baja la cuenta local
        self.assertEqual(lim.estado("h")["usadas"], 90)
        lim.sincronizar("h", None)
        lim.sincronizar("h", "basura")
        self.assertEqual(lim.estado("h")["usadas"], 90)

    def test_penalizacion_por_429(self):
        lim, reloj = limitador()
        lim.penalizar("h", 30)
        lim.adquirir("h")
        self.assertGreaterEqual(reloj.t, 1030.0)


class Respuesta:
    """Lo que devuelve urlopen: el cuerpo (o la excepción que lanza al leerlo) y sus cabeceras."""

    def __init__(self, cuerpo, gzip_=False):
        self.cuerpo = cuerpo
        self.headers = {"Content-Encoding": "gzip"} if gzip_ else {}

    def read(self):
        if isinstance(self.cuerpo, Exception):
            raise self.cuerpo
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Reintentos(unittest.TestCase):
    """Riot a veces corta la respuesta a medias (pasó en una partida de prueba): se reintenta como un fallo de red."""

    def setUp(self):
        cfg = {"plataforma": "euw1", "region": "europe"}
        self.cliente = Cliente(cfg, lambda: "RGAPI-prueba", Limitador(reloj=lambda: 0.0, dormir=lambda s: None))
        parche = mock.patch("deepprep.riot.time.sleep")
        parche.start()
        self.addCleanup(parche.stop)

    def pedir(self, respuestas):
        with mock.patch("deepprep.riot.urllib.request.urlopen", side_effect=respuestas) as urlopen:
            try:
                return self.cliente._get(self.cliente.region, "/lol/match/v5/matches/EUW1_1"), urlopen.call_count
            except ErrorRiot as e:
                return e, urlopen.call_count

    def test_respuesta_cortada_se_reintenta(self):
        datos = {"metadata": {"matchId": "EUW1_1"}}
        cortada = Respuesta(http.client.IncompleteRead(b'{"meta', 100))
        resultado, llamadas = self.pedir([cortada, Respuesta(json.dumps(datos).encode())])
        self.assertEqual(resultado, datos)
        self.assertEqual(llamadas, 2)

    def test_gzip_sin_acabar_se_reintenta(self):
        entero = gzip.compress(b'{"ok": 1}')
        resultado, llamadas = self.pedir([Respuesta(entero[:-6], gzip_=True), Respuesta(entero, gzip_=True)])
        self.assertEqual(resultado, {"ok": 1})
        self.assertEqual(llamadas, 2)

    def test_si_siempre_se_corta_es_un_error_de_riot(self):
        cortadas = [Respuesta(http.client.IncompleteRead(b"", 10)) for _ in range(4)]
        resultado, llamadas = self.pedir(cortadas)
        self.assertIsInstance(resultado, ErrorRiot)
        self.assertIn("Sin conexión", str(resultado))
        self.assertEqual(llamadas, 4)


if __name__ == "__main__":
    unittest.main()

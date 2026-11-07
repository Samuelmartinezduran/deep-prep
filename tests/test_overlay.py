"""Cuándo se ve el panel encima del juego, sin Windows de por medio."""

import tempfile
import unittest
from pathlib import Path

from deepprep import overlay


class AppFalsa:
    def __init__(self):
        self.cfg = {"overlay": True, "atajo_overlay": "ctrl+tab", "ruta_lol": "."}
        self.fase = "InProgress"
        self.modo = "carga"

    def actualizar_modo(self):
        pass


class VentanaFalsa:
    def __init__(self):
        self.visible = False
        self.cambios = 0

    def mostrar(self):
        self.visible, self.cambios = True, self.cambios + 1

    def ocultar(self):
        self.visible, self.cambios = False, self.cambios + 1


def montar(pulsadas=(), juego=True):
    app, ventana = AppFalsa(), VentanaFalsa()
    teclas = set(pulsadas)
    ctl = overlay.Controlador(app, ventana, tecla_pulsada=lambda vk: vk in teclas, juego_delante=lambda: juego, reloj=lambda: 0.0)
    ctl._modo_juego = overlay.MODO_SIN_BORDES
    return app, ventana, ctl, teclas


class Atajo(unittest.TestCase):
    def test_parsear(self):
        self.assertEqual(overlay.parsear_atajo("Ctrl + Tab"), [0x11, 0x09])
        self.assertEqual(overlay.parsear_atajo("shift+f2"), [0x10, 0x71])
        self.assertEqual(overlay.parsear_atajo("alt+x"), [0x12, ord("X")])
        self.assertIsNone(overlay.parsear_atajo("ctrl+nada"))
        self.assertIsNone(overlay.parsear_atajo(""))


class Visibilidad(unittest.TestCase):
    def test_carga_se_ve_sola_y_en_juego_solo_con_el_atajo(self):
        app, ventana, ctl, teclas = montar()
        ctl.paso()
        self.assertTrue(ventana.visible)
        app.modo = "juego"
        ctl.paso()
        self.assertFalse(ventana.visible)
        teclas.update({0x11, 0x09})
        ctl.paso()
        self.assertTrue(ventana.visible)
        teclas.discard(0x09)  # soltar una de las dos teclas basta para esconderlo
        ctl.paso()
        self.assertFalse(ventana.visible)
        ctl.paso()
        self.assertEqual(ventana.cambios, 4)  # sin cambios, no se toca la ventana

    def test_fuera_de_partida_nunca(self):
        app, ventana, ctl, _teclas = montar(pulsadas={0x11, 0x09})
        app.modo = "previa"
        ctl.paso()
        self.assertFalse(ventana.visible)

    def test_sin_ventana_del_juego_o_en_pantalla_completa_no_se_ve(self):
        _, ventana, ctl, _ = montar(juego=False)
        ctl.paso()
        self.assertFalse(ventana.visible)
        _, ventana, ctl, _ = montar()
        ctl._modo_juego = "0"
        ctl.paso()
        self.assertFalse(ventana.visible)

    def test_con_alt_tab_a_otra_ventana_no_tapa_nada(self):
        # Visto en la prueba de la 2.0.0: la vista de carga se quedaba encima de lo que abrías con Alt+Tab.
        app, ventana, delante, teclas = AppFalsa(), VentanaFalsa(), [True], set()
        ctl = overlay.Controlador(
            app, ventana, tecla_pulsada=lambda vk: vk in teclas, juego_delante=lambda: delante[0], reloj=lambda: 0.0
        )
        ctl._modo_juego = overlay.MODO_SIN_BORDES
        ctl.paso()
        self.assertTrue(ventana.visible)
        delante[0] = False
        ctl.paso()
        self.assertFalse(ventana.visible)
        app.modo = "juego"
        teclas.update({0x11, 0x09})  # Ctrl+Tab en el navegador, con el juego detrás
        ctl.paso()
        self.assertFalse(ventana.visible)
        delante[0] = True  # vuelves al juego con el atajo pulsado
        ctl.paso()
        self.assertTrue(ventana.visible)

    def test_apagado_en_la_configuracion(self):
        app, ventana, ctl, _ = montar()
        app.cfg["overlay"] = False
        ctl.paso()
        self.assertFalse(ventana.visible)


class ModoVentana(unittest.TestCase):
    def test_lee_game_cfg(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Config").mkdir()
            (Path(d) / "Config" / "game.cfg").write_text("[General]\nWindowMode=2\nWidth=1920\n[HUD]\nx=1\n", encoding="utf-8")
            self.assertEqual(overlay.modo_ventana(d), "2")
            self.assertIsNone(overlay.modo_ventana(Path(d) / "no-existe"))


if __name__ == "__main__":
    unittest.main()

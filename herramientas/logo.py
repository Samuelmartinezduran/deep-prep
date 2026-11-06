"""Genera el icono de Deep Prep (deepprep/web/icono.ico) y una vista previa.

El dibujo es la Grieta reducida a lo esencial: el borde son las líneas de top y bot, la diagonal es mid,
las esquinas son las dos bases y el punto del centro eres tú. Violeta de la app sobre fondo oscuro.
Uso: py herramientas/logo.py [vista_previa.png]
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
VIOLETA = (139, 124, 246, 255)
FONDO = (19, 18, 28, 255)
TAMANOS = (16, 20, 24, 32, 40, 48, 64, 128, 256)
AUMENTO = 8  # se dibuja a 8 veces el tamaño y se reduce: bordes suaves


def dibujar(tam):
    s = tam * AUMENTO
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 32  # rejilla de 32 x 32
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=7 * u, fill=FONDO)
    # En tamaños pequeños, trazos más gruesos para que no se pierdan.
    grueso = (2.4 if tam <= 20 else 2.0 if tam <= 32 else 1.6) * u
    a, b = 6 * u, 26 * u  # el cuadrado de las líneas de top y bot
    # El río, más tenue, de esquina a esquina por el otro lado (en los tamaños muy pequeños no se ve: fuera).
    if tam > 20:
        rio = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(rio).line([a + 3 * u, a + 3 * u, b - 3 * u, b - 3 * u], fill=(*VIOLETA[:3], 90), width=round(grueso * 0.6))
        img.alpha_composite(rio)
    d.rounded_rectangle([a, a, b, b], radius=2.5 * u, outline=VIOLETA, width=round(grueso))
    # Las dos bases, metidas en sus esquinas, y mid uniéndolas.
    lado = 5.5 * u
    d.rounded_rectangle([a, b - lado, a + lado, b], radius=2.5 * u, fill=VIOLETA)
    d.rounded_rectangle([b - lado, a, b, a + lado], radius=2.5 * u, fill=VIOLETA)
    d.line([a + lado * 0.5, b - lado * 0.5, b - lado * 0.5, a + lado * 0.5], fill=VIOLETA, width=round(grueso))
    # Tú: punto en el centro, separado de mid por un anillo del color del fondo.
    c, r = 16 * u, 2.4 * u
    hueco = r + grueso * 0.55
    d.ellipse([c - hueco, c - hueco, c + hueco, c + hueco], fill=FONDO)
    d.ellipse([c - r, c - r, c + r, c + r], fill=VIOLETA)
    return img.resize((tam, tam), Image.LANCZOS)


def main():
    imagenes = [dibujar(t) for t in TAMANOS]
    destino = RAIZ / "deepprep" / "web" / "icono.ico"
    imagenes[-1].save(destino, format="ICO", sizes=[(t, t) for t in TAMANOS], append_images=imagenes[:-1])
    print(destino)
    if len(sys.argv) > 1:
        # Vista previa: todos los tamaños, sobre fondo claro y oscuro (como en la barra de tareas).
        ancho = sum(TAMANOS) + 16 * (len(TAMANOS) + 1)
        hoja = Image.new("RGBA", (ancho, 2 * 256 + 48), (8, 9, 10, 255))
        ImageDraw.Draw(hoja).rectangle([0, 256 + 24, ancho, 2 * 256 + 48], fill=(240, 240, 240, 255))
        x = 16
        for t, im in zip(TAMANOS, imagenes, strict=True):
            hoja.alpha_composite(im, (x, 8 + (256 - t) // 2))
            hoja.alpha_composite(im, (x, 256 + 32 + (256 - t) // 2))
            x += t + 16
        hoja.save(sys.argv[1])
        print(sys.argv[1])


if __name__ == "__main__":
    main()

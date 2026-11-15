"""La interfaz de la app, con Qt Quick: ventanas de QML que dibuja la gráfica (hasta la 2.0, un panel web en WebView2).

- ventanas.py: las ventanas (la principal y la de encima del juego), su arranque y su cierre.
- vistas.py: lo que se escribe en cada vista, en Python puro; el QML solo lo coloca.
- puente.py: lo que la interfaz lee de la app y lo que le pide.
- marco.py: la barra de arriba es la de la app, y Windows sigue haciendo lo suyo (encajar, Win+flechas, sombra...).
- oro.py: la diferencia de oro de la partida, minuto a minuto, para el gráfico.
- __main__.py: py -m deepprep.nativa, la interfaz con la demo para diseñar.
- qml/DeepPrep: la interfaz. fuentes/: Space Grotesk e IBM Plex Mono en TTF (Qt no lee WOFF2), con su licencia (OFL).
"""

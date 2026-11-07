# Registro de cambios

Los cambios importantes de cada versión. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones, [versionado semántico](https://semver.org/lang/es/). Hasta la 1.0.2 la app se llamaba Porofesor.

## [2.0.0] - 2026-11-06

Porofesor pasa a llamarse Deep Prep y se rehace por dentro para publicar el código. Lo que ve el jugador no cambia, salvo los arreglos de abajo.

### Cambiado

- El proyecto se llama Deep Prep: paquete `deepprep` (`py -m deepprep`), `DeepPrep.exe`, programa en `%LOCALAPPDATA%\Programs\DeepPrep`, datos en `%LOCALAPPDATA%\DeepPrep` y acceso directo **Deep Prep**. Las actualizaciones llegan de `Samuelmartinezduran/deep-prep`.
- Las copias de Porofesor 1.0.x pasan solas: una versión puente, publicada donde ellas buscan actualizaciones, lleva un `Porofesor.exe` que es una copia de `DeepPrep.exe`. La 2.0.0 se instala en la carpeta nueva, cambia los accesos directos, borra el programa viejo si no corre nada desde él y, antes de abrir bases o registros, muda los datos (clave, ajustes, notas y revisiones).
- El panel web pasa de un `app.js` de 960 líneas a módulos ES en `deepprep/web/js`, sin paso de compilación ni dependencias de npm.
- La clase `App` (unas 1 000 líneas) se parte en piezas que recibe ya hechas: `cuentas`, `partidas`, `comparador`, `ajustes`, `revisiones`, `seleccion` y `vigia`. Ninguna función pasa de 50 líneas, el código repetido va a `almacen.py`, `sistema.py` y `constantes.py`, y ningún módulo toca lo privado de otro. Lo que sale no cambia: lo fijan las pruebas de caracterización.
- El registro usa `logging`: un logger por módulo y la fecha, la hora, el nivel y el módulo en cada línea de `deepprep.log`.
- Todo el código de la app lleva tipos y mypy lo revisa en modo estricto. `tipos.py` nombra los datos que van de un módulo a otro: alias con nombre para el JSON de Riot y `TypedDict` para lo pequeño y fijo.

### Añadido

- Modo demo: `py -m deepprep --demo` (o `DeepPrep.exe --demo`) abre la app con una partida de ejemplo y una barra para cambiar de escena, sin el LoL ni clave de Riot. Lo que se guarda va a una carpeta temporal que se borra al salir. Admite `--sin-ventana`, `--puerto` y `--escena`. `herramientas/maqueta.py` pasa a ser la demo con opciones para diseñar.
- Licencia MIT (`LICENSE`, y `LICENSE.txt` en el zip). La de las fuentes del panel, la SIL Open Font License, va en `deepprep/web/fuentes/OFL.txt`.
- `pyproject.toml` con las herramientas de desarrollo: ruff, mypy, coverage con un mínimo del 70 %, `.editorconfig` y `.gitattributes`.
- CI en GitHub Actions: formato, lint, tipos y pruebas con cobertura en Windows con Python 3.14, y las pruebas del panel con Node 24.
- Pruebas de caracterización (12) antes de reordenar el código, y pruebas del panel con `node --test`.
- `herramientas/publicar.py` pasa lo mismo que la CI antes de publicar: formato, lint, tipos, pruebas con cobertura y `node --test`.
- Datos de las pruebas, las maquetas y la demo anonimizados con `herramientas/anonimizar.py`: los Riot ID, los PUUID y los id de invocador, de cuenta y de partida son inventados.
- README, este registro y `docs/ARQUITECTURA.md`.

### Corregido

- `config.json` y `clave.txt` se escriben de golpe (temporal, `fsync` y `os.replace`). Antes, una escritura a medias se leía como «sin configuración» y el siguiente guardado pisaba tus cuentas. Ahora uno roto se aparta y se recupera de la última copia buena, y uno que Windows tiene ocupado un momento (el antivirus) ya no cuenta como roto.
- Los clips y el «dónde en el vídeo» de las muertes valen para todas las series de la grabación: si ffmpeg se relanzaba a media partida, las muertes de después se quedaban sin clip o apuntaban a otro trozo. El recorte de dos trozos ya no falla con un apóstrofo en la ruta (`C:\Users\O'Neill`).
- La caché en memoria crecía sin parar con la app siempre en marcha. Ahora guarda las últimas 2 000 partidas y 300 líneas de tiempo, unos 55 MB como mucho.
- Los cerrojos de la grabación y del recolector se cierran siempre, también cuando ya había otro proceso con el cerrojo.
- Los errores de red y HTTP se ven en el panel. Antes el botón se quedaba igual sin conexión y un 4xx o 5xx se leía como una respuesta buena.
- Sin red, los retratos de campeón que no llegan dejan su hueco en lugar del icono de imagen rota.
- Una respuesta de Riot cortada a medias (`IncompleteRead`, o un gzip sin acabar) se reintenta como cualquier fallo de red. Antes no se reintentaba: el recolector paraba un minuto y, si pasaba al bajar la partida recién acabada, esa revisión se perdía. Salió en la partida de prueba de la 2.0.0.

### Seguridad

- El tooltip volvía a meter como HTML un texto ya escapado, así que un nombre con `<img onerror=...>` se ejecutaba al pasar el ratón. Ahora el contenido va como JSON y se pinta con `textContent`; las pruebas del panel comprueban que no se vuelva a usar `innerHTML`.

## [1.0.2] - 2026-10-29

### Corregido

- Las actualizaciones ya no cierran la app delante de ti: solo se instalan con la ventana escondida y fuera de partida.
- Tras instalarse, la versión nueva se abre a la vista si alguien acababa de abrir la vieja; con el PC recién encendido, escondida.
- Abrir el `.exe` de un zip viejo ya no instala encima una versión anterior: abre la que ya está instalada.
- La instalación copia encima en lugar de borrar antes y, si falla, lo apunta en el registro y vuelve a abrir la versión que había.

## [1.0.1] - 2026-10-29

### Añadido

- Selección de campeón: tu pool contra el rival de tu posición, con el porcentaje de victorias en Master+ y tus partidas.
- Mapa de dónde suele estar el jungla rival entre el 2:00 y el 6:00, girado al lado del mapa que le toca. Solo antes de jugar: en partida se quita.
- Revisión: línea de tiempo de objetivos y muertes, un clip de cada muerte sacado de la grabación y los LP ganados o perdidos. En Revisiones, un mapa de dónde mueres y el resumen del día.
- Aviso de versión nueva y, al abrirla, sus novedades hasta pulsar «Entendido».

### Cambiado

- Interfaz rehecha: barra lateral con navegación, estado y cuota de Riot; tablas de equipos con columnas rotuladas, y ajustes por grupos. Superficies planas, un solo acento (violeta, `#8b7cf6`) y el color siempre con una cifra o una palabra al lado. Logo nuevo.

### Corregido

- Guardar los ajustes fallaba si había jugadores de referencia por campeón.
- Los nombres que se escriben de derecha a izquierda ya no desordenan las líneas.

## [1.0.0] - 2026-10-14

Primera versión, como Porofesor.

### Añadido

- Panel de la partida en vivo: los diez jugadores en la pantalla de carga y, ya jugando, encima del juego mientras se mantiene un atajo.
- Duelos de línea medidos en partidas de Master o más.
- Revisión de tu partida al acabar.
- Grabación integrada de cada partida.
- Actualizaciones automáticas desde GitHub Releases: la versión nueva espera a que se cierre la vieja y se instala ella.

[2.0.0]: https://github.com/Samuelmartinezduran/deep-prep/releases/tag/v2.0.0

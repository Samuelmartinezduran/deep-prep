# Deep Prep

Panel para el League of Legends pensado para jugadores de rango alto: antes de cada partida te enseña cómo va cada jugador, cómo juega el jungla rival (y dónde suele estar en sus primeros minutos) y cómo suele ir tu duelo contra tu rival directo, con datos de partidas de Master o más. En la selección de campeón compara tus campeones contra el rival de tu posición. En partida puedes volver a verlo con **Ctrl+Tab**. Al acabar, graba la partida y te hace una revisión: dónde moriste, por qué, qué se perdió por esa muerte, un clip de cada muerte y los LP que ganaste o perdiste.

## Instalarla

1. Descarga `DeepPrep-x.y.z.zip` de la última versión (abajo, en **Releases**), descomprímelo y abre `DeepPrep.exe`.
2. Windows avisará de que es una app desconocida (no está firmada). Pulsa **Más información → Ejecutar de todas formas**.
3. Se instala sola, deja un acceso directo en el escritorio y arranca con Windows en segundo plano. Las actualizaciones también llegan solas: la app avisa cuando hay una versión nueva y, al instalarla, te enseña qué ha cambiado.
4. A partir de ahí ábrela siempre con el acceso directo **Deep Prep** del escritorio. La carpeta que descomprimiste ya no hace falta: puedes borrarla.

## ¿Tenías Porofesor?

Es la misma app: hasta la versión 1.0.2 se llamaba Porofesor. No tienes que hacer nada: se actualiza sola a Deep Prep, se lleva tus datos (clave, ajustes, notas y revisiones) a la carpeta nueva y cambia el acceso directo **Porofesor** del escritorio por uno de **Deep Prep**.

## Tu clave de Riot (obligatoria)

La app pide los datos a Riot con **tu propia clave**. Es gratis:

1. Entra en [developer.riotgames.com](https://developer.riotgames.com/) con tu cuenta del LoL.
2. Copia la **Development API Key** y pégala en la app (sale un aviso arriba para pegarla).
3. Esa clave caduca cada 24 horas. Para no renovarla cada día, en la misma web pulsa **Register Product → Personal API Key** y rellénalo; si te piden una descripción, vale esta:

   > Third-party desktop app (Deep Prep, made by Samuel Martínez) that I run only for myself on my own PC. It shows pre-game information about the players in my live game (ranks and champion stats from match history), a post-game review of my own matches, and stats from high-elo matches. The data is only shown to me. APIs: Account-V1, Spectator-V5, League-V4, Match-V5, Champion-Mastery-V4.

   Cuando te la aprueben, pega la clave nueva en la app y ya no caduca.

**No compartas tu clave con nadie** (ni la pegues en Discord): es personal y Riot la puede anular.

## Para que salga encima del juego

Pon el LoL en **ventana sin bordes**: Opciones → Vídeo → Modo de ventana → Sin bordes. Sale solo en la pantalla de carga y, ya jugando, mientras mantienes **Ctrl+Tab** (se cambia en Ajustes). Si cambias a otra ventana con Alt+Tab, se esconde.

## Grabaciones

Cada partida en la Grieta se graba en **Vídeos\LoL-coach** (unos 2 GB por partida). Al pasar de 50 GB se borran las más viejas; en Ajustes puedes cambiar el límite, grabar con la gráfica o el procesador, o apagar la grabación.

## ¿Cumple las normas de Riot?

Está diseñada para cumplir las normas de Riot para apps de terceros. La app es una ventana aparte: no toca el juego, no lee su memoria y no intercepta el teclado. Durante la partida solo enseña datos de antes de empezar, como exige Riot a las apps de terceros (las mismas normas que Porofessor, Blitz o Mobalytics).

## Quitarla

En Ajustes desmarca **Siempre en marcha** y pulsa **Cerrar Deep Prep del todo**. Luego borra las carpetas `%LOCALAPPDATA%\Programs\DeepPrep` (el programa) y `%LOCALAPPDATA%\DeepPrep` (tus datos) y el acceso directo del escritorio.

---

Deep Prep isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

Deep Prep es software libre con licencia MIT (`LICENSE.txt`, junto a `DeepPrep.exe`).

Incluye [FFmpeg](https://ffmpeg.org/) (licencia GPL v3; build «essentials» de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)) para grabar la pantalla. Su licencia va en `ffmpeg/LICENSE` dentro del zip y su código fuente está en [ffmpeg.org](https://ffmpeg.org/download.html#get-sources) y en [github.com/FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg).

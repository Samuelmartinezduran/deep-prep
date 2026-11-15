pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// El jungla rival: quién es, dónde estaba a cada minuto en sus partidas anteriores (antes de jugar) y lo que suele
// hacer (vistas.jungla). También tu rival de línea si no juegas jungla (vistas.rival_linea: con su título, sin mapa).
Caja {
    id: jungla

    property var datos
    property string minuto: datos && datos.mapa ? datos.mapa.inicial : ""

    titulo: datos && datos.titulo ? datos.titulo : "Jungla rival"
    sub: datos && !datos.vacio ? (datos.sub || "de sus partidas anteriores; posición una vez por minuto") : ""
    onDatosChanged: if (datos && datos.mapa && !datos.mapa.puntos[minuto])
        minuto = datos.mapa.inicial

    Text {
        visible: !!jungla.datos && !!jungla.datos.vacio
        text: jungla.datos && jungla.datos.vacio ? jungla.datos.vacio : ""
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
    }
    Row {
        visible: !!jungla.datos && !jungla.datos.vacio
        spacing: 12
        bottomPadding: 16

        Retrato {
            anchors.verticalCenter: parent.verticalCenter
            tam: 48
            fuente: jungla.datos && !jungla.datos.vacio ? jungla.datos.retrato : ""
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: jungla.anchoDentro - 60

            Text {
                text: jungla.datos ? jungla.datos.campeon || "" : ""
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 18
                font.weight: Font.DemiBold
                font.letterSpacing: -0.18
            }
            Rico {
                width: parent.width
                text: jungla.datos ? jungla.datos.nota || "" : ""
                color: Tema.texto3
                font.pixelSize: 12
            }
        }
    }
    Row {
        visible: !!jungla.datos && !jungla.datos.vacio
        width: jungla.anchoDentro
        spacing: 24

        Column {
            id: mapaJungla

            visible: !!jungla.datos && !!jungla.datos.mapa
            width: visible ? Math.min(280, jungla.anchoDentro * 0.4) : 0
            spacing: 8

            Selector {
                width: parent.width
                repartir: true
                opciones: jungla.datos && jungla.datos.mapa ? jungla.datos.mapa.minutos.map(m => ({
                            id: m,
                            txt: m + ":00"
                        })) : []
                actual: jungla.minuto
                onElegir: id => jungla.minuto = id
            }
            Mapa {
                width: parent.width
                colorPunto: Tema.rival
                tamPunto: 8
                puntos: jungla.datos && jungla.datos.mapa ? (jungla.datos.mapa.puntos[jungla.minuto] || []).map(xy => ({
                            xy: xy
                        })) : []
            }
            Text {
                width: parent.width
                text: jungla.datos && jungla.datos.mapa ? `Cada punto es una de sus ${(jungla.datos.mapa.puntos[jungla.minuto] || []).length} partidas: dónde estaba al ${jungla.minuto}:00, ya girado al lado en que juega hoy.` : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
        Tarjetas {
            width: jungla.anchoDentro - (mapaJungla.visible ? mapaJungla.width + 24 : 0)
            columns: mapaJungla.visible ? 2 : 3
            lista: jungla.datos && jungla.datos.tarjetas ? jungla.datos.tarjetas : []
        }
    }
}

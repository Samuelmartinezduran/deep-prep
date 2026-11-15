pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Las novedades de la versión recién instalada (vistas.novedades), hasta que se pulsa «Entendido».
Rectangle {
    id: nov

    property var datos

    signal cerrada

    height: cuerpo.implicitHeight + 40
    color: Tema.panel

    Rectangle {
        width: 2
        height: parent.height
        color: Tema.acento
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Tema.linea2
    }
    Column {
        x: 32
        y: 20
        width: 220
        spacing: 4

        Etiqueta {
            text: "Novedades"
        }
        Text {
            text: nov.datos ? "Deep Prep " + nov.datos.version : ""
            color: Tema.texto
            font.family: Tema.sans
            font.pixelSize: 18
            font.weight: Font.DemiBold
            font.letterSpacing: -0.18
        }
    }
    Column {
        id: cuerpo

        x: 32 + 220 + 24
        y: 20
        width: Math.min(720, nov.width - x - entendido.width - 64)
        spacing: 8

        Repeater {
            model: nov.datos ? nov.datos.parrafos : []

            Text {
                required property string modelData

                width: cuerpo.width
                text: modelData
                color: Tema.texto2
                font.family: Tema.sans
                font.pixelSize: 14
                wrapMode: Text.Wrap
            }
        }
        Repeater {
            model: nov.datos ? nov.datos.puntos : []

            Row {
                id: punto

                required property string modelData

                leftPadding: 4
                spacing: 10

                Text {
                    text: "•"
                    color: Tema.texto3
                    font.pixelSize: 14
                }
                Text {
                    width: cuerpo.width - 24
                    text: punto.modelData
                    color: Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
            }
        }
    }
    Boton {
        id: entendido

        anchors.right: parent.right
        anchors.rightMargin: 32
        y: 20
        texto: "Entendido"
        onPulsar: puente.llamar("novedadesVistas", [], r => {
            if (r.ok)
                nov.cerrada();
            else
                entendido.texto = r.error;
        })
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tus notas por campeón (las escribes en Ajustes): salen cuando ese campeón está en la partida.
Caja {
    id: cajaNotas

    property var lista: []

    visible: lista.length > 0
    titulo: "Tus notas"

    Repeater {
        model: cajaNotas.lista

        Item {
            id: nota

            required property var modelData
            required property int index

            width: cajaNotas.anchoDentro
            height: Math.max(24, cuerpoNota.implicitHeight) + (nota.index > 0 ? 20 : 10)

            Rectangle {
                visible: nota.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Retrato {
                y: nota.index > 0 ? 10 : 0
                tam: 24
                fuente: nota.modelData.retrato
            }
            Column {
                id: cuerpoNota

                x: 36
                y: nota.index > 0 ? 10 : 0
                width: parent.width - 36

                Text {
                    text: nota.modelData.campeon
                    color: nota.modelData.rival ? Tema.rival : Tema.aliado
                    font.family: Tema.sans
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: nota.modelData.texto
                    color: Tema.texto2
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}

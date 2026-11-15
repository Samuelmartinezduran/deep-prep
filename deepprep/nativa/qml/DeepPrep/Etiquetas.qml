pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Etiquetas de jugador: punto + palabra (verde si es un punto fuerte, rojo si flojo), con su explicación al pasar.
Flow {
    id: etiquetas

    property var lista: []
    property int tamLetra: 12

    spacing: 14

    Repeater {
        model: etiquetas.lista

        Item {
            id: etq

            required property var modelData

            implicitWidth: filaEtq.implicitWidth
            implicitHeight: filaEtq.implicitHeight

            Row {
                id: filaEtq

                spacing: 6

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6
                    height: 6
                    radius: 3
                    color: etq.modelData.tono === "fuerte" ? Tema.bien : etq.modelData.tono === "flojo" ? Tema.mal : Tema.texto3
                }
                Text {
                    text: etq.modelData.t
                    color: Tema.texto2
                    font.family: Tema.sans
                    font.pixelSize: etiquetas.tamLetra
                    font.weight: Font.Medium
                }
            }
            Tip {
                texto: etq.modelData.d || ""
            }
        }
    }
}

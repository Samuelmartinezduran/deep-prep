pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Botones de una sola elección (minutos del mapa del jungla, filtros de muertes, escenas de la demo).
Rectangle {
    id: selector

    property var opciones: [] // [{id, txt}]
    property string actual: ""
    property bool repartir: false // todos del mismo ancho, ocupando la caja
    property bool mono: true

    signal elegir(string id)

    implicitWidth: fila.implicitWidth + 4
    implicitHeight: 30
    color: Tema.fondo
    border.color: Tema.linea2
    radius: Tema.radio

    Row {
        id: fila

        x: 2
        y: 2

        Repeater {
            model: selector.opciones

            Rectangle {
                id: opcion

                required property var modelData
                readonly property bool activa: modelData.id === selector.actual

                width: selector.repartir ? (selector.width - 4) / selector.opciones.length : txt.implicitWidth + (selector.mono ? 20 : 24)
                height: 26
                radius: 2
                color: activa ? Tema.panel2 : "transparent"
                border.color: activa ? Tema.linea2 : "transparent"

                Text {
                    id: txt

                    anchors.centerIn: parent
                    text: opcion.modelData.txt
                    color: opcion.activa || zona.containsMouse ? Tema.texto : Tema.texto3
                    font.family: selector.mono ? Tema.mono : Tema.sans
                    font.pixelSize: selector.mono ? 12 : 13
                    font.weight: Font.Medium
                }
                MouseArea {
                    id: zona

                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: selector.elegir(opcion.modelData.id)
                }
            }
        }
    }
}

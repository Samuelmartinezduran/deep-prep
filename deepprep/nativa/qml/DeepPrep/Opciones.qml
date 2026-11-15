pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Una sola elección entre unas pocas opciones con texto largo (con quién compararte): una lista con su marca, en vez
// de un desplegable, para que se lean todas a la vez.
Column {
    id: opciones

    property var lista: [] // [{k, v}]
    property string actual: ""

    signal elegir(string k)

    spacing: 2

    Repeater {
        model: opciones.lista

        Rectangle {
            id: opcion

            required property var modelData
            readonly property bool activa: modelData.k === opciones.actual

            width: opciones.width
            height: 34
            radius: Tema.radio
            color: activa ? Tema.panel2 : zona.containsMouse ? Tema.hover : "transparent"
            border.color: activa ? Tema.linea2 : "transparent"

            Rectangle {
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 14
                radius: 7
                color: "transparent"
                border.color: opcion.activa ? Tema.acento : Tema.linea3
                border.width: 1.5

                Rectangle {
                    visible: opcion.activa
                    anchors.centerIn: parent
                    width: 6
                    height: 6
                    radius: 3
                    color: Tema.acento
                }
            }
            Text {
                x: 34
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 44
                text: opcion.modelData.v
                color: opcion.activa ? Tema.texto : Tema.texto2
                font.family: Tema.sans
                font.pixelSize: 14
                elide: Text.ElideRight
            }
            MouseArea {
                id: zona

                anchors.fill: parent
                hoverEnabled: true
                onClicked: opciones.elegir(opcion.modelData.k)
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Las teclas de un atajo: CTRL + TAB como teclas dibujadas.
Row {
    id: teclas

    property var lista: []

    spacing: 4

    Repeater {
        model: teclas.lista

        Rectangle {
            id: tecla

            required property string modelData

            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            width: Math.max(20, txt.implicitWidth + 12)
            height: 19
            radius: 3
            color: Tema.panel2
            border.color: Tema.linea2

            Rectangle {
                // El borde de abajo más grueso, como una tecla.
                anchors.bottom: parent.bottom
                x: 1
                width: parent.width - 2
                height: 1
                color: Tema.linea2
            }
            Text {
                id: txt

                anchors.centerIn: parent
                anchors.verticalCenterOffset: -1
                text: tecla.modelData
                color: Tema.texto
                font.family: Tema.mono
                font.pixelSize: 11
                font.weight: Font.Medium
            }
        }
    }
}

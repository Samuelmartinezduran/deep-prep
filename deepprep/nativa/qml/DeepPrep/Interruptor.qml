import QtQuick
import DeepPrep

// Interruptor con su texto (.interruptor): violeta encendido. Se cambia con el ratón o con Espacio.
Item {
    id: interruptor

    property bool activo: false
    property string texto: ""

    signal cambiado(bool activo)

    implicitWidth: fila.implicitWidth
    implicitHeight: 22
    activeFocusOnTab: true
    Keys.onSpacePressed: {
        interruptor.activo = !interruptor.activo;
        interruptor.cambiado(interruptor.activo);
    }

    Row {
        id: fila

        anchors.verticalCenter: parent.verticalCenter
        spacing: 12

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 32
            height: 18
            radius: 9
            color: interruptor.activo ? Tema.acento : Tema.panel2
            border.color: interruptor.activo ? Tema.acento : Tema.linea3

            Behavior on color {
                ColorAnimation {
                    duration: 150
                }
            }
            Rectangle {
                x: interruptor.activo ? 16 : 2
                anchors.verticalCenter: parent.verticalCenter
                width: 12
                height: 12
                radius: 6
                color: interruptor.activo ? "#0e0b1f" : Tema.texto2

                Behavior on x {
                    NumberAnimation {
                        duration: 150
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: interruptor.texto
            color: Tema.texto
            font.family: Tema.sans
            font.pixelSize: 14
        }
    }
    Rectangle {
        // Foco del teclado.
        visible: interruptor.activeFocus
        x: -3
        y: (parent.height - 24) / 2
        width: 38
        height: 24
        radius: 12
        color: "transparent"
        border.color: Tema.acento
    }
    MouseArea {
        anchors.fill: parent
        onClicked: {
            interruptor.forceActiveFocus();
            interruptor.activo = !interruptor.activo;
            interruptor.cambiado(interruptor.activo);
        }
    }
}

import QtQuick
import DeepPrep

// Botón del panel: 32 px de alto, fondo panel2 y línea fina; el primario, en violeta.
Rectangle {
    id: boton

    property string texto
    property string icono: ""
    property bool primario: false
    property bool pequeno: false

    signal pulsar

    implicitWidth: fila.implicitWidth + (pequeno ? 20 : 24)
    implicitHeight: pequeno ? 28 : 32
    radius: Tema.radio
    color: primario ? (zona.containsMouse ? Tema.acento2 : Tema.acento) : (zona.containsMouse ? Tema.hover : Tema.panel2)
    border.width: 1
    border.color: primario ? color : (zona.containsMouse ? Tema.linea3 : Tema.linea2)

    Behavior on color {
        ColorAnimation {
            duration: 150
            easing.type: Easing.OutCubic
        }
    }

    Row {
        id: fila

        anchors.centerIn: parent
        anchors.verticalCenterOffset: zona.pressed ? 1 : 0
        spacing: boton.pequeno ? 6 : 8

        Icono {
            anchors.verticalCenter: parent.verticalCenter
            visible: boton.icono !== ""
            nombre: boton.icono
            tam: boton.pequeno ? 12 : 16
            color: etiqueta.color
        }
        Text {
            id: etiqueta

            anchors.verticalCenter: parent.verticalCenter
            text: boton.texto
            color: boton.primario ? "#0e0b1f" : Tema.texto
            font.family: Tema.sans
            font.pixelSize: boton.pequeno ? 13 : 14
            font.weight: boton.primario ? Font.DemiBold : Font.Normal
        }
    }
    MouseArea {
        id: zona

        anchors.fill: parent
        hoverEnabled: true
        onClicked: boton.pulsar()
    }
}

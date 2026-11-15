import QtQuick
import DeepPrep

// Campo de texto de una línea (input del panel): fondo oscuro, línea fina, violeta con el foco.
Rectangle {
    id: campo

    property alias texto: editor.text
    property string pista: ""
    property alias entrada: editor

    signal editado(string texto)
    signal aceptado

    implicitWidth: 520
    implicitHeight: 32
    radius: Tema.radio
    color: Tema.fondo
    border.color: editor.activeFocus ? Tema.acento : zona.containsMouse ? Tema.linea3 : Tema.linea2

    TextInput {
        id: editor

        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        color: Tema.texto
        selectionColor: Tema.alfa(Tema.acento, 0.3)
        selectedTextColor: Tema.texto
        font.family: Tema.sans
        font.pixelSize: 14
        clip: true
        selectByMouse: true
        onTextEdited: campo.editado(text)
        onAccepted: campo.aceptado()

        Text {
            visible: !editor.text && !editor.preeditText
            text: campo.pista
            color: Tema.texto3
            font: editor.font
            elide: Text.ElideRight
            width: editor.width
        }
    }
    MouseArea {
        id: zona

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        cursorShape: Qt.IBeamCursor
    }
}

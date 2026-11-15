import QtQuick
import DeepPrep

// Texto de varias líneas (cuentas, reglas): crece con lo que se escribe, a partir de las líneas que se le pidan.
Rectangle {
    id: area

    property alias texto: edicion.text
    property int lineas: 3

    signal editado(string texto)

    implicitHeight: Math.max(lineas * 22 + 16, edicion.contentHeight + 16)
    radius: Tema.radio
    color: Tema.fondo
    border.color: edicion.activeFocus ? Tema.acento : zona.containsMouse ? Tema.linea3 : Tema.linea2

    TextEdit {
        id: edicion

        x: 12
        y: 8
        width: parent.width - 24
        color: Tema.texto
        selectionColor: Tema.alfa(Tema.acento, 0.3)
        selectedTextColor: Tema.texto
        font.family: Tema.sans
        font.pixelSize: 14
        wrapMode: TextEdit.Wrap
        selectByMouse: true
        onTextChanged: if (activeFocus)
            area.editado(text)
    }
    MouseArea {
        id: zona

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        cursorShape: Qt.IBeamCursor
    }
}

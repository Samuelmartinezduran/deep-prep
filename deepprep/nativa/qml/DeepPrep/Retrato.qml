import QtQuick
import DeepPrep

// Retrato de campeón de Data Dragon. Mientras llega (o sin red) queda su hueco.
Rectangle {
    id: retrato

    property string fuente
    property int tam: 40
    property bool anillo: false

    width: tam
    height: tam
    radius: 2
    color: Tema.panel2

    Image {
        anchors.fill: parent
        source: retrato.fuente
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        smooth: true
        mipmap: true
    }
    Rectangle {
        // La línea fina por fuera del retrato grande.
        visible: retrato.anillo
        anchors.fill: parent
        anchors.margins: -1
        radius: 3
        color: "transparent"
        border.color: Tema.linea2
    }
}

import QtQuick
import DeepPrep

// Minimizar, maximizar y cerrar, con los iconos y colores de Windows 11 (cerrar se pone rojo).
// En Windows, el de maximizar lo lleva el propio Windows (marco.py): por eso su «ratón encima» y su clic se leen de
// marco, y Windows 11 enseña su menú de distribuciones al dejar el ratón encima.
Item {
    id: boton

    property string tipo // "min", "max" o "cerrar"
    property bool maximizada: false
    property bool activa: true
    readonly property bool deWindows: tipo === "max" && marco.integrado
    readonly property bool encima: deWindows ? marco.maxEncima : zona.containsMouse
    readonly property bool pulsado: deWindows ? marco.maxPulsado : zona.pressed

    signal pulsar

    width: 46
    height: Tema.altoBarra

    Rectangle {
        anchors.fill: parent
        color: {
            if (boton.tipo === "cerrar")
                return boton.pulsado ? "#b3271c" : boton.encima ? "#c42b1c" : "transparent";
            return boton.pulsado ? Qt.rgba(1, 1, 1, 0.04) : boton.encima ? Qt.rgba(1, 1, 1, 0.07) : "transparent";
        }
    }
    Text {
        anchors.centerIn: parent
        text: boton.tipo === "min" ? "" : boton.tipo === "max" ? (boton.maximizada ? "" : "") : ""
        color: boton.tipo === "cerrar" && boton.encima ? "#ffffff" : boton.activa ? Tema.texto : Tema.texto3
        font.family: Tema.iconos
        font.pixelSize: 10
    }
    MouseArea {
        id: zona

        anchors.fill: parent
        hoverEnabled: true
        onClicked: boton.pulsar()
    }
}

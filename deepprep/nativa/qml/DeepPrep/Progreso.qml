import QtQuick
import DeepPrep

// Barra fina de progreso (datos que se cargan, historial que se descarga).
Rectangle {
    property real valor: 0 // 0..1

    implicitWidth: 160
    implicitHeight: 2
    color: Tema.linea2
    clip: true

    Rectangle {
        width: parent.width * Math.max(0, Math.min(1, parent.valor))
        height: parent.height
        color: Tema.acento

        Behavior on width {
            NumberAnimation {
                duration: 400
                easing.type: Easing.OutCubic
            }
        }
    }
}

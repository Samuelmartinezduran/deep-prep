import QtQuick
import DeepPrep

// Barra de desplazamiento fina, que solo sale si hay algo que desplazar. Se puede arrastrar.
Item {
    id: pista

    property real desp // cuánto se ha bajado
    property real maxDesp // cuánto se puede bajar

    signal mover(real nuevo)

    width: 12
    visible: maxDesp > 0

    Rectangle {
        id: asa

        x: 3
        width: 6
        radius: 3
        height: Math.max(40, pista.height * pista.height / (pista.height + pista.maxDesp))
        y: pista.maxDesp > 0 ? (pista.height - height) * pista.desp / pista.maxDesp : 0
        color: zona.pressed || zona.containsMouse ? Tema.linea3 : Tema.linea2

        MouseArea {
            id: zona

            property real y0
            property real desp0

            anchors.fill: parent
            anchors.margins: -3
            hoverEnabled: true
            onPressed: mouse => {
                y0 = mapToItem(pista, mouse.x, mouse.y).y;
                desp0 = pista.desp;
            }
            onPositionChanged: mouse => {
                if (!pressed)
                    return;
                const dy = mapToItem(pista, mouse.x, mouse.y).y - y0;
                pista.mover(desp0 + dy * pista.maxDesp / Math.max(1, pista.height - asa.height));
            }
        }
    }
}

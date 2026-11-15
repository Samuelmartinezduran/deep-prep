import QtQuick
import DeepPrep

// Una pestaña con desplazamiento: la rueda baja unos 100 px por muesca (como el navegador), con una barra fina que se
// puede arrastrar. El contenido va centrado, a lo sumo 1680 px de ancho, con el margen del panel.
Item {
    id: hoja

    property real desp: 0
    readonly property real maxDesp: Math.max(0, cuerpo.height + 32 + 48 - height)
    readonly property real anchoContenido: cuerpo.width
    default property alias contenido: cuerpo.data

    function desplazar(nuevo) {
        animacion.stop();
        desp = Math.max(0, Math.min(maxDesp, nuevo));
    }
    function arriba() {
        desplazar(0);
    }

    clip: true
    onMaxDespChanged: if (desp > maxDesp)
        desp = maxDesp

    Column {
        id: cuerpo

        x: Math.max(32, (hoja.width - 1680) / 2)
        y: 32 - hoja.desp
        width: Math.min(hoja.width - 64, 1680)
        spacing: 24
    }
    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: evento => {
            const d = evento.pixelDelta.y !== 0 ? -evento.pixelDelta.y : -evento.angleDelta.y / 120 * 100;
            animacion.to = Math.max(0, Math.min(hoja.maxDesp, (animacion.running ? animacion.to : hoja.desp) + d));
            animacion.restart();
        }
    }
    NumberAnimation {
        id: animacion

        target: hoja
        property: "desp"
        duration: 160
        easing.type: Easing.OutCubic
    }
    Pista {
        anchors.right: parent.right
        height: parent.height
        desp: hoja.desp
        maxDesp: hoja.maxDesp
        onMover: nuevo => hoja.desplazar(nuevo)
    }
}

import QtQuick
import DeepPrep

// Deslizador (la opacidad del overlay): pista fina con el tramo elegido en violeta y la cifra al lado.
Item {
    id: deslizador

    property int desde: 40
    property int hasta: 100
    property int valor: 94
    property string sufijo: "%"

    signal cambiado(int valor)

    function poner(x) {
        const v = Math.round(desde + (hasta - desde) * Math.max(0, Math.min(1, x / pista.width)));
        if (v !== valor) {
            valor = v;
            cambiado(v);
        }
    }

    implicitWidth: 520
    implicitHeight: 24
    activeFocusOnTab: true
    Keys.onLeftPressed: poner((valor - desde - 1) / (hasta - desde) * pista.width)
    Keys.onRightPressed: poner((valor - desde + 1) / (hasta - desde) * pista.width)

    Rectangle {
        id: pista

        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 56
        height: 4
        radius: 2
        color: Tema.linea2

        Rectangle {
            width: parent.width * (deslizador.valor - deslizador.desde) / (deslizador.hasta - deslizador.desde)
            height: parent.height
            radius: 2
            color: Tema.acento
        }
        Rectangle {
            x: parent.width * (deslizador.valor - deslizador.desde) / (deslizador.hasta - deslizador.desde) - width / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            radius: 8
            color: Tema.acento
            border.width: deslizador.activeFocus ? 2 : 0
            border.color: Tema.texto
        }
    }
    Text {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 40
        horizontalAlignment: Text.AlignRight
        text: deslizador.valor + deslizador.sufijo
        color: Tema.texto
        font.family: Tema.mono
        font.pixelSize: 14
    }
    MouseArea {
        width: pista.width
        height: parent.height
        onPressed: raton => {
            deslizador.forceActiveFocus();
            deslizador.poner(raton.x);
        }
        onPositionChanged: raton => {
            if (pressed)
                deslizador.poner(raton.x);
        }
    }
}

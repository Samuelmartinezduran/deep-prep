import QtQuick

// El detalle al dejar el ratón encima: va dentro de cualquier pieza y la cubre entera. Lo pinta la ventana
// (Principal.mostrarTip), encima de todo y sin tapar la marca.
MouseArea {
    id: tip

    property string texto: ""
    property string texto2: ""

    anchors.fill: parent
    anchors.margins: -4 // un poco más de zona que la marca
    hoverEnabled: texto !== ""
    acceptedButtons: Qt.NoButton
    onContainsMouseChanged: {
        const w = Window.window;
        if (!w || !w.mostrarTip)
            return;
        if (containsMouse)
            w.mostrarTip(texto, texto2, tip);
        else
            w.esconderTip(tip);
    }
}

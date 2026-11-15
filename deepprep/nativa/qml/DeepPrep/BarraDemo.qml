pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Modo demo: la barra que cambia de escena (vistas.ESCENAS), debajo de la barra de arriba. Las escenas de la partida
// se piden a la app (y con ellas cambia el overlay); Revisiones y Ajustes son pestañas.
Rectangle {
    id: barra

    property var escenas: []
    property string vista
    property var demo // {escena}
    property string error: ""
    readonly property string actual: demo ? (vista === "partida" ? demo.escena : vista) : ""
    readonly property var escena: escenas.find(x => x.id === actual) || escenas[0]

    signal abrir(string vista)
    signal verOverlay

    height: Math.max(59, fila.implicitHeight + 20)
    color: Tema.panel

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Tema.linea
    }
    Row {
        id: fila

        x: 32
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 64
        spacing: 20

        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: Tema.acento
            }
            Etiqueta {
                text: "Modo demo"
                color: Tema.acento2
            }
        }
        Selector {
            id: selector

            anchors.verticalCenter: parent.verticalCenter
            mono: false
            opciones: barra.escenas.map(x => ({
                        id: x.id,
                        txt: x.nombre
                    }))
            actual: barra.actual
            onElegir: id => {
                const e = barra.escenas.find(x => x.id === id);
                if (!e)
                    return;
                if (e.vista !== "partida") {
                    barra.error = "";
                    barra.abrir(e.vista);
                    return;
                }
                puente.llamar("escena", [id], r => {
                    barra.error = r.ok ? "" : r.error;
                    if (r.ok)
                        barra.abrir("partida");
                });
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: fila.width - selector.width - 160 - (enlace.visible ? enlace.width + 20 : 0) - 40
            text: barra.error || (barra.escena ? barra.escena.txt : "")
            color: barra.error ? Tema.mal : Tema.texto2
            font.family: Tema.sans
            font.pixelSize: 13
            wrapMode: Text.Wrap
        }
        Text {
            id: enlace

            visible: !!barra.escena && barra.escena.overlay
            anchors.verticalCenter: parent.verticalCenter
            text: "Ver el overlay ↗"
            color: zona.containsMouse ? Tema.acento2 : Tema.acento
            font.family: Tema.sans
            font.pixelSize: 13
            font.underline: zona.containsMouse

            MouseArea {
                id: zona

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: barra.verOverlay()
            }
        }
    }
}

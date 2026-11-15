import QtQuick
import DeepPrep

// La clave de Riot ha caducado o no vale: el aviso, dónde pegar la nueva y dónde sacarla.
Rectangle {
    id: banda

    property string error: ""
    property string fallo: ""

    function guardar() {
        puente.llamar("clave", [clave.texto], r => {
            banda.fallo = r.ok ? "" : r.error;
            if (r.ok)
                clave.texto = "";
        });
    }

    height: Math.max(56, fila.implicitHeight + 24)
    color: Tema.panel2

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Tema.linea2
    }
    Flow {
        id: fila

        x: 32
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 64
        spacing: 12

        Row {
            height: 32
            spacing: 10

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: Tema.mal
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: banda.error
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 14
            }
        }
        Campo {
            id: clave

            width: 380
            pista: "Pega aquí la clave nueva (RGAPI-…)"
            onAceptado: banda.guardar()
        }
        Boton {
            primario: true
            texto: "Guardar"
            onPulsar: banda.guardar()
        }
        Text {
            height: 32
            verticalAlignment: Text.AlignVCenter
            text: "developer.riotgames.com"
            color: Tema.acento
            font.family: Tema.sans
            font.pixelSize: 14
            font.underline: zona.containsMouse

            MouseArea {
                id: zona

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: Qt.openUrlExternally("https://developer.riotgames.com/")
            }
        }
        Text {
            visible: banda.fallo !== ""
            height: 32
            verticalAlignment: Text.AlignVCenter
            text: banda.fallo
            color: Tema.mal
            font.family: Tema.sans
            font.pixelSize: 13
        }
    }
}

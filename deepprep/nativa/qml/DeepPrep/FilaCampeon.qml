pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Una fila de «por campeón» en Ajustes (una nota o un jugador de referencia): el campeón, con sugerencias al
// escribir, el texto y Quitar. Un campeón que no existe no se guarda.
Item {
    id: fila

    property string campeon: ""
    property string texto: ""
    property string estado: ""
    property string pistaTexto: ""
    property var campeones: []
    readonly property var sugerencias: {
        const q = campeon.trim().toLowerCase();
        if (!campo.entrada.activeFocus || q.length < 1)
            return [];
        const r = campeones.filter(c => c.toLowerCase().startsWith(q) && c.toLowerCase() !== q);
        return r.slice(0, 6);
    }

    signal cambiado(string campeon, string texto)
    signal quitar

    implicitHeight: 32 + (estado !== "" ? 22 : 0)
    z: sugerencias.length ? 10 : 0

    Campo {
        id: campo

        width: 168
        texto: fila.campeon
        pista: "Campeón"
        onEditado: t => {
            fila.campeon = t;
            fila.cambiado(fila.campeon, fila.texto);
        }
    }
    Campo {
        x: 176
        width: parent.width - 176 - quitar.width - 8
        texto: fila.texto
        pista: fila.pistaTexto
        onEditado: t => {
            fila.texto = t;
            fila.cambiado(fila.campeon, fila.texto);
        }
    }
    Boton {
        id: quitar

        anchors.right: parent.right
        texto: "Quitar"
        onPulsar: fila.quitar()
    }
    Text {
        visible: fila.estado !== ""
        y: 38
        text: fila.estado
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 12
    }
    Rectangle {
        // Sugerencias de campeón, debajo del campo.
        visible: fila.sugerencias.length > 0
        y: 34
        width: 168
        height: sug.implicitHeight + 8
        radius: Tema.radio
        color: Tema.panel2
        border.color: Tema.linea2

        Column {
            id: sug

            x: 4
            y: 4
            width: parent.width - 8

            Repeater {
                model: fila.sugerencias

                Rectangle {
                    id: s

                    required property string modelData

                    width: sug.width
                    height: 28
                    radius: 2
                    color: zonaS.containsMouse ? Tema.hover : "transparent"

                    Text {
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: s.modelData
                        color: Tema.texto
                        font.family: Tema.sans
                        font.pixelSize: 14
                    }
                    MouseArea {
                        id: zonaS

                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            fila.campeon = s.modelData;
                            campo.texto = s.modelData;
                            campo.entrada.focus = false;
                            fila.cambiado(fila.campeon, fila.texto);
                        }
                    }
                }
            }
        }
    }
}

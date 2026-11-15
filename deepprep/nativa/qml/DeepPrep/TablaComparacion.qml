pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tú (violeta) contra tu referencia (gris): una fila por dato, cada una con su escala. Si alguno es negativo, las
// barras salen del centro (vistas.tabla_comparacion).
Column {
    id: tabla

    property var datos

    visible: !!datos
    spacing: 0

    Row {
        spacing: 20
        bottomPadding: 12

        Row {
            spacing: 8

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                height: 10
                radius: 2
                color: Tema.acento
            }
            Text {
                text: "Tú"
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
        Row {
            spacing: 8

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                height: 10
                radius: 2
                color: Tema.texto3
            }
            Text {
                text: tabla.datos ? tabla.datos.ref : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
    }
    Repeater {
        model: tabla.datos ? tabla.datos.filas : []

        Item {
            id: par

            required property var modelData
            required property int index

            width: tabla.width
            height: 46

            Rectangle {
                visible: par.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 52 - 72 - 20
                text: par.modelData.que
                color: Tema.texto2
                font.family: Tema.sans
                font.pixelSize: 13
                wrapMode: Text.Wrap
                lineHeight: 1.05
            }
            Repeater {
                // Dos líneas: la tuya y la de la referencia.
                model: [
                    {
                        v: par.modelData.tu,
                        tono: par.modelData.tu_tono,
                        barra: par.modelData.barras ? par.modelData.barras.tu : null,
                        color: Tema.acento
                    },
                    {
                        v: par.modelData.ref,
                        tono: "suave",
                        barra: par.modelData.barras ? par.modelData.barras.ref : null,
                        color: Tema.texto3
                    }
                ]

                Item {
                    id: linea

                    required property var modelData
                    required property int index

                    x: par.width - 52 - 72 - 10
                    y: linea.index === 0 ? 8 : 25
                    width: 52 + 10 + 72
                    height: 15

                    Text {
                        width: 52
                        horizontalAlignment: Text.AlignRight
                        anchors.verticalCenter: parent.verticalCenter
                        text: linea.modelData.v
                        color: linea.modelData.tono === "bien" ? Tema.bien : linea.modelData.tono === "mal" ? Tema.mal : linea.modelData.tono === "suave" ? Tema.texto3 : Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: 12
                    }
                    Item {
                        x: 62
                        anchors.verticalCenter: parent.verticalCenter
                        width: 72
                        height: 6

                        Rectangle {
                            visible: !!par.modelData.barras && par.modelData.barras.centro
                            x: parent.width / 2
                            y: -2
                            width: 1
                            height: 10
                            color: Tema.linea3
                        }
                        Rectangle {
                            visible: !!linea.modelData.barra
                            x: linea.modelData.barra ? linea.modelData.barra.x * parent.width : 0
                            width: linea.modelData.barra ? linea.modelData.barra.ancho * parent.width : 0
                            height: parent.height
                            radius: 1
                            color: linea.modelData.color
                        }
                    }
                }
            }
        }
    }
    Rico {
        width: tabla.width
        topPadding: 12
        text: tabla.datos ? tabla.datos.pie : ""
        color: Tema.texto3
        font.pixelSize: 12
    }
}

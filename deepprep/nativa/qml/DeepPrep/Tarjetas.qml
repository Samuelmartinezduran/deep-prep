pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tarjetas del jungla rival: rótulo (con un punto si es para tener en cuenta), dato y explicación. La del primer gank
// lleva sus barras por línea.
Grid {
    id: tarjetas

    property var lista: []
    property bool compacto: false

    columns: 2
    columnSpacing: compacto ? 16 : 24
    rowSpacing: 0

    Repeater {
        model: tarjetas.lista

        Column {
            id: tarjeta

            required property var modelData

            width: (tarjetas.width - (tarjetas.columns - 1) * tarjetas.columnSpacing) / tarjetas.columns
            topPadding: tarjetas.compacto ? 4 : 12
            bottomPadding: tarjetas.compacto ? 6 : 12
            spacing: tarjetas.compacto ? 2 : 4

            Rectangle {
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Row {
                spacing: 6

                Etiqueta {
                    text: tarjeta.modelData.titulo
                    font.pixelSize: tarjetas.compacto ? 10 : 11
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: tarjeta.modelData.tono === "ojo" || tarjeta.modelData.tono === "bien"
                    width: 6
                    height: 6
                    radius: 3
                    color: tarjeta.modelData.tono === "bien" ? Tema.bien : Tema.acento
                }
            }
            Text {
                width: parent.width
                text: tarjeta.modelData.valor
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: tarjetas.compacto ? 13 : 14
                font.weight: Font.Medium
                wrapMode: Text.Wrap
            }
            Column {
                // El primer gank, por línea.
                visible: !!tarjeta.modelData.gank
                width: parent.width
                topPadding: 4
                bottomPadding: 4
                spacing: 4

                Repeater {
                    model: tarjeta.modelData.gank ? tarjeta.modelData.gank.filas : []

                    Item {
                        id: barraGank

                        required property var modelData

                        width: tarjeta.width // la tarjeta, no parent: al rehacerse, parent aún es null
                        height: 14

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: barraGank.modelData.l.toUpperCase()
                            color: Tema.texto3
                            font.family: Tema.mono
                            font.pixelSize: 11
                            font.weight: Font.Medium
                        }
                        Rectangle {
                            x: 36
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 36 - 24
                            height: 6
                            color: Tema.linea

                            Rectangle {
                                width: parent.width * barraGank.modelData.ancho
                                height: parent.height
                                color: Tema.rival
                                radius: 1
                            }
                        }
                        Text {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: barraGank.modelData.n
                            color: Tema.texto
                            font.family: Tema.mono
                            font.pixelSize: 11
                        }
                        Tip {
                            texto: barraGank.modelData.tip
                        }
                    }
                }
            }
            Text {
                visible: !tarjetas.compacto && tarjeta.modelData.detalle !== ""
                width: parent.width
                text: tarjeta.modelData.detalle
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
                wrapMode: Text.Wrap
                lineHeight: 1.1
            }
        }
    }
}

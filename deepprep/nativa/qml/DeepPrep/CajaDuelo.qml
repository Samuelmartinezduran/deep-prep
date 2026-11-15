pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tu duelo contra el rival directo, en partidas de Master+, y tú contra tu referencia. Solo antes de empezar.
// compacto: el del overlay (dos datos, sin tablas ni build).
Caja {
    id: duelo

    property var datos
    property bool compacto: false

    visible: !!datos
    titulo: datos ? datos.titulo : ""
    sub: datos ? datos.sub : ""
    colorBorde: Tema.linea2
    relleno: compacto ? 12 : 20

    Item {
        width: duelo.anchoDentro
        height: (duelo.compacto ? 32 : 48) + 1

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -8
            spacing: 10

            Row {
                spacing: 8

                Retrato {
                    anchors.verticalCenter: parent.verticalCenter
                    tam: duelo.compacto ? 24 : 32
                    fuente: duelo.datos ? duelo.datos.icono_a : ""
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: duelo.datos ? duelo.datos.a : ""
                    color: Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: duelo.compacto ? 13 : 14
                    font.weight: Font.DemiBold
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "VS"
                color: Tema.texto3
                font.family: Tema.mono
                font.pixelSize: 11
                font.weight: Font.Medium
            }
            Row {
                spacing: 8

                Retrato {
                    anchors.verticalCenter: parent.verticalCenter
                    tam: duelo.compacto ? 24 : 32
                    fuente: duelo.datos ? duelo.datos.icono_b : ""
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: duelo.datos ? duelo.datos.b : ""
                    color: Tema.rival
                    font.family: Tema.sans
                    font.pixelSize: duelo.compacto ? 13 : 14
                    font.weight: Font.DemiBold
                }
            }
        }
        Column {
            visible: !!duelo.datos && !!duelo.datos.wr
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -8

            Text {
                anchors.right: parent.right
                text: duelo.datos && duelo.datos.wr ? duelo.datos.wr.txt : ""
                color: Tema.texto
                font.family: Tema.mono
                font.pixelSize: duelo.compacto ? 16 : 22
            }
            Text {
                visible: !duelo.compacto
                anchors.right: parent.right
                text: duelo.datos && duelo.datos.wr ? duelo.datos.wr.linea2 : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Tema.linea
        }
    }
    Item {
        width: 1
        height: duelo.compacto ? 8 : 16
    }
    Text {
        visible: !!duelo.datos && duelo.datos.poco
        width: duelo.anchoDentro
        text: duelo.datos ? duelo.datos.motivo : ""
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
        wrapMode: Text.Wrap
    }
    Repeater {
        model: duelo.datos ? duelo.datos.datos : []

        Column {
            id: dato

            required property var modelData
            required property int index

            width: duelo.anchoDentro
            topPadding: dato.index > 0 ? (duelo.compacto ? 5 : 10) : 0
            bottomPadding: duelo.compacto ? 5 : 10
            spacing: 2

            Rectangle {
                visible: dato.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Text {
                width: parent.width
                text: dato.modelData.texto
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: duelo.compacto ? 13 : 14
                wrapMode: Text.Wrap
            }
            Text {
                visible: dato.modelData.detalle !== ""
                width: parent.width
                text: dato.modelData.detalle
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
    }
    Item {
        visible: !!duelo.datos && !!duelo.datos.tu
        width: duelo.anchoDentro
        height: comparativa.height + 17

        Rectangle {
            width: parent.width
            height: 1
            color: Tema.linea
        }
        TablaComparacion {
            id: comparativa

            y: 16
            width: parent.width
            datos: duelo.datos ? duelo.datos.tu : null
        }
    }
    Column {
        visible: !!duelo.datos && duelo.datos.build !== ""
        width: duelo.anchoDentro
        topPadding: 16
        spacing: 4

        Rectangle {
            width: parent.width
            height: 1
            color: Tema.linea
        }
        Item {
            width: 1
            height: 8
        }
        Etiqueta {
            text: "Lo más jugado"
        }
        Rico {
            width: parent.width
            text: duelo.datos ? duelo.datos.build : ""
            font.pixelSize: 13
        }
    }
}

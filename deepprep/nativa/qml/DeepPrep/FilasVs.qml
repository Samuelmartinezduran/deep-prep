pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tu historial contra los campeones de la partida: con tu campeón y en total (vistas.filas_vs).
Column {
    id: vs

    property var datos

    Repeater {
        model: vs.datos ? vs.datos.filas : []

        Item {
            id: filaVs

            required property var modelData
            required property int index

            width: vs.width
            height: 41

            Rectangle {
                visible: filaVs.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Retrato {
                anchors.verticalCenter: parent.verticalCenter
                tam: 24
                fuente: filaVs.modelData.retrato
            }
            Text {
                x: 34
                anchors.verticalCenter: parent.verticalCenter
                text: filaVs.modelData.nombre
                color: Tema.texto2
                font.family: Tema.sans
                font.pixelSize: 14
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Rico {
                    anchors.verticalCenter: parent.verticalCenter
                    text: filaVs.modelData.mio
                    color: Tema.texto3
                    font.pixelSize: 12
                    wrapMode: Text.NoWrap
                }
                Rico {
                    anchors.verticalCenter: parent.verticalCenter
                    text: filaVs.modelData.total
                    font.family: Tema.mono
                    wrapMode: Text.NoWrap
                }
            }
        }
    }
    Text {
        visible: !!vs.datos && vs.datos.sin !== ""
        width: vs.width
        topPadding: 8
        text: vs.datos ? vs.datos.sin : ""
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 12
        wrapMode: Text.Wrap
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Dónde va a haber errores (o, ya jugando, las líneas sin veredicto): por qué, del rival en blanco y de tu equipo en
// gris, y a qué línea fue su primer gank.
Caja {
    id: lineas

    property var datos

    titulo: datos ? datos.titulo : ""
    sub: "rival en blanco, tu equipo en gris"

    Text {
        visible: !!lineas.datos && lineas.datos.lineas.length === 0
        text: "Faltan datos de las líneas."
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
    }
    Repeater {
        model: lineas.datos ? lineas.datos.lineas : []

        Column {
            id: linea

            required property var modelData
            required property int index

            width: lineas.anchoDentro
            topPadding: linea.index > 0 ? 12 : 0
            bottomPadding: 12
            spacing: 4

            Rectangle {
                visible: linea.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Item {
                width: parent.width
                height: 20

                Etiqueta {
                    anchors.verticalCenter: parent.verticalCenter
                    text: linea.modelData.linea
                    color: Tema.texto
                }
                Row {
                    visible: linea.modelData.veredicto !== ""
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6
                        height: 6
                        radius: 3
                        color: linea.modelData.tono === "bien" ? Tema.bien : linea.modelData.tono === "ojo" ? Tema.acento : linea.modelData.tono === "fallo" ? Tema.mal : Tema.texto3
                    }
                    Text {
                        text: linea.modelData.veredicto
                        color: Tema.texto
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                }
            }
            Repeater {
                model: linea.modelData.motivos

                Row {
                    id: motivo

                    required property var modelData

                    leftPadding: 4
                    spacing: 8

                    Text {
                        text: "•"
                        color: motivo.modelData.aliado ? Tema.texto3 : Tema.texto2
                        font.pixelSize: 13
                    }
                    Text {
                        width: lineas.anchoDentro - 24
                        text: motivo.modelData.t
                        color: motivo.modelData.aliado ? Tema.texto3 : Tema.texto2
                        font.family: Tema.sans
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                    }
                }
            }
            Text {
                visible: linea.modelData.motivos.length === 0
                text: "Nada que destaque en sus últimas partidas."
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
    }
    Column {
        visible: !!lineas.datos && lineas.datos.pie !== ""
        width: lineas.anchoDentro
        spacing: 12

        Rectangle {
            width: parent.width
            height: 1
            color: Tema.linea
        }
        Rico {
            width: parent.width
            text: lineas.datos ? lineas.datos.pie : ""
            color: Tema.texto3
            font.pixelSize: 13
        }
    }
}

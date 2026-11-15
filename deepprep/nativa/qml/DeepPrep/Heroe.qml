import QtQuick
import DeepPrep

// La cabecera de la pestaña Partida: tu retrato, la cola y la etapa, tu campeón y, a la derecha, sus datos.
Item {
    id: heroe

    property string retrato: ""
    property string cabecera: ""
    property string titulo: ""
    property string rol: ""
    property string sub: "" // RichText
    default property alias derecha: datos.data

    implicitHeight: Math.max(64, textos.implicitHeight)

    Retrato {
        id: foto

        visible: heroe.retrato !== ""
        anchors.verticalCenter: parent.verticalCenter
        tam: 64
        anillo: true
        fuente: heroe.retrato
    }
    Column {
        id: textos

        anchors.left: foto.visible ? foto.right : parent.left
        anchors.leftMargin: foto.visible ? 20 : 0
        anchors.right: datos.left
        anchors.rightMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        Etiqueta {
            text: heroe.cabecera
        }
        Row {
            spacing: 12
            topPadding: 2

            Text {
                text: heroe.titulo
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 32
                font.weight: Font.DemiBold
                font.letterSpacing: -0.8
            }
            Text {
                visible: heroe.rol !== ""
                anchors.baseline: parent.children[0].baseline
                text: heroe.rol
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 13
                font.weight: Font.Medium
            }
        }
        Rico {
            width: parent.width
            text: heroe.sub
            color: Tema.texto2
        }
    }
    Row {
        id: datos

        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: 48
    }
}

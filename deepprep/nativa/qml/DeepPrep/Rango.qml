import QtQuick
import DeepPrep

// El rango de solo/dúo de un jugador: oculto, cargando, sin rango o con su emblema (vistas.rango).
Item {
    id: rango

    property var datos
    property int tamIcono: 28

    implicitWidth: fila.implicitWidth
    implicitHeight: Math.max(tamIcono, fila.implicitHeight)

    Text {
        visible: !!rango.datos && rango.datos.estado === "cargando"
        anchors.verticalCenter: parent.verticalCenter
        text: "…"
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
    }
    Text {
        visible: !!rango.datos && rango.datos.estado === "oculto"
        anchors.verticalCenter: parent.verticalCenter
        text: rango.datos ? rango.datos.linea2 || "" : ""
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 12
    }
    Row {
        id: fila

        visible: !!rango.datos && (rango.datos.estado === "ok" || rango.datos.estado === "sin")
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10

        Image {
            anchors.verticalCenter: parent.verticalCenter
            width: rango.tamIcono
            height: rango.tamIcono
            sourceSize: Qt.size(rango.tamIcono * 2, rango.tamIcono * 2)
            source: rango.datos ? rango.datos.icono || "" : ""
            asynchronous: true
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, rango.width > 0 ? rango.width - rango.tamIcono - 10 : implicitWidth)

            Text {
                text: rango.datos ? rango.datos.txt || "" : ""
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 14
                font.weight: Font.Medium
            }
            Rico {
                text: rango.datos ? rango.datos.linea2 || "" : ""
                color: Tema.texto3
                font.pixelSize: 12
                wrapMode: Text.NoWrap
                elide: Text.ElideRight
            }
        }
    }
    Tip {
        texto: rango.datos ? rango.datos.titulo || "" : ""
    }
}

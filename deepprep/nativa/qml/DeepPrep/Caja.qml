import QtQuick
import DeepPrep

// Caja del panel (.caja): fondo panel, línea fina y esquinas de 4 px, con su título (rótulo + subtítulo) si lo tiene.
// Lo de dentro va en una columna del ancho de la caja menos el relleno.
Rectangle {
    id: caja

    property string titulo: ""
    property string sub: ""
    property int relleno: 20
    property color colorBorde: Tema.linea
    default property alias contenido: cuerpo.data
    readonly property real anchoDentro: width - 2 * relleno

    implicitHeight: columna.implicitHeight + 2 * relleno
    color: Tema.panel
    border.color: colorBorde
    radius: Tema.radio

    Column {
        id: columna

        x: caja.relleno
        y: caja.relleno
        width: caja.anchoDentro
        spacing: 16

        Flow {
            visible: caja.titulo !== ""
            width: parent.width
            spacing: 8

            Etiqueta {
                text: caja.titulo
                color: Tema.texto2
            }
            Text {
                visible: caja.sub !== ""
                width: Math.min(implicitWidth, caja.anchoDentro)
                wrapMode: Text.Wrap
                text: caja.sub
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
                textFormat: Text.RichText
            }
        }
        Column {
            id: cuerpo

            width: parent.width
        }
    }
}

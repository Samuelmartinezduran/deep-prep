import QtQuick
import DeepPrep

// Barra de % de victorias con la marca del 50 %. El color lo lleva la cifra de al lado, no la barra.
Item {
    id: barra

    property var datos // {ancho: 0..1, titulo}

    implicitWidth: 56
    implicitHeight: 8

    Rectangle {
        y: 2
        width: parent.width
        height: 4
        color: Tema.linea

        Rectangle {
            width: parent.width * (barra.datos ? barra.datos.ancho : 0)
            height: parent.height
            color: Tema.texto3
        }
    }
    Rectangle {
        x: parent.width / 2
        width: 1
        height: 8
        color: Tema.linea3
    }
    Tip {
        texto: barra.datos ? barra.datos.titulo : ""
    }
}

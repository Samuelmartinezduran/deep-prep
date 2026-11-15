import QtQuick
import DeepPrep

// Un dato de la derecha de la cabecera (baneos, datos, tiempo): rótulo arriba, dato abajo, separados por una línea.
Item {
    id: dato

    property string rotulo
    property bool primero: false
    default property alias contenido: cuerpo.data

    implicitWidth: Math.max(rot.implicitWidth, cuerpo.childrenRect.width) + (primero ? 0 : 24) + 24
    height: 48

    Rectangle {
        visible: !dato.primero
        width: 1
        height: parent.height
        color: Tema.linea
    }
    Etiqueta {
        id: rot

        x: dato.primero ? 0 : 24
        text: dato.rotulo
    }
    Item {
        id: cuerpo

        x: dato.primero ? 0 : 24
        y: 24
        width: childrenRect.width
        height: 24
    }
}

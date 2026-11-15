import QtQuick
import DeepPrep

// Racha: victoria hacia arriba (verde), derrota hacia abajo (rojo); se lee también sin color. La más reciente, a la
// derecha (vistas.racha ya las da en ese orden).
Item {
    id: racha

    property var datos // {items: [bool], titulo}

    implicitWidth: datos ? datos.items.length * 6 - 2 : 0
    implicitHeight: 16

    Rectangle {
        y: 8
        width: parent.width
        height: 1
        color: Tema.linea2
    }
    Row {
        spacing: 2

        Repeater {
            model: racha.datos ? racha.datos.items : []

            Rectangle {
                required property bool modelData

                width: 4
                height: 7
                y: modelData ? 1 : 9
                color: modelData ? Tema.bien : Tema.mal
                opacity: 0.85
            }
        }
    }
    Tip {
        texto: racha.datos ? racha.datos.titulo : ""
    }
}

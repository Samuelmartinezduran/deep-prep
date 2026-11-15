pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tu historial: cómo te va con tu campeón y contra los de esta partida, y con quién ya has jugado.
Caja {
    id: historial

    property var datos

    visible: !!datos
    titulo: "Tu historial"
    sub: datos ? datos.sub : ""

    Text {
        visible: !!historial.datos && historial.datos.vacio !== ""
        width: historial.anchoDentro
        text: historial.datos ? historial.datos.vacio : ""
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
        wrapMode: Text.Wrap
    }
    Item {
        visible: !!historial.datos && historial.datos.vacio === ""
        width: historial.anchoDentro
        height: 56

        Column {
            visible: !!historial.datos && !!historial.datos.cifra
            spacing: 4

            Text {
                text: historial.datos && historial.datos.cifra ? historial.datos.cifra.txt : ""
                color: historial.datos && historial.datos.cifra ? (historial.datos.cifra.tono === "bien" ? Tema.bien : historial.datos.cifra.tono === "mal" ? Tema.mal : Tema.texto) : Tema.texto
                font.family: Tema.mono
                font.pixelSize: 28
                font.letterSpacing: -0.56
            }
            Rico {
                text: historial.datos && historial.datos.cifra ? historial.datos.cifra.linea2 : ""
                color: Tema.texto3
                font.pixelSize: 12
                wrapMode: Text.NoWrap
            }
        }
        Text {
            visible: !!historial.datos && historial.datos.sin !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: historial.datos ? historial.datos.sin || "" : ""
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 12
        }
        Racha {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: !!historial.datos && !!historial.datos.racha
            datos: historial.datos ? historial.datos.racha : null
        }
    }
    Etiqueta {
        visible: !!historial.datos && historial.datos.vacio === ""
        topPadding: 4
        bottomPadding: 4
        text: "Contra estos campeones"
    }
    FilasVs {
        visible: !!historial.datos && historial.datos.vacio === ""
        width: historial.anchoDentro
        datos: historial.datos ? historial.datos.vs : null
    }
    Column {
        visible: !!historial.datos && !!historial.datos.conocidos && historial.datos.conocidos.length > 0
        width: historial.anchoDentro
        topPadding: 12
        spacing: 12

        Rectangle {
            width: parent.width
            height: 1
            color: Tema.linea
        }
        Repeater {
            model: historial.datos && historial.datos.conocidos ? historial.datos.conocidos : []

            Rico {
                required property string modelData

                width: historial.anchoDentro
                text: modelData
                color: Tema.texto3
                font.pixelSize: 13
            }
        }
    }
}

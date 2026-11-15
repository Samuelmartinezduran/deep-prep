pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Lista de frases separadas por una línea fina, con su marca delante: avisos (punto), plan (01, 02...) o reglas.
Column {
    id: lista

    property var elementos: [] // textos, o {texto, tono}
    property string marca: "punto" // "punto", "numero" o "nada"
    property int tamLetra: 14

    Repeater {
        model: lista.elementos

        Item {
            id: elemento

            required property var modelData
            required property int index
            readonly property string texto: typeof modelData === "string" ? modelData : modelData.texto
            readonly property string tono: typeof modelData === "string" ? "" : modelData.tono || ""

            width: lista.width
            height: txt.implicitHeight + (elemento.index > 0 ? 20 : 10)

            Rectangle {
                visible: elemento.index > 0
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Text {
                visible: lista.marca === "numero"
                y: txt.y + 1
                text: String(elemento.index + 1).padStart(2, "0")
                color: Tema.acento
                font.family: Tema.mono
                font.pixelSize: 11
                font.weight: Font.Medium
            }
            Rectangle {
                visible: lista.marca === "punto"
                y: txt.y + txt.font.pixelSize * 0.55
                width: 6
                height: 6
                radius: 3
                color: elemento.tono === "ojo" ? Tema.acento : elemento.tono === "bien" ? Tema.bien : Tema.linea3
            }
            Text {
                id: txt

                x: lista.marca === "nada" ? 0 : lista.marca === "numero" ? 28 : 16
                y: elemento.index > 0 ? 10 : 0
                width: parent.width - x
                text: elemento.texto
                color: lista.marca === "punto" && elemento.tono !== "ojo" && elemento.tono !== "bien" ? Tema.texto2 : Tema.texto
                font.family: Tema.sans
                font.pixelSize: lista.tamLetra
                wrapMode: Text.Wrap
            }
        }
    }
}

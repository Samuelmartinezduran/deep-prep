import QtQuick
import DeepPrep

// Texto con trozos de distinto estilo (cifras en mono, negritas, tonos). El RichText lo hace vistas.py, con todo lo
// que viene de la app ya escapado.
Text {
    color: Tema.texto2
    font.family: Tema.sans
    font.pixelSize: 14
    textFormat: Text.RichText
    wrapMode: Text.Wrap
    lineHeight: 1.15
}

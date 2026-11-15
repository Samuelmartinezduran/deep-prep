pragma Singleton
import QtQuick

// Los colores, las letras y las medidas del panel (los de web/estilo.css), en un solo sitio.
// Un solo acento, el violeta: eres tú, lo activo y la acción principal. Azul y rojo solo dicen de qué equipo es algo;
// verde y rojo claro, si un dato va bien o mal, y siempre acompañan a una cifra o una palabra.
QtObject {
    readonly property color fondo: "#08090a"
    readonly property color panel: "#0e0f11"
    readonly property color panel2: "#131417"
    readonly property color hover: "#17191c"
    readonly property color yo: "#13121c"
    readonly property color linea: Qt.rgba(1, 1, 1, 0.07)
    readonly property color linea2: Qt.rgba(1, 1, 1, 0.14)
    readonly property color linea3: Qt.rgba(1, 1, 1, 0.24)
    readonly property color texto: "#f4f5f6"
    readonly property color texto2: "#a3aab4"
    readonly property color texto3: "#79808b"
    readonly property color acento: "#8b7cf6"
    readonly property color acento2: "#a196f8"
    readonly property color aliado: "#4790ec"
    readonly property color rival: "#e5534d"
    readonly property color bien: "#40cf8f"
    readonly property color mal: "#f2706a"

    readonly property string sans: "Space Grotesk"
    readonly property string mono: "IBM Plex Mono"
    // Los iconos de los botones de la ventana, los mismos que usa Windows (en Windows 10, su versión anterior).
    readonly property string iconos: Qt.fontFamilies().indexOf("Segoe Fluent Icons") >= 0 ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"

    readonly property int radio: 4
    readonly property int barra: 224
    readonly property int altoBarra: 56

    function tono(t) {
        return t === "bien" ? bien : t === "mal" ? mal : texto3;
    }
    function alfa(c, a) {
        return Qt.rgba(c.r, c.g, c.b, a);
    }
}

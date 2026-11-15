import QtQuick
import QtQuick.Shapes
import DeepPrep

// Iconos de línea del panel (web/js/iconos.js): trazo de 1,5 en una retícula de 16, dibujados como vectores.
Item {
    id: icono

    property string nombre
    property color color: Tema.texto2
    property real tam: 16
    property real grosor: 1.5 // en unidades de la retícula
    readonly property bool relleno: nombre === "play"
    readonly property var trazos: ({
            "partida": "M13.75 8A5.75 5.75 0 1 1 2.25 8A5.75 5.75 0 1 1 13.75 8ZM10 8A2 2 0 1 1 6 8A2 2 0 1 1 10 8ZM8 .75v2.5M8 12.75v2.5M.75 8h2.5M12.75 8h2.5",
            "revisiones": "M2.75 3.25h10.5M2.75 8h10.5M2.75 12.75h6.5M11.5 11.25l1.25 1.5 2.25-3",
            "ajustes": "M2 4h4.5M9.5 4H14M2 12h2.5M7.5 12H14M9.5 4A1.5 1.5 0 1 1 6.5 4A1.5 1.5 0 1 1 9.5 4ZM7.5 12A1.5 1.5 0 1 1 4.5 12A1.5 1.5 0 1 1 7.5 12Z",
            "buscar": "M11.75 7A4.75 4.75 0 1 1 2.25 7A4.75 4.75 0 1 1 11.75 7ZM10.5 10.5l3.75 3.75",
            "carpeta": "M1.75 4.25v8.5h12.5v-7H8L6.5 3.75H2.25z",
            "muerte": "M2.4 2.4l11.2 11.2M13.6 2.4L2.4 13.6",
            "play": "M5 3.5v9l7-4.5z"
        })

    implicitWidth: tam
    implicitHeight: tam

    Shape {
        width: 16
        height: 16
        preferredRendererType: Shape.CurveRenderer
        transform: Scale {
            xScale: icono.tam / 16
            yScale: icono.tam / 16
        }

        ShapePath {
            strokeColor: icono.relleno ? "transparent" : icono.color
            strokeWidth: icono.relleno ? 0 : icono.grosor
            fillColor: icono.relleno ? icono.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin

            PathSvg {
                path: icono.trazos[icono.nombre] || ""
            }
        }
    }
}

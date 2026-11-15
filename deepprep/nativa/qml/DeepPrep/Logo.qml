import QtQuick
import QtQuick.Shapes
import DeepPrep

// El logo (web/js/iconos.js): la Grieta en pequeño. Las calles de top y bot, mid entre las dos bases, el río y tú en
// el centro, con su hueco alrededor. Retícula de 32.
Item {
    id: logo

    property real tam: 20

    implicitWidth: tam
    implicitHeight: tam

    Shape {
        width: 32
        height: 32
        preferredRendererType: Shape.CurveRenderer
        transform: Scale {
            xScale: logo.tam / 32
            yScale: logo.tam / 32
        }

        ShapePath {
            strokeColor: Tema.alfa(Tema.acento, 0.4)
            strokeWidth: 1.4
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathSvg {
                path: "M9 9L13.6 13.6M18.4 18.4L23 23"
            }
        }
        ShapePath {
            strokeColor: Tema.acento
            strokeWidth: 1.8
            fillColor: "transparent"
            PathSvg {
                path: "M9.3 6.8H22.7A2.5 2.5 0 0 1 25.2 9.3V22.7A2.5 2.5 0 0 1 22.7 25.2H9.3A2.5 2.5 0 0 1 6.8 22.7V9.3A2.5 2.5 0 0 1 9.3 6.8Z"
            }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: Tema.acento
            PathSvg {
                path: "M8.5 20.5H9A2.5 2.5 0 0 1 11.5 23V23.5A2.5 2.5 0 0 1 9 26H8.5A2.5 2.5 0 0 1 6 23.5V23A2.5 2.5 0 0 1 8.5 20.5ZM23 6H23.5A2.5 2.5 0 0 1 26 8.5V9A2.5 2.5 0 0 1 23.5 11.5H23A2.5 2.5 0 0 1 20.5 9V8.5A2.5 2.5 0 0 1 23 6Z"
            }
        }
        ShapePath {
            strokeColor: Tema.acento
            strokeWidth: 1.8
            fillColor: "transparent"
            PathSvg {
                path: "M8.75 23.25L13.6 18.4M18.4 13.6L23.25 8.75"
            }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: Tema.acento
            PathSvg {
                path: "M18.4 16A2.4 2.4 0 1 1 13.6 16A2.4 2.4 0 1 1 18.4 16Z"
            }
        }
    }
}

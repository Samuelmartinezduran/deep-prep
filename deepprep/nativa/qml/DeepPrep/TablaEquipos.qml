pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Los dos equipos en una tabla con columnas rotuladas (el de cada uno, con su color). Las columnas de texto se
// reparten el ancho 1,35 : 1 : 0,7 : 0,8. basico: fuera de la Grieta, solo el nombre (con su
// maestría) y el rango.
Rectangle {
    id: tabla

    property var aliado: []
    property var rival: []
    property bool basico: false
    readonly property real libre: width - 108 - (basico ? 1 : 3) * 16 - 20
    readonly property real anchoNombre: basico ? libre * 0.55 : Math.max(170, libre * 1.35 / 3.85)
    readonly property real anchoRango: basico ? libre * 0.45 : Math.max(150, libre * 1 / 3.85)
    readonly property real anchoForma: Math.max(112, libre * 0.7 / 3.85)

    implicitHeight: columna.implicitHeight
    color: Tema.panel
    border.color: Tema.linea
    radius: Tema.radio
    clip: true

    Column {
        id: columna

        width: parent.width

        Repeater {
            model: [
                {
                    nombre: "Tu equipo",
                    color: Tema.aliado,
                    filas: tabla.aliado
                },
                {
                    nombre: "Rival",
                    color: Tema.rival,
                    filas: tabla.rival
                }
            ]

            Column {
                id: equipo

                required property var modelData
                required property int index

                width: columna.width

                Rectangle {
                    visible: equipo.index > 0
                    width: parent.width
                    height: 1
                    color: Tema.linea2
                }
                Item {
                    // Cabecera: el nombre del equipo y qué es cada columna.
                    width: parent.width
                    height: 40

                    Row {
                        x: 108
                        y: 18
                        spacing: 8

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 8
                            height: 8
                            radius: 1
                            color: equipo.modelData.color
                        }
                        Etiqueta {
                            text: equipo.modelData.nombre
                            color: Tema.texto
                        }
                    }
                    Etiqueta {
                        x: 108 + tabla.anchoNombre + 16
                        y: 18
                        text: "Rango solo/dúo"
                    }
                    Etiqueta {
                        visible: !tabla.basico
                        x: 108 + tabla.anchoNombre + 16 + tabla.anchoRango + 16
                        y: 18
                        text: "Últimas partidas"
                    }
                    Etiqueta {
                        visible: !tabla.basico
                        x: 108 + tabla.anchoNombre + 16 + tabla.anchoRango + 16 + tabla.anchoForma + 16
                        y: 18
                        text: "Con su campeón"
                    }
                }
                Repeater {
                    model: equipo.modelData.filas

                    Column {
                        id: jugador

                        required property var modelData

                        width: columna.width

                        Rectangle {
                            width: parent.width
                            height: 1
                            color: Tema.linea
                        }
                        FilaJugador {
                            width: parent.width
                            basico: tabla.basico
                            datos: jugador.modelData
                            anchoNombre: tabla.anchoNombre
                            anchoRango: tabla.anchoRango
                            anchoForma: tabla.anchoForma
                        }
                    }
                }
            }
        }
    }
}

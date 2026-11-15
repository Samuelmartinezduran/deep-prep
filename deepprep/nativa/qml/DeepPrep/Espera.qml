pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Sin partida ni selección: qué hace la app y cómo sale el overlay (vistas.espera).
Item {
    id: espera

    property var datos

    implicitHeight: col.implicitHeight + 128

    Column {
        id: col

        anchors.horizontalCenter: parent.horizontalCenter
        y: 64
        width: Math.min(560, espera.width)
        spacing: 8

        Rectangle {
            width: 48
            height: 48
            radius: Tema.radio
            color: Tema.panel
            border.color: Tema.linea2

            Logo {
                anchors.centerIn: parent
                tam: 24
            }
        }
        Item {
            width: 1
            height: 16
        }
        Etiqueta {
            text: "Deep Prep"
        }
        Text {
            width: parent.width
            text: espera.datos ? espera.datos.titulo : ""
            color: Tema.texto
            font.family: Tema.sans
            font.pixelSize: 28
            font.weight: Font.DemiBold
            font.letterSpacing: -0.56
            wrapMode: Text.Wrap
        }
        Text {
            width: parent.width
            text: espera.datos ? espera.datos.texto : ""
            color: Tema.texto2
            font.family: Tema.sans
            font.pixelSize: 14
            wrapMode: Text.Wrap
        }
        Column {
            visible: !!espera.datos && !!espera.datos.sync
            width: parent.width
            topPadding: 8
            spacing: 8

            Row {
                Text {
                    text: espera.datos && espera.datos.sync ? espera.datos.sync.txt : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 12
                }
                Text {
                    text: espera.datos && espera.datos.sync ? espera.datos.sync.num : ""
                    color: Tema.texto3
                    font.family: Tema.mono
                    font.pixelSize: 12
                }
            }
            Progreso {
                width: parent.width
                valor: espera.datos && espera.datos.sync ? espera.datos.sync.ancho : 0
            }
        }
        Column {
            // Cómo sale el panel encima del juego.
            visible: !!espera.datos && espera.datos.pasos
            width: parent.width
            topPadding: 24

            Repeater {
                model: [
                    {
                        n: "01",
                        t: "Pantalla de carga",
                        d: "El panel sale solo encima del juego y se esconde al empezar."
                    },
                    {
                        n: "02",
                        t: "Ya jugando",
                        d: ""
                    },
                    {
                        n: "03",
                        t: "Dentro de las normas",
                        d: "Durante la partida solo enseña datos de antes de empezar, como permite Riot."
                    }
                ]

                Item {
                    id: paso

                    required property var modelData

                    width: col.width
                    height: textoPaso.implicitHeight + 33

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Tema.linea
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Tema.linea
                    }
                    Text {
                        y: 17
                        text: paso.modelData.n
                        color: Tema.acento
                        font.family: Tema.mono
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }
                    Column {
                        id: textoPaso

                        x: 40
                        y: 16
                        width: parent.width - 40
                        spacing: 2

                        Text {
                            text: paso.modelData.t
                            color: Tema.texto
                            font.family: Tema.sans
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Text {
                            visible: paso.modelData.d !== ""
                            width: parent.width
                            text: paso.modelData.d
                            color: Tema.texto3
                            font.family: Tema.sans
                            font.pixelSize: 12
                            wrapMode: Text.Wrap
                        }
                        Row {
                            visible: paso.modelData.d === ""
                            spacing: 6

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Mantén"
                                color: Tema.texto3
                                font.family: Tema.sans
                                font.pixelSize: 12
                            }
                            Teclas {
                                anchors.verticalCenter: parent.verticalCenter
                                lista: espera.datos ? espera.datos.teclas : []
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "para verlo; al soltar, desaparece."
                                color: Tema.texto3
                                font.family: Tema.sans
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
        }
        Row {
            visible: !!espera.datos && espera.datos.aviso !== ""
            width: parent.width
            topPadding: 24
            spacing: 12

            Rectangle {
                y: 7
                width: 6
                height: 6
                radius: 3
                color: Tema.mal
            }
            Text {
                width: parent.width - 18
                text: espera.datos ? espera.datos.aviso : ""
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 14
                wrapMode: Text.Wrap
            }
        }
    }
}

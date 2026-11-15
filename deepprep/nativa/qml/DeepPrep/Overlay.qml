pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import DeepPrep

// La ventana encima del juego (vistas.overlay): lo justo para leerlo en dos segundos. Cuándo sale lo decide
// overlay.Controlador (las normas de Riot); ventanas.py la enseña y la esconde. En partida, la app ya ha quitado lo
// que Riot no deja enseñar.
// Sin foco, transparente al ratón y siempre encima: el juego sigue recibiendo todo. En la demo (previa), una ventana
// normal para verla sin juego.
Window {
    id: ov

    readonly property var d: puente.overlay
    readonly property bool conDuelo: !!d && !!d.duelo
    readonly property bool basico: !!d && !!d.basico // fuera de la Grieta: ni jungla ni rival de línea

    width: 1180
    height: 580
    visible: false
    title: "Deep Prep · overlay"
    color: Tema.fondo
    flags: overlayPrevia ? Qt.Window : Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput

    component FilaOv: Item {
        id: fila

        property var datos

        height: 54

        Rectangle {
            anchors.fill: parent
            visible: !!fila.datos && fila.datos.soy_yo
            color: Tema.yo

            Rectangle {
                width: 2
                height: parent.height
                color: Tema.acento
            }
        }
        Rol {
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            tam: 14
            nombre: fila.datos ? fila.datos.rol.icono : ""
        }
        Retrato {
            x: 40
            anchors.verticalCenter: parent.verticalCenter
            tam: 36
            fuente: fila.datos ? fila.datos.retrato : ""
        }
        Column {
            x: 88
            anchors.verticalCenter: parent.verticalCenter
            width: (fila.width - 88 - 64 - 24) * 0.55

            Text {
                width: parent.width
                text: fila.datos ? fila.datos.nombre : ""
                color: fila.datos && fila.datos.soy_yo ? Tema.acento : Tema.texto
                font.family: Tema.sans
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Etiquetas {
                visible: !!fila.datos && fila.datos.etiquetas.length > 0
                width: parent.width
                spacing: 12
                tamLetra: 11
                lista: fila.datos ? fila.datos.etiquetas : []
            }
            Text {
                visible: !!fila.datos && fila.datos.etiquetas.length === 0
                text: fila.datos ? fila.datos.campeon : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
        Rango {
            x: 88 + (fila.width - 88 - 64 - 24) * 0.55 + 12
            anchors.verticalCenter: parent.verticalCenter
            width: (fila.width - 88 - 64 - 24) * 0.45
            tamIcono: 22
            datos: fila.datos ? fila.datos.rango : null
        }
        Column {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter

            Text {
                anchors.right: parent.right
                text: !fila.datos ? "" : fila.datos.wr.cargando ? "…" : fila.datos.wr.txt
                color: fila.datos && !fila.datos.wr.cargando ? (fila.datos.wr.tono === "bien" ? Tema.bien : fila.datos.wr.tono === "mal" ? Tema.mal : Tema.texto) : Tema.texto3
                font.family: Tema.mono
                font.pixelSize: 14
            }
            Text {
                visible: !!fila.datos && !fila.datos.wr.cargando
                anchors.right: parent.right
                text: fila.datos && !fila.datos.wr.cargando ? fila.datos.wr.linea2 : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
    }
    component EquipoOv: Rectangle {
        id: equipo

        property string nombre
        property color marca
        property var filas: []

        height: 30 + 5 * 54
        color: Tema.panel
        border.color: Tema.linea
        radius: Tema.radio
        clip: true

        Row {
            x: 12
            y: 9
            spacing: 8

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 8
                height: 8
                radius: 1
                color: equipo.marca
            }
            Etiqueta {
                text: equipo.nombre
                color: Tema.texto2
            }
        }
        Column {
            y: 30
            width: parent.width

            Repeater {
                model: equipo.filas

                Column {
                    id: f

                    required property var modelData
                    required property int index

                    width: equipo.width

                    Rectangle {
                        visible: f.index > 0
                        width: parent.width
                        height: 1
                        color: Tema.linea
                    }
                    FilaOv {
                        width: parent.width
                        datos: f.modelData
                    }
                }
            }
        }
    }

    Rectangle {
        // Al tamaño de la ventana (no de su contentItem, que escondida mide 0). Opaca: la opacidad de Qt la funde con
        // el juego entera.
        width: ov.width
        height: ov.height
        color: Tema.fondo
        border.color: Tema.linea2

        Row {
            // Esperando la partida.
            visible: !ov.d || ov.d.esperando
            x: 16
            y: 14
            spacing: 12

            Logo {
                anchors.verticalCenter: parent.verticalCenter
                tam: 18
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Deep Prep"
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Esperando la partida…"
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
            }
        }
        Column {
            visible: !!ov.d && !ov.d.esperando
            x: 16
            y: 12
            width: parent.width - 32
            height: parent.height - 24
            spacing: 12

            Item {
                width: parent.width
                height: 24

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12

                    Logo {
                        anchors.verticalCenter: parent.verticalCenter
                        tam: 18
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ov.d ? ov.d.titulo || "" : ""
                        color: Tema.texto
                        font.family: Tema.sans
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                    Etiqueta {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ov.d ? ov.d.cola || "" : ""
                    }
                }
                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ov.d ? ov.d.atajo || "" : ""
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 12
                    }
                    Teclas {
                        anchors.verticalCenter: parent.verticalCenter
                        lista: ov.d && ov.d.teclas ? ov.d.teclas : []
                    }
                    Reloj {
                        anchors.verticalCenter: parent.verticalCenter
                        raya: false
                        font.pixelSize: 16
                    }
                }
            }
            Row {
                width: parent.width
                spacing: 12

                EquipoOv {
                    width: (parent.width - 12) / 2
                    nombre: "Tu equipo"
                    marca: Tema.aliado
                    filas: ov.d && ov.d.aliado ? ov.d.aliado : []
                }
                EquipoOv {
                    width: (parent.width - 12) / 2
                    nombre: "Rival"
                    marca: Tema.rival
                    filas: ov.d && ov.d.rival ? ov.d.rival : []
                }
            }
            Row {
                id: pie

                readonly property real alto: parent.height - 24 - 12 - (30 + 5 * 54) - 12

                width: parent.width
                height: alto
                spacing: 12

                Caja {
                    visible: !ov.basico
                    width: (pie.width - (ov.conDuelo ? 24 : 12)) * (ov.conDuelo ? 1.1 / 3 : 1.35 / 2.35)
                    height: pie.alto
                    relleno: 12
                    clip: true
                    titulo: ov.d && ov.d.jungla ? ov.d.jungla.titulo : "Jungla rival"
                    sub: ov.d && ov.d.jungla ? ov.d.jungla.sub : ""

                    Text {
                        visible: !ov.d || !ov.d.jungla
                        text: "Sin datos."
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                    Tarjetas {
                        visible: !!ov.d && !!ov.d.jungla
                        width: parent.width
                        compacto: true
                        columns: ov.conDuelo ? 2 : 3
                        lista: ov.d && ov.d.jungla ? ov.d.jungla.tarjetas : []
                    }
                }
                CajaDuelo {
                    visible: ov.conDuelo
                    width: (pie.width - 24) * 0.9 / 3
                    height: pie.alto
                    clip: true
                    compacto: true
                    datos: ov.d ? ov.d.duelo : null
                }
                Caja {
                    id: destacado

                    readonly property var dd: ov.d ? ov.d.destacado : null

                    width: ov.basico ? pie.width : (pie.width - (ov.conDuelo ? 24 : 12)) * (ov.conDuelo ? 1 / 3 : 1 / 2.35)
                    height: pie.alto
                    relleno: 12
                    clip: true
                    titulo: dd ? dd.titulo : ""

                    Repeater {
                        model: destacado.dd ? destacado.dd.notas : []

                        Text {
                            required property var modelData

                            width: destacado.anchoDentro
                            bottomPadding: 6
                            textFormat: Text.StyledText
                            text: `<b><font color="${modelData.rival ? Tema.rival : Tema.aliado}">${modelData.campeon.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</font></b> ` + modelData.texto.replace(/&/g, "&amp;").replace(/</g, "&lt;")
                            color: Tema.texto2
                            font.family: Tema.sans
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                    Lista {
                        visible: !!destacado.dd && destacado.dd.plan.length > 0
                        width: destacado.anchoDentro
                        marca: "numero"
                        tamLetra: 13
                        elementos: destacado.dd ? destacado.dd.plan : []
                    }
                    Lista {
                        width: destacado.anchoDentro
                        tamLetra: 13
                        elementos: destacado.dd ? destacado.dd.avisos : []
                    }
                    Text {
                        visible: !!destacado.dd && destacado.dd.notas.length + destacado.dd.plan.length + destacado.dd.avisos.length === 0
                        text: "Nada que destacar."
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                }
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// La revisión de una partida: cabecera, cifras, el gráfico de la partida y tus muertes.
Rectangle {
    id: detalle

    property var r

    component Titulo: Row {
        id: titulo

        property alias texto: rotulo.text
        property string cuenta: ""

        topPadding: 32
        bottomPadding: 12
        spacing: 8

        Etiqueta {
            id: rotulo

            anchors.verticalCenter: parent.verticalCenter
            color: Tema.texto2
        }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            visible: parent.cuenta !== ""
            width: cuentaTxt.width + 12
            height: cuentaTxt.height + 2
            radius: 2
            color: "transparent"
            border.color: Tema.linea2

            Etiqueta {
                id: cuentaTxt

                anchors.centerIn: parent
                text: titulo.cuenta
                color: Tema.texto
            }
        }
    }

    implicitHeight: r ? col.height + 48 : vacio.height + 40
    color: Tema.panel
    border.color: Tema.linea
    radius: Tema.radio

    Text {
        id: vacio

        x: 20
        y: 20
        visible: !detalle.r
        text: "Elige una partida de la lista."
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
    }
    Column {
        id: col

        x: 24
        y: 24
        width: detalle.width - 48
        visible: !!detalle.r

        Item {
            // Cabecera: retrato, cuándo y en qué liga, el resultado.
            width: parent.width
            height: 64

            Retrato {
                id: heroe

                tam: 64
                anillo: true
                fuente: detalle.r ? detalle.r.retrato : ""
            }
            Column {
                anchors.left: heroe.right
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Row {
                    Etiqueta {
                        text: detalle.r ? detalle.r.cabecera + (detalle.r.lp.txt ? " · " : "") : ""
                    }
                    Etiqueta {
                        text: detalle.r ? detalle.r.lp.txt : ""
                        color: detalle.r ? Tema.tono(detalle.r.lp.tono) : Tema.texto3
                    }
                }
                Row {
                    Text {
                        text: detalle.r ? detalle.r.resultado : ""
                        color: detalle.r && detalle.r.gana ? Tema.bien : Tema.mal
                        font.family: Tema.sans
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.48
                    }
                    Text {
                        leftPadding: 10
                        rightPadding: 10
                        text: "·"
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 24
                    }
                    Text {
                        text: detalle.r ? detalle.r.campeon : ""
                        color: Tema.texto
                        font.family: Tema.sans
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.48
                    }
                    Text {
                        leftPadding: 10
                        rightPadding: 10
                        text: "·"
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 24
                    }
                    Text {
                        text: detalle.r ? detalle.r.duracion : ""
                        color: Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.48
                    }
                }
            }
            Boton {
                id: grabacion

                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: detalle.r ? detalle.r.grabacion : false
                texto: "Abrir la grabación"
                icono: "carpeta"
                onPulsar: puente.llamar("carpeta", [detalle.r.id], r => {
                    if (!r.ok)
                        grabacion.texto = r.error;
                })
            }
        }
        Item {
            width: 1
            height: 24
        }
        Item {
            // Las cifras de la partida.
            width: parent.width
            height: 92

            Rectangle {
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Rectangle {
                y: parent.height - 1
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Row {
                anchors.fill: parent

                Repeater {
                    model: detalle.r ? detalle.r.metricas : []

                    Item {
                        id: metrica

                        required property var modelData
                        required property int index

                        width: col.width / 5
                        height: 92

                        Rectangle {
                            visible: metrica.index > 0
                            width: 1
                            height: parent.height
                            color: Tema.linea
                        }
                        Column {
                            x: metrica.index > 0 ? 20 : 0
                            y: 16
                            spacing: 6

                            Etiqueta {
                                text: metrica.modelData.que
                            }
                            Row {
                                Repeater {
                                    // KDA con las barras más suaves; el resto, una cifra.
                                    model: metrica.modelData.kda ? metrica.modelData.kda : [metrica.modelData.v]

                                    Row {
                                        id: cifra

                                        required property string modelData
                                        required property int index

                                        Text {
                                            visible: cifra.index > 0
                                            text: " / "
                                            color: Tema.texto3
                                            font.family: Tema.mono
                                            font.pixelSize: 24
                                            font.letterSpacing: -0.48
                                        }
                                        Text {
                                            text: cifra.modelData
                                            color: Tema.texto
                                            font.family: Tema.mono
                                            font.pixelSize: 24
                                            font.letterSpacing: -0.48
                                        }
                                    }
                                }
                            }
                            Text {
                                visible: !!metrica.modelData.sub
                                text: metrica.modelData.sub || ""
                                color: Tema.texto3
                                font.family: Tema.sans
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
        }
        Titulo {
            texto: "La partida"
        }
        GraficoOro {
            visible: !!(detalle.r && detalle.r.grafico)
            width: parent.width
            datos: detalle.r ? detalle.r.grafico : null
        }
        Titulo {
            texto: "Tus muertes"
            cuenta: detalle.r ? String(detalle.r.muertes.length) : ""
        }
        Repeater {
            model: detalle.r ? detalle.r.muertes : []

            Item {
                id: muerte

                required property var modelData
                required property int index
                readonly property real libre: width - 56 - 200 - 3 * 16

                width: col.width
                height: 54

                Rectangle {
                    width: parent.width
                    height: 1
                    color: Tema.linea
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: muerte.modelData.t
                    color: Tema.texto
                    font.family: Tema.mono
                    font.pixelSize: 14
                }
                Column {
                    x: 72
                    anchors.verticalCenter: parent.verticalCenter
                    width: muerte.libre * 1.4 / 2.4

                    Row {
                        spacing: 6

                        Text {
                            text: muerte.modelData.asesino
                            color: Tema.texto
                            font.family: Tema.sans
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Text {
                            visible: muerte.modelData.ayudas !== ""
                            text: "+ " + muerte.modelData.ayudas
                            color: Tema.texto3
                            font.family: Tema.sans
                            font.pixelSize: 14
                        }
                    }
                    Text {
                        width: parent.width
                        text: muerte.modelData.linea2
                        color: Tema.texto3
                        elide: Text.ElideRight
                        font.family: Tema.sans
                        font.pixelSize: 12
                    }
                }
                Row {
                    x: 72 + muerte.libre * 1.4 / 2.4 + 16
                    anchors.verticalCenter: parent.verticalCenter
                    width: muerte.libre / 2.4
                    spacing: 8

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: muerte.modelData.perdido !== ""
                        width: 6
                        height: 6
                        radius: 3
                        color: Tema.mal
                    }
                    Text {
                        text: muerte.modelData.perdido || "sin objetivo perdido"
                        color: muerte.modelData.perdido ? Tema.texto : Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 14
                    }
                }
                Boton {
                    id: botonClip

                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    visible: muerte.modelData.clip
                    pequeno: true
                    icono: "play"
                    texto: "Ver clip"
                    onPulsar: puente.llamar("clip", [detalle.r.id, muerte.index], r => {
                        if (!r.ok)
                            botonClip.texto = r.error;
                    })
                }
                Text {
                    // Sin clip, en qué vídeo y en qué minuto está.
                    visible: !muerte.modelData.clip && muerte.modelData.video !== ""
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: muerte.modelData.video
                    color: Tema.texto3
                    font.family: Tema.mono
                    font.pixelSize: 12
                }
            }
        }
        Text {
            visible: !!detalle.r && detalle.r.muertes.length === 0
            text: "No moriste ni una vez."
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 14
        }
        Grid {
            // Contra el jungla rival, minuto a minuto, y lo que preveía el panel.
            columns: col.width > 700 ? 2 : 1
            columnSpacing: 40
            width: col.width

            Column {
                width: col.width > 700 ? (col.width - 40) / 2 : col.width

                Titulo {
                    texto: detalle.r && detalle.r.comparacion ? "Contra " + detalle.r.comparacion.rival : "Contra el jungla rival"
                }
                Text {
                    visible: !!detalle.r && !detalle.r.comparacion
                    text: "Sin jungla rival con el que comparar."
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                }
                Grid {
                    visible: !!detalle.r && !!detalle.r.comparacion
                    columns: 5
                    width: parent.width
                    rowSpacing: 0

                    Repeater {
                        model: ["", "Oro", "CS", "Exp.", "Nivel"]

                        Etiqueta {
                            required property string modelData
                            required property int index

                            width: index === 0 ? 64 : (parent.width - 64) / 4
                            bottomPadding: 8
                            text: modelData
                        }
                    }
                    Repeater {
                        model: detalle.r && detalle.r.comparacion ? detalle.r.comparacion.filas : []

                        Repeater {
                            id: filaComp

                            required property var modelData

                            model: [
                                {
                                    txt: "Min " + filaComp.modelData.min,
                                    tono: "",
                                    rotulo: true
                                },
                                filaComp.modelData.oro, filaComp.modelData.cs, filaComp.modelData.xp, filaComp.modelData.nivel]

                            Item {
                                id: celda

                                required property var modelData
                                required property int index

                                width: index === 0 ? 64 : (detalle.width - 48 > 700 ? ((detalle.width - 48 - 40) / 2 - 64) / 4 : (detalle.width - 48 - 64) / 4)
                                height: 37

                                Rectangle {
                                    width: parent.width
                                    height: 1
                                    color: Tema.linea
                                }
                                Etiqueta {
                                    visible: !!celda.modelData.rotulo
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: celda.modelData.txt
                                }
                                Text {
                                    visible: !celda.modelData.rotulo
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: celda.modelData.txt
                                    color: Tema.tono(celda.modelData.tono)
                                    font.family: Tema.mono
                                    font.pixelSize: 15
                                }
                            }
                        }
                    }
                }
            }
            Column {
                width: col.width > 700 ? (col.width - 40) / 2 : col.width

                Titulo {
                    texto: "Lo que preveía el panel"
                }
                Text {
                    visible: !!detalle.r && detalle.r.prevision.length === 0
                    text: "Sin datos del panel de esa partida."
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                }
                Repeater {
                    model: detalle.r ? detalle.r.prevision : []

                    Column {
                        id: prev

                        required property var modelData
                        required property int index

                        width: parent.width
                        topPadding: prev.index > 0 ? 10 : 0
                        bottomPadding: 10
                        spacing: 2

                        Rectangle {
                            visible: prev.index > 0
                            width: parent.width
                            height: 1
                            color: Tema.linea
                        }
                        Item {
                            width: parent.width
                            height: 20

                            Text {
                                text: prev.modelData.tema
                                color: Tema.texto
                                font.family: Tema.sans
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Row {
                                anchors.right: parent.right
                                spacing: 6

                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: prev.modelData.acierto ? Tema.bien : Tema.mal
                                }
                                Text {
                                    text: prev.modelData.acierto ? "Acertó" : "Falló"
                                    color: Tema.texto
                                    font.family: Tema.sans
                                    font.pixelSize: 13
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: "Decía: " + prev.modelData.dijo
                            color: Tema.texto3
                            font.family: Tema.sans
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                        Text {
                            width: parent.width
                            text: "Pasó: " + prev.modelData.paso
                            color: Tema.texto2
                            font.family: Tema.sans
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
        Column {
            visible: !!detalle.r && !!detalle.r.referencia
            width: col.width

            Titulo {
                texto: detalle.r ? detalle.r.ref_titulo : ""
            }
            TablaComparacion {
                width: parent.width
                datos: detalle.r ? detalle.r.referencia : null
            }
        }
        Titulo {
            texto: "Objetivos"
        }
        Text {
            visible: !!detalle.r && detalle.r.objetivos.length === 0
            text: "Nadie hizo objetivos épicos."
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 14
        }
        Grid {
            columns: 2
            columnSpacing: 40
            width: col.width

            Repeater {
                model: detalle.r ? detalle.r.objetivos : []

                Item {
                    id: objetivo

                    required property var modelData

                    width: (col.width - 40) / 2
                    height: 33

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Tema.linea
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: objetivo.modelData.t
                        color: Tema.texto3
                        font.family: Tema.mono
                        font.pixelSize: 13
                    }
                    Text {
                        x: 52
                        anchors.verticalCenter: parent.verticalCenter
                        text: objetivo.modelData.nombre
                        color: objetivo.modelData.tuyo ? Tema.aliado : Tema.rival
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: objetivo.modelData.quien
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                }
            }
        }
    }
}

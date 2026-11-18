pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Barra lateral: la marca (arriba, dentro de la barra de la ventana), las pestañas, los avisos (revisión nueva,
// versión nueva) y el estado (fase del cliente, grabación, cuenta y consultas a Riot). Estrecha, solo iconos.
Rectangle {
    id: lateral

    property string vista
    property var comun: ({})
    property bool compacta: false
    property bool revisionNueva: false

    signal elegir(string vista)
    signal verRevisionNueva

    width: compacta ? 64 : Tema.barra
    color: Tema.panel

    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Tema.linea
    }
    Rectangle {
        // La línea de la barra de la ventana sigue por aquí: la barra es una sola, de lado a lado.
        y: Tema.altoBarra - 1
        width: parent.width
        height: 1
        color: Tema.linea
    }
    Row {
        x: lateral.compacta ? 22 : 20
        height: Tema.altoBarra - 1
        spacing: 10

        Logo {
            anchors.verticalCenter: parent.verticalCenter
            tam: 20
        }
        Text {
            visible: !lateral.compacta
            anchors.verticalCenter: parent.verticalCenter
            text: "Deep Prep"
            color: Tema.texto
            font.family: Tema.sans
            font.pixelSize: 15
            font.weight: Font.DemiBold
            font.letterSpacing: -0.15
        }
    }
    Column {
        x: 12
        y: Tema.altoBarra + 12
        width: lateral.width - 24
        spacing: 2

        Repeater {
            model: [
                {
                    v: "partida",
                    t: "Partida"
                },
                {
                    v: "revisiones",
                    t: "Revisiones"
                },
                {
                    v: "ajustes",
                    t: "Ajustes"
                }
            ]

            Rectangle {
                id: pestana

                required property var modelData
                readonly property bool activa: lateral.vista === modelData.v

                width: parent.width
                height: 36
                radius: Tema.radio
                color: activa ? Tema.panel2 : zona.containsMouse ? Tema.hover : "transparent"

                Rectangle {
                    visible: pestana.activa
                    width: 2
                    height: parent.height
                    color: Tema.acento
                }
                Row {
                    x: lateral.compacta ? (parent.width - 16) / 2 : 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12

                    Icono {
                        anchors.verticalCenter: parent.verticalCenter
                        nombre: pestana.modelData.v
                        color: pestana.activa ? Tema.acento : zona.containsMouse ? Tema.texto : Tema.texto2
                    }
                    Text {
                        visible: !lateral.compacta
                        anchors.verticalCenter: parent.verticalCenter
                        text: pestana.modelData.t
                        color: pestana.activa || zona.containsMouse ? Tema.texto : Tema.texto2
                        font.family: Tema.sans
                        font.pixelSize: 14
                        font.weight: Font.Medium
                    }
                }
                MouseArea {
                    id: zona

                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: lateral.elegir(pestana.modelData.v)
                }
                Tip {
                    enabled: lateral.compacta
                    texto: lateral.compacta ? pestana.modelData.t : ""
                }
            }
        }
        Item {
            width: 1
            height: 6
        }
        Rectangle {
            // Revisión nueva lista: lleva a ella.
            visible: lateral.revisionNueva
            width: parent.width
            height: Math.max(36, avisoRev.implicitHeight + 16)
            radius: Tema.radio
            color: zonaRev.containsMouse ? Tema.alfa(Tema.acento, 0.18) : Tema.alfa(Tema.acento, 0.12)
            border.color: zonaRev.containsMouse ? Tema.acento : Tema.alfa(Tema.acento, 0.35)

            Row {
                id: avisoRev

                x: lateral.compacta ? (parent.width - 6) / 2 : 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6
                    height: 6
                    radius: 3
                    color: Tema.acento
                }
                Text {
                    visible: !lateral.compacta
                    text: "Revisión nueva lista"
                    color: Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: 13
                }
            }
            MouseArea {
                id: zonaRev

                anchors.fill: parent
                hoverEnabled: true
                onClicked: lateral.verRevisionNueva()
            }
        }
    }
    Column {
        x: 12
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 16
        width: lateral.width - 24
        spacing: 12

        Rectangle {
            // Versión nueva descargada: «Actualizar ahora» la instala ya (fuera de cola y de partida); si no, se instala
            // sola al cerrar la ventana. Estrecha, el aviso entero es el botón.
            id: avisoVersion

            property bool instalando: false
            property string error: ""

            function actualizar() {
                if (instalando)
                    return;
                instalando = true;
                error = "";
                puente.llamar("actualizar", [], r => {
                    if (r && r.ok)
                        return; // la app se cierra y la versión nueva se abre sola
                    avisoVersion.instalando = false;
                    avisoVersion.error = r && r.error ? r.error : "No se ha podido.";
                    if (lateral.compacta)
                        Window.window.avisar(avisoVersion.error, "", avisoVersion);
                    finError.restart();
                });
            }

            visible: !!lateral.comun.version
            width: parent.width
            height: lateral.compacta ? 36 : versionTxt.implicitHeight + 20
            radius: Tema.radio
            color: lateral.compacta && zonaVersion.containsMouse ? Tema.alfa(Tema.acento, 0.18) : Tema.alfa(Tema.acento, 0.12)
            border.color: lateral.compacta && zonaVersion.containsMouse ? Tema.acento : Tema.alfa(Tema.acento, 0.35)

            Timer {
                id: finError

                interval: 10000
                onTriggered: avisoVersion.error = ""
            }
            MouseArea {
                id: zonaVersion

                enabled: lateral.compacta
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: avisoVersion.actualizar()
            }
            Tip {
                enabled: lateral.compacta
                texto: lateral.compacta ? (avisoVersion.instalando ? "Instalando la versión " + (lateral.comun.version || "") : "Versión " + (lateral.comun.version || "") + " lista") : ""
                texto2: avisoVersion.instalando ? "Se cierra y vuelve a abrirse en unos segundos." : "Pulsa para actualizar ahora."
            }
            Row {
                x: lateral.compacta ? (parent.width - 6) / 2 : 8
                y: lateral.compacta ? (parent.height - 6) / 2 - 6 : 10
                spacing: 10

                Rectangle {
                    y: 6
                    width: 6
                    height: 6
                    radius: 3
                    color: Tema.acento
                }
                Column {
                    id: versionTxt

                    visible: !lateral.compacta
                    width: lateral.width - 24 - 34
                    spacing: 2

                    Text {
                        text: (avisoVersion.instalando ? "Instalando la " : "Versión ") + (lateral.comun.version || "") + (avisoVersion.instalando ? "" : " lista")
                        color: Tema.texto
                        font.family: Tema.sans
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Text {
                        width: parent.width
                        text: avisoVersion.instalando ? "La app se cierra y vuelve a abrirse en unos segundos." : avisoVersion.error ? avisoVersion.error : "Instálala ahora (tarda unos segundos) o se instalará sola cuando cierres esta ventana, fuera de partida."
                        color: avisoVersion.error && !avisoVersion.instalando ? Tema.mal : Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                    Item {
                        visible: !avisoVersion.instalando
                        width: 1
                        height: 6
                    }
                    Boton {
                        visible: !avisoVersion.instalando
                        texto: "Actualizar ahora"
                        primario: true
                        pequeno: true
                        onPulsar: avisoVersion.actualizar()
                    }
                }
            }
        }
        Column {
            visible: !lateral.compacta
            width: parent.width
            spacing: 10

            Rectangle {
                width: parent.width
                height: 1
                color: Tema.linea
            }
            Column {
                x: 8
                width: parent.width - 16
                topPadding: 6
                spacing: 10

                Etiqueta {
                    text: "Estado"
                }
                Repeater {
                    // La fase del cliente y, si la hay, la grabación.
                    model: [lateral.comun.fase, lateral.comun.grabacion].filter(x => !!x)

                    Item {
                        id: chip

                        required property var modelData
                        readonly property bool late: modelData.tono === "vivo" || modelData.tono === "rec"

                        implicitWidth: filaChip.implicitWidth
                        implicitHeight: filaChip.implicitHeight

                        Row {
                            id: filaChip

                            spacing: 8

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 6
                                height: 6
                                radius: 3
                                color: chip.modelData.tono === "vivo" ? Tema.bien : chip.modelData.tono === "rec" ? Tema.rival : chip.modelData.tono === "parada" ? Tema.mal : chip.modelData.tono === "activo" ? Tema.texto2 : Tema.texto3

                                SequentialAnimation on opacity {
                                    running: chip.late
                                    loops: Animation.Infinite
                                    NumberAnimation {
                                        to: 0.3
                                        duration: 1500
                                        easing.type: Easing.InOutSine
                                    }
                                    NumberAnimation {
                                        to: 1
                                        duration: 1500
                                        easing.type: Easing.InOutSine
                                    }
                                }
                            }
                            Text {
                                text: chip.modelData.txt
                                color: chip.late ? Tema.texto : chip.modelData.tono === "parada" ? Tema.mal : Tema.texto2
                                font.family: Tema.sans
                                font.pixelSize: 13
                            }
                        }
                        Tip {
                            texto: chip.modelData.tip || ""
                        }
                    }
                }
                Text {
                    visible: !!lateral.comun.cuenta
                    width: parent.width
                    text: lateral.comun.cuenta || ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                Item {
                    width: parent.width
                    height: cuota.implicitHeight

                    Column {
                        id: cuota

                        width: parent.width
                        spacing: 6

                        Item {
                            width: parent.width
                            height: cuotaTxt.height

                            Text {
                                id: cuotaTxt

                                text: "Consultas a Riot"
                                color: Tema.texto3
                                font.family: Tema.sans
                                font.pixelSize: 12
                            }
                            Text {
                                anchors.right: parent.right
                                text: lateral.comun.cuota ? lateral.comun.cuota.txt : ""
                                color: Tema.texto3
                                font.family: Tema.mono
                                font.pixelSize: 12
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: 2
                            color: Tema.linea2

                            Rectangle {
                                width: parent.width * (lateral.comun.cuota ? lateral.comun.cuota.ancho : 0)
                                height: parent.height
                                color: lateral.comun.cuota && lateral.comun.cuota.lleno ? Tema.mal : Tema.texto3

                                Behavior on width {
                                    NumberAnimation {
                                        duration: 400
                                        easing.type: Easing.OutCubic
                                    }
                                }
                            }
                        }
                    }
                    Tip {
                        texto: "Consultas a Riot en los últimos 2 minutos"
                    }
                }
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Un jugador de la tabla de equipos (vistas.fila): posición, retrato, nombre y etiquetas, rango, últimas partidas y
// con su campeón. Tu fila, en violeta.
Rectangle {
    id: fila

    property var datos
    property bool basico: false // fuera de la Grieta: sin sus últimas partidas ni «con su campeón»
    // Anchos de las columnas de texto (los reparte TablaEquipos).
    property real anchoNombre: 200
    property real anchoRango: 160
    property real anchoForma: 120

    implicitHeight: Math.max(64, nombre.implicitHeight + 24)
    color: datos && datos.soy_yo ? (zona.containsMouse ? "#1a1826" : Tema.yo) : zona.containsMouse ? Tema.hover : "transparent"

    Behavior on color {
        ColorAnimation {
            duration: 150
        }
    }
    MouseArea {
        id: zona

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
    Rectangle {
        visible: !!fila.datos && fila.datos.soy_yo
        width: 2
        height: parent.height
        color: Tema.acento
    }
    Rol {
        x: 20
        anchors.verticalCenter: parent.verticalCenter
        nombre: fila.datos ? fila.datos.rol.icono : ""

        Tip {
            texto: fila.datos ? fila.datos.rol.txt : ""
        }
    }
    Retrato {
        x: 52
        anchors.verticalCenter: parent.verticalCenter
        fuente: fila.datos ? fila.datos.retrato : ""
    }
    Column {
        id: nombre

        x: 108
        anchors.verticalCenter: parent.verticalCenter
        width: fila.anchoNombre

        Item {
            // El nombre: al pulsarlo se copia el Riot ID (para buscarlo luego en op.gg o donde sea).
            id: nombreJugador

            readonly property string riotId: fila.datos ? fila.datos.riot_id || "" : ""

            width: parent.width
            height: filaNombre.implicitHeight

            Row {
                id: filaNombre

                width: parent.width
                spacing: 4

                Text {
                    text: fila.datos ? fila.datos.nombre : ""
                    color: fila.datos && fila.datos.soy_yo ? Tema.acento : Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    font.underline: zonaNombre.containsMouse && nombreJugador.riotId !== ""
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, parent.width - tag.implicitWidth - 4)
                }
                Text {
                    id: tag

                    visible: !!fila.datos && fila.datos.tag !== ""
                    text: fila.datos ? "#" + fila.datos.tag : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                }
            }
            MouseArea {
                id: zonaNombre

                width: filaNombre.childrenRect.width
                height: parent.height
                enabled: nombreJugador.riotId !== ""
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onContainsMouseChanged: {
                    const w = Window.window;
                    if (!w)
                        return;
                    if (containsMouse)
                        w.mostrarTip("Copiar " + nombreJugador.riotId, "Para buscarlo luego en op.gg o donde quieras", nombreJugador);
                    else
                        w.esconderTip(nombreJugador);
                }
                onClicked: {
                    puente.copiar(nombreJugador.riotId);
                    Window.window.avisar("Copiado: " + nombreJugador.riotId, "Pégalo en el buscador de op.gg", nombreJugador);
                }
            }
        }
        Text {
            width: parent.width
            text: fila.datos ? fila.datos.campeon : ""
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 12
            elide: Text.ElideRight

            Tip {
                texto: fila.datos ? fila.datos.mains : ""
            }
        }
        Etiquetas {
            visible: !!fila.datos && fila.datos.etiquetas.length > 0
            width: parent.width
            topPadding: 4
            lista: fila.datos ? fila.datos.etiquetas : []
        }
    }
    Rango {
        x: 108 + fila.anchoNombre + 16
        anchors.verticalCenter: parent.verticalCenter
        width: fila.anchoRango
        datos: fila.datos ? fila.datos.rango : null
    }
    Column {
        // Últimas partidas: victorias y derrotas, y la racha.
        visible: !fila.basico
        x: 108 + fila.anchoNombre + 16 + fila.anchoRango + 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Text {
            visible: !!fila.datos && !fila.datos.forma
            text: fila.datos ? fila.datos.cargando : ""
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 14
        }
        Rico {
            visible: !!fila.datos && !!fila.datos.forma
            text: fila.datos && fila.datos.forma ? fila.datos.forma.txt : ""
            wrapMode: Text.NoWrap
        }
        Racha {
            visible: !!fila.datos && !!fila.datos.forma && !!fila.datos.forma.racha
            datos: fila.datos && fila.datos.forma ? fila.datos.forma.racha : null
        }
    }
    Column {
        // Con su campeón: % de victorias, partidas y su KDA medio.
        x: 108 + fila.anchoNombre + 16 + fila.anchoRango + 16 + fila.anchoForma + 16
        anchors.verticalCenter: parent.verticalCenter
        visible: !!fila.datos && !!fila.datos.con_campeon
        spacing: 2

        Text {
            visible: !!fila.datos && !!fila.datos.con_campeon && !!fila.datos.con_campeon.ninguna
            text: "Ninguna reciente"
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 12
        }
        Row {
            visible: !!fila.datos && !!fila.datos.con_campeon && !fila.datos.con_campeon.ninguna
            spacing: 8

            Rico {
                anchors.verticalCenter: parent.verticalCenter
                text: fila.datos && fila.datos.con_campeon && fila.datos.con_campeon.txt ? fila.datos.con_campeon.txt : ""
                wrapMode: Text.NoWrap
            }
            BarraWr {
                anchors.verticalCenter: parent.verticalCenter
                width: 40
                datos: fila.datos && fila.datos.con_campeon ? fila.datos.con_campeon.barra : null
            }
        }
        Text {
            visible: !!fila.datos && !!fila.datos.con_campeon && !!fila.datos.con_campeon.kda
            text: fila.datos && fila.datos.con_campeon ? fila.datos.con_campeon.kda || "" : ""
            color: Tema.texto3
            font.family: Tema.mono
            font.pixelSize: 12
        }
    }
}

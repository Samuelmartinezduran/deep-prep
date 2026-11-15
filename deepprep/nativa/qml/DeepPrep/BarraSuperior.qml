import QtQuick
import DeepPrep

// La barra de arriba es también la de la ventana: se arrastra desde cualquier hueco, con doble clic se maximiza y con
// el botón derecho sale el menú de Windows. Lo que es de la app (la búsqueda, los botones) se lo dice a marco.
Rectangle {
    id: barra

    property string titulo
    property Window ventanaPrincipal
    property string error: ""

    signal buscado

    // La partida en vivo de cualquier jugador: si la encuentra, se abre en la pestaña Partida.
    function buscar() {
        const rid = entrada.text.trim();
        if (!rid)
            return;
        barra.error = "Buscando…";
        puente.llamar("buscar", [rid], r => {
            barra.error = r.ok ? "" : r.error;
            if (r.ok) {
                entrada.text = "";
                barra.buscado();
            }
        });
    }

    height: Tema.altoBarra
    color: Tema.fondo

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Tema.linea
    }
    Text {
        anchors.left: parent.left
        anchors.leftMargin: 32
        anchors.verticalCenter: parent.verticalCenter
        text: barra.titulo
        color: Tema.texto
        font.family: Tema.sans
        font.pixelSize: 15
        font.weight: Font.DemiBold
    }
    Row {
        anchors.right: botones.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 16

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: barra.error !== ""
            text: barra.error
            color: Tema.mal
            font.family: Tema.sans
            font.pixelSize: 13
        }
        Row {
            spacing: 8

            Rectangle {
                id: campo

                width: 280
                height: 32
                radius: Tema.radio
                color: Tema.panel
                border.color: entrada.activeFocus ? Tema.acento : zonaCampo.containsMouse ? Tema.linea3 : Tema.linea2
                Component.onCompleted: marco.interactivo(campo)

                Icono {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    nombre: "buscar"
                    color: Tema.texto3
                }
                TextInput {
                    id: entrada

                    anchors.left: parent.left
                    anchors.leftMargin: 34
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    color: Tema.texto
                    selectionColor: Tema.alfa(Tema.acento, 0.3)
                    selectedTextColor: Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: 14
                    clip: true
                    selectByMouse: true
                    onAccepted: barra.buscar()

                    Text {
                        visible: !entrada.text && !entrada.preeditText
                        text: "Ver la partida de Nombre#TAG"
                        color: Tema.texto3
                        font: entrada.font
                    }
                }
                MouseArea {
                    id: zonaCampo

                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    cursorShape: Qt.IBeamCursor
                }
            }
            Boton {
                id: ver

                texto: "Ver"
                onPulsar: barra.buscar()
                Component.onCompleted: marco.interactivo(ver)
            }
        }
    }
    Row {
        id: botones

        anchors.right: parent.right
        anchors.top: parent.top

        BotonVentana {
            id: minimizar

            tipo: "min"
            activa: barra.ventanaPrincipal ? barra.ventanaPrincipal.active : true
            onPulsar: barra.ventanaPrincipal.showMinimized()
            Component.onCompleted: marco.interactivo(minimizar)
        }
        BotonVentana {
            id: maximizar

            tipo: "max"
            activa: barra.ventanaPrincipal ? barra.ventanaPrincipal.active : true
            maximizada: barra.ventanaPrincipal ? barra.ventanaPrincipal.visibility === Window.Maximized : false
            onPulsar: marco.alternar_maximizada()
            Component.onCompleted: marco.botonMaximizar(maximizar)
        }
        BotonVentana {
            id: cerrar

            tipo: "cerrar"
            activa: barra.ventanaPrincipal ? barra.ventanaPrincipal.active : true
            onPulsar: barra.ventanaPrincipal.close()
            Component.onCompleted: marco.interactivo(cerrar)
        }
    }
}

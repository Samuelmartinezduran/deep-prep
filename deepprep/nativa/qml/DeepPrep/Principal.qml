import QtQuick
import QtQuick.Window
import DeepPrep

// La ventana principal, sin el marco de Windows: su barra de arriba es la de la app (marco.py la integra con Windows).
// Empieza escondida: ventanas.py la prepara antes de enseñarla. Cerrarla solo la esconde (ventanas.cerrar decide).
Window {
    id: ventana

    property string vista: vistaInicial
    property string revisionAvisada: ""
    property bool novedadesCerradas: false
    readonly property var comun: puente.comun
    readonly property var titulos: ({
            "partida": "Partida",
            "revisiones": "Revisiones",
            "ajustes": "Ajustes"
        })

    // El detalle al pasar el ratón (Tip.qml): encima de todo, junto a la pieza, sin taparla.
    function mostrarTip(texto, texto2, pieza) {
        if (!texto)
            return;
        bocadillo.pieza = pieza;
        bocadillo.texto = texto;
        bocadillo.texto2 = texto2 || "";
        const p = pieza.mapToItem(ventana.contentItem, 0, 0);
        const x = p.x + pieza.width / 2 - bocadillo.width / 2;
        bocadillo.x = Math.max(8, Math.min(ventana.width - bocadillo.width - 8, x));
        bocadillo.y = p.y - bocadillo.height - 8 < Tema.altoBarra ? p.y + pieza.height + 8 : p.y - bocadillo.height - 8;
        bocadillo.visible = true;
    }
    function esconderTip(pieza) {
        if (bocadillo.pieza === pieza && !finAviso.running)
            bocadillo.visible = false;
    }
    // Un aviso breve junto a una pieza (p. ej. «Copiado»): se va solo.
    function avisar(texto, texto2, pieza) {
        finAviso.stop();
        mostrarTip(texto, texto2, pieza);
        finAviso.restart();
    }

    width: 1500
    height: 950
    minimumWidth: 1100
    minimumHeight: 700
    visible: false
    title: tituloVentana
    color: Tema.fondo
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint
    onClosing: cierre => cierre.accepted = ventanas.cerrar()
    onVistaChanged: bocadillo.visible = false

    BarraLateral {
        id: lateral

        height: ventana.height
        vista: ventana.vista
        comun: ventana.comun
        compacta: ventana.width <= 1280
        revisionNueva: !!ventana.comun.ultima_revision && ventana.comun.ultima_revision !== ventana.revisionAvisada && ventana.vista !== "revisiones"
        onElegir: v => ventana.vista = v
        onVerRevisionNueva: {
            ventana.revisionAvisada = ventana.comun.ultima_revision;
            ventana.vista = "revisiones";
        }
    }
    Column {
        id: contenido

        x: lateral.width
        width: ventana.width - lateral.width
        height: ventana.height

        BarraSuperior {
            id: cabecera

            width: parent.width
            titulo: ventana.titulos[ventana.vista]
            ventanaPrincipal: ventana
            onBuscado: if (ventana.vista !== "partida")
                ventana.vista = "partida"
        }
        BarraDemo {
            id: demo

            visible: !!ventana.comun.demo
            width: parent.width
            escenas: escenasDemo
            vista: ventana.vista
            demo: ventana.comun.demo
            onAbrir: v => ventana.vista = v
            onVerOverlay: ventanas.verOverlay()
        }
        BandaClave {
            visible: !!ventana.comun.clave
            width: parent.width
            error: ventana.comun.clave || ""
        }
        Novedades {
            id: novedades

            visible: !!ventana.comun.novedades && !ventana.novedadesCerradas
            width: parent.width
            datos: ventana.comun.novedades
            onCerrada: ventana.novedadesCerradas = true
        }
        Item {
            id: hueco

            width: parent.width
            height: ventana.height - cabecera.height - (demo.visible ? demo.height : 0) - (novedades.visible ? novedades.height : 0) - (ventana.comun.clave ? 56 : 0)

            VistaPartida {
                anchors.fill: parent
                visible: ventana.vista === "partida"
            }
            Revisiones {
                anchors.fill: parent
                visible: ventana.vista === "revisiones"
            }
            Ajustes {
                anchors.fill: parent
                visible: ventana.vista === "ajustes"
            }
        }
    }
    Timer {
        id: finAviso

        interval: 1600
        onTriggered: bocadillo.visible = false
    }
    Rectangle {
        id: bocadillo

        property Item pieza: null
        property string texto: ""
        property string texto2: ""

        visible: false
        z: 100
        width: Math.min(280, Math.max(linea1.implicitWidth, linea2.implicitWidth) + 24)
        height: col.implicitHeight + 16
        radius: Tema.radio
        color: Tema.panel2
        border.color: Tema.linea2

        Column {
            id: col

            x: 12
            y: 8
            width: bocadillo.width - 24
            spacing: 2

            Text {
                id: linea1

                width: Math.min(implicitWidth, 256)
                text: bocadillo.texto
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
            Text {
                id: linea2

                visible: bocadillo.texto2 !== ""
                width: Math.min(implicitWidth, 256)
                text: bocadillo.texto2
                color: Tema.texto2
                font.family: Tema.sans
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
        }
    }
}

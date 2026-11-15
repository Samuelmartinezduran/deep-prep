pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// El minimapa de la Grieta (Data Dragon) con puntos encima: dónde estaba el jungla rival o dónde moriste.
// Cada punto viene en fracciones de la imagen (vistas.en_mapa); al pasar, su detalle, y si lleva id, se puede pulsar.
// resaltado: los puntos con ese id (las muertes de la partida elegida) van en violeta, más grandes y por encima.
Rectangle {
    id: mapa

    property var puntos: [] // [{xy: [x, y], tip?, tip2?, id?}]
    property color colorPunto: Tema.texto
    property real tamPunto: 9
    property string resaltado: ""
    readonly property int nResaltados: resaltado === "" ? 0 : puntos.filter(p => p.id === resaltado).length

    signal pulsar(string id)

    implicitHeight: width
    color: Tema.fondo
    border.color: Tema.linea2
    radius: Tema.radio
    clip: true

    Image {
        anchors.fill: parent
        anchors.margins: 1
        source: "image://ddragon/mapa/map11"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        opacity: 0.55 // el mapa se lee, pero los puntos mandan
    }
    Rectangle {
        // Un velo frío: el verde del mapa no compite con el color de los puntos.
        anchors.fill: parent
        anchors.margins: 1
        color: Tema.alfa(Tema.fondo, 0.35)
    }
    Repeater {
        model: mapa.puntos

        Rectangle {
            id: punto

            required property var modelData
            readonly property bool encima: tip.containsMouse
            readonly property bool marcado: mapa.nResaltados > 0 && modelData.id === mapa.resaltado

            x: modelData.xy[0] * mapa.width - width / 2
            y: modelData.xy[1] * mapa.height - height / 2
            z: marcado ? 1 : 0
            width: mapa.tamPunto * (marcado ? 1.4 : 1) * (encima ? 1.5 : 1)
            height: width
            radius: width / 2
            color: marcado || (encima && punto.modelData.id) ? Tema.acento : mapa.colorPunto
            // Con una partida resaltada, las demás se atenúan.
            opacity: encima || marcado ? 1 : (mapa.nResaltados > 0 ? 0.4 : 0.8)
            border.width: 1.5
            border.color: Tema.alfa(Tema.fondo, 0.85)

            Behavior on width {
                NumberAnimation {
                    duration: 120
                }
            }
            Tip {
                id: tip

                texto: punto.modelData.tip || ""
                texto2: punto.modelData.tip2 || ""
                cursorShape: punto.modelData.id ? Qt.PointingHandCursor : Qt.ArrowCursor
            }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -4
                enabled: !!punto.modelData.id
                acceptedButtons: Qt.LeftButton
                onClicked: mapa.pulsar(punto.modelData.id)
            }
        }
    }
}

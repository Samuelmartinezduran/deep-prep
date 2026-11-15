pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Pestaña Revisiones: lo de hoy, tus tendencias, dónde mueres, las partidas revisadas y la revisión de la que elijas.
// Los datos se piden a la app al abrir la pestaña y cuando hay una revisión nueva (vistas.revisiones y detalle).
Hoja {
    id: vista

    property var datos: null
    property string elegida: ""
    property var revision: null
    property string error: ""
    property string filtro: "todas"
    readonly property bool estrecha: anchoContenido < 1100

    function cargar() {
        puente.llamar("revisiones", [], d => {
            if (!d || d.ok === false) {
                vista.error = d && d.error ? d.error : "No se han podido cargar las revisiones.";
                return;
            }
            vista.error = "";
            vista.datos = d;
            if (!vista.elegida && d.lista.length)
                vista.elegir(d.lista[0].id);
        });
    }
    function elegir(id) {
        elegida = id;
        puente.llamar("revision", [id], r => {
            if (vista.elegida === id)
                vista.revision = r;
        });
    }

    Component.onCompleted: if (visible)
        cargar()
    onVisibleChanged: if (visible)
        cargar()

    Connections {
        // Revisión nueva lista: se vuelve a leer la lista (y se abre esa, si viene del aviso).
        target: puente
        function onEstadoCambiado() {
            const u = puente.comun.ultima_revision;
            if (vista.visible && u && u !== vista.ultimaVista) {
                vista.ultimaVista = u;
                vista.cargar();
            }
        }
    }
    property string ultimaVista: ""

    Text {
        visible: vista.error !== ""
        text: vista.error
        color: Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 14
    }
    Item {
        // Hoy: victorias, derrotas, LP y la racha.
        id: bloqueHoy

        readonly property var hoy: vista.datos ? vista.datos.hoy : null

        visible: !!hoy
        width: vista.anchoContenido
        height: visible ? filaHoy.height + 25 : 0

        Row {
            id: filaHoy

            spacing: 40

            Column {
                spacing: 6

                Etiqueta {
                    text: "Hoy"
                }
                Text {
                    text: bloqueHoy.hoy ? `${bloqueHoy.hoy.v}V ${bloqueHoy.hoy.d}D` : ""
                    color: Tema.texto
                    font.family: Tema.mono
                    font.pixelSize: 22
                    font.letterSpacing: -0.44
                }
            }
            Column {
                readonly property var lp: bloqueHoy.hoy ? bloqueHoy.hoy.lp : null

                visible: !!lp
                spacing: 6

                Etiqueta {
                    text: "LP"
                }
                Text {
                    text: parent.lp ? parent.lp.txt : ""
                    color: parent.lp ? Tema.tono(parent.lp.tono) : Tema.texto
                    font.family: Tema.mono
                    font.pixelSize: 22
                    font.letterSpacing: -0.44
                }
            }
            Column {
                spacing: 6

                Etiqueta {
                    text: "Partidas"
                }
                Row {
                    spacing: 4

                    Repeater {
                        model: bloqueHoy.hoy ? bloqueHoy.hoy.racha : []

                        Rectangle {
                            required property bool modelData

                            width: 22
                            height: 22
                            radius: 2
                            color: "transparent"
                            border.color: Tema.linea2

                            Text {
                                anchors.centerIn: parent
                                text: parent.modelData ? "V" : "D"
                                color: parent.modelData ? Tema.bien : Tema.mal
                                font.family: Tema.mono
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Tema.linea
        }
    }
    Grid {
        // Tus tendencias y dónde mueres.
        visible: !!vista.datos && (!!vista.datos.tendencias || !!vista.datos.muertes)
        columns: vista.estrecha || !vista.datos || !vista.datos.tendencias || !vista.datos.muertes ? 1 : 2
        columnSpacing: 24
        rowSpacing: 24
        width: vista.anchoContenido

        Caja {
            id: tendencias

            readonly property var t: vista.datos ? vista.datos.tendencias : null

            visible: !!t
            width: vista.estrecha || !vista.datos || !vista.datos.muertes ? vista.anchoContenido : vista.anchoContenido - 360 - 24
            titulo: "Tus tendencias"
            sub: t ? t.sub : ""

            Grid {
                columns: 2
                columnSpacing: 32
                rowSpacing: 24
                width: parent.width

                Repeater {
                    model: tendencias.t ? tendencias.t.tablas : []

                    Column {
                        id: tabla

                        required property var modelData

                        width: (tendencias.anchoDentro - 32) / 2

                        Etiqueta {
                            bottomPadding: 8
                            text: tabla.modelData.nombre
                        }
                        Repeater {
                            model: tabla.modelData.filas

                            Rectangle {
                                id: filaT

                                required property var modelData

                                width: tabla.width
                                height: 33
                                color: zonaT.containsMouse ? Tema.hover : "transparent"

                                Rectangle {
                                    width: parent.width
                                    height: 1
                                    color: Tema.linea
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - 40 - 36 - 28 - 30
                                    text: filaT.modelData.nombre
                                    color: Tema.texto2
                                    font.family: Tema.sans
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                }
                                BarraWr {
                                    x: parent.width - 40 - 36 - 28 - 20
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 40
                                    datos: filaT.modelData.barra
                                }
                                Text {
                                    x: parent.width - 36 - 28 - 10
                                    width: 36
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: filaT.modelData.pct
                                    color: Tema.tono(filaT.modelData.tono) === Tema.texto3 ? Tema.texto2 : Tema.tono(filaT.modelData.tono)
                                    font.family: Tema.mono
                                    font.pixelSize: 13
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 28
                                    horizontalAlignment: Text.AlignRight
                                    text: filaT.modelData.n
                                    color: Tema.texto3
                                    font.family: Tema.mono
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: zonaT

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
                                Tip {
                                    texto: filaT.modelData.nombre + " · " + filaT.modelData.tip
                                }
                            }
                        }
                    }
                }
            }
        }
        Caja {
            id: muertes

            readonly property var m: vista.datos ? vista.datos.muertes : null

            visible: !!m
            width: vista.estrecha || !vista.datos || !vista.datos.tendencias ? Math.min(vista.anchoContenido, 420) : 360
            titulo: "Dónde mueres"
            sub: m ? `${m.n} muertes de tus partidas revisadas, todas vistas desde la base azul` : ""

            Selector {
                width: muertes.anchoDentro
                repartir: true
                opciones: muertes.m ? muertes.m.botones.map(x => ({
                            id: x.id,
                            txt: x.txt
                        })) : []
                actual: vista.filtro
                onElegir: id => vista.filtro = id
            }
            Item {
                width: 1
                height: 12
            }
            Mapa {
                id: mapaMuertes

                width: muertes.anchoDentro
                puntos: muertes.m ? muertes.m.puntos[vista.filtro] : []
                resaltado: vista.elegida // las de la partida que estás viendo, en violeta
                onPulsar: id => vista.elegir(id)
            }
            Text {
                readonly property int n: mapaMuertes.nResaltados

                width: muertes.anchoDentro
                topPadding: 8
                text: muertes.m ? `${muertes.m.puntos[vista.filtro].length} muertes` + (n === 1 ? "; la de esta partida, en violeta" : n > 1 ? `; las ${n} de esta partida, en violeta` : "") + ". Pulsa una para abrir su partida." : ""
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
    }
    Grid {
        // Las partidas revisadas y la que elijas.
        visible: !!vista.datos
        columns: vista.estrecha ? 1 : 2
        columnSpacing: 24
        rowSpacing: 24
        width: vista.anchoContenido

        Rectangle {
            width: vista.estrecha ? vista.anchoContenido : 304
            height: lista.height + 28
            color: Tema.panel
            border.color: Tema.linea
            radius: Tema.radio

            Column {
                id: lista

                x: 8
                y: 20
                width: parent.width - 16

                Row {
                    x: 12
                    spacing: 8
                    bottomPadding: 16

                    Etiqueta {
                        text: "Partidas revisadas"
                        color: Tema.texto2
                    }
                    Text {
                        anchors.baseline: parent.children[0].baseline
                        text: vista.datos ? vista.datos.resumen : ""
                        color: Tema.texto3
                        font.family: Tema.mono
                        font.pixelSize: 12
                    }
                }
                Text {
                    visible: !!vista.datos && vista.datos.lista.length === 0
                    x: 12
                    width: parent.width - 24
                    bottomPadding: 12
                    text: "Aún no hay revisiones. Se hacen solas al acabar cada partida tuya en la Grieta."
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
                Repeater {
                    model: vista.datos ? vista.datos.lista : []

                    Rectangle {
                        id: item

                        required property var modelData
                        readonly property bool activa: vista.elegida === modelData.id

                        width: lista.width
                        height: 56
                        radius: 2
                        color: activa ? Tema.panel2 : zonaItem.containsMouse ? Tema.hover : "transparent"

                        Rectangle {
                            visible: item.activa
                            width: 2
                            height: parent.height
                            color: Tema.acento
                        }
                        Text {
                            x: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: item.modelData.gana ? "V" : "D"
                            color: item.modelData.gana ? Tema.bien : Tema.mal
                            font.family: Tema.mono
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                        Retrato {
                            x: 38
                            anchors.verticalCenter: parent.verticalCenter
                            tam: 28
                            fuente: item.modelData.retrato
                        }
                        Column {
                            x: 76
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 76 - lpItem.width - 22

                            Row {
                                spacing: 6

                                Text {
                                    text: item.modelData.campeon
                                    color: Tema.texto
                                    font.family: Tema.sans
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    anchors.baseline: parent.children[0].baseline
                                    text: item.modelData.kda
                                    color: Tema.texto3
                                    font.family: Tema.mono
                                    font.pixelSize: 14
                                }
                            }
                            Text {
                                width: parent.width
                                text: item.modelData.linea2
                                color: Tema.texto3
                                elide: Text.ElideRight
                                font.family: Tema.sans
                                font.pixelSize: 12
                            }
                        }
                        Text {
                            id: lpItem

                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: item.modelData.lp.txt
                            color: Tema.tono(item.modelData.lp.tono)
                            font.family: Tema.mono
                            font.pixelSize: 12
                        }
                        MouseArea {
                            id: zonaItem

                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: vista.elegir(item.modelData.id)
                        }
                    }
                }
            }
        }
        DetalleRevision {
            width: vista.estrecha ? vista.anchoContenido : vista.anchoContenido - 304 - 24
            r: vista.revision
        }
    }
}

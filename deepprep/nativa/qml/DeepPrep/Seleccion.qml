pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// La pestaña Partida durante la selección de campeón: vistas.seleccion. Solo campeones y tu historial contra ellos.
Column {
    id: seleccion

    property var datos
    readonly property real anchoLateral: width > 1376 ? 368 : 320
    readonly property bool estrecha: width < 1080

    spacing: 32

    Heroe {
        width: seleccion.width
        retrato: seleccion.datos ? seleccion.datos.hero.retrato : ""
        cabecera: "Selección de campeón"
        titulo: seleccion.datos ? seleccion.datos.hero.titulo : ""
        sub: seleccion.datos ? seleccion.datos.hero.sub : ""

        DatoHeroe {
            visible: !!seleccion.datos && !!seleccion.datos.hero.racha
            primero: true
            rotulo: "Últimas con él"

            Racha {
                y: 4
                datos: seleccion.datos ? seleccion.datos.hero.racha : null
            }
        }
    }
    ElegirRol {
        datos: seleccion.datos ? seleccion.datos.elegir_rol : null
    }
    Grid {
        columns: seleccion.estrecha ? 1 : 2
        columnSpacing: 24
        rowSpacing: 24
        width: seleccion.width

        Column {
            id: principal

            width: seleccion.estrecha ? seleccion.width : seleccion.width - seleccion.anchoLateral - 24
            spacing: 24

            Caja {
                // Tu pool contra el rival de tu posición.
                id: pool

                readonly property var p: seleccion.datos ? seleccion.datos.pool : null

                visible: !!p
                width: principal.width
                titulo: p && p.titulo ? p.titulo : "Tu pool"
                sub: p && p.sub ? p.sub : ""

                Text {
                    visible: !!pool.p && !pool.p.filas
                    width: parent.width
                    text: pool.p && pool.p.vacio ? pool.p.vacio : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
                Item {
                    visible: !!pool.p && !!pool.p.filas
                    width: parent.width
                    height: 28

                    Repeater {
                        model: pool.p && pool.p.cabeza ? pool.p.cabeza : []

                        Etiqueta {
                            required property string modelData
                            required property int index

                            x: [0, 0.26, 0.62, 0.81][index] * parent.width
                            text: modelData
                        }
                    }
                }
                Repeater {
                    model: pool.p && pool.p.filas ? pool.p.filas : []

                    Item {
                        id: filaPool

                        required property var modelData

                        width: pool.anchoDentro
                        height: 45

                        Rectangle {
                            width: parent.width
                            height: 1
                            color: Tema.linea
                        }
                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10

                            Retrato {
                                anchors.verticalCenter: parent.verticalCenter
                                tam: 24
                                fuente: filaPool.modelData.retrato
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: filaPool.modelData.nombre
                                color: Tema.texto
                                font.family: Tema.sans
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                            }
                        }
                        Row {
                            x: 0.26 * parent.width
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10

                            Rico {
                                visible: !!filaPool.modelData.master.wr
                                anchors.verticalCenter: parent.verticalCenter
                                width: 36
                                text: filaPool.modelData.master.wr || ""
                                wrapMode: Text.NoWrap
                            }
                            BarraWr {
                                visible: !!filaPool.modelData.master.barra
                                anchors.verticalCenter: parent.verticalCenter
                                datos: filaPool.modelData.master.barra || null
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: filaPool.modelData.master.n !== undefined ? filaPool.modelData.master.n : filaPool.modelData.master.linea2
                                color: Tema.texto3
                                font.family: filaPool.modelData.master.n !== undefined ? Tema.mono : Tema.sans
                                font.pixelSize: filaPool.modelData.master.n !== undefined ? 14 : 12
                            }
                        }
                        Rico {
                            x: 0.62 * parent.width
                            anchors.verticalCenter: parent.verticalCenter
                            text: filaPool.modelData.yo
                            wrapMode: Text.NoWrap
                        }
                        Rico {
                            x: 0.81 * parent.width
                            anchors.verticalCenter: parent.verticalCenter
                            text: filaPool.modelData.vs
                            wrapMode: Text.NoWrap
                        }
                    }
                }
                Text {
                    visible: !!pool.p && !!pool.p.filas && pool.p.vacio !== ""
                    width: parent.width
                    text: pool.p && pool.p.filas ? pool.p.vacio : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
                Text {
                    visible: !!pool.p && !!pool.p.pie
                    width: parent.width
                    topPadding: 12
                    text: pool.p && pool.p.pie ? pool.p.pie : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
            Caja {
                id: vs

                width: principal.width
                titulo: "Contra lo que van eligiendo"
                sub: seleccion.datos ? seleccion.datos.vs.sub : ""

                FilasVs {
                    visible: !!seleccion.datos && !!seleccion.datos.vs.filas
                    width: parent.width
                    datos: seleccion.datos ? seleccion.datos.vs.filas : null
                }
                Text {
                    visible: !!seleccion.datos && seleccion.datos.vs.vacio !== ""
                    text: seleccion.datos ? seleccion.datos.vs.vacio : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                }
            }
        }
        Column {
            id: lateral

            width: seleccion.estrecha ? seleccion.width : seleccion.anchoLateral
            spacing: 16

            CajaDuelo {
                width: lateral.width
                datos: seleccion.datos ? seleccion.datos.duelo : null
            }
            Notas {
                width: lateral.width
                lista: seleccion.datos ? seleccion.datos.notas : []
            }
            Caja {
                width: lateral.width
                titulo: "Qué se ve aquí"

                Text {
                    width: parent.width
                    text: seleccion.datos ? seleccion.datos.que_se_ve : ""
                    color: Tema.texto2
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}

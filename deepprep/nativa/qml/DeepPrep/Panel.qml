pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// La pestaña Partida con una partida (pantalla de carga, en juego o ya terminada): vistas.panel.
Column {
    id: panel

    property var datos
    readonly property real anchoLateral: width > 1376 ? 368 : 320
    readonly property bool estrecha: width < 1080 // a una columna

    spacing: 32

    Heroe {
        width: panel.width
        retrato: panel.datos ? panel.datos.hero.retrato : ""
        cabecera: panel.datos ? panel.datos.hero.cabecera : ""
        titulo: panel.datos ? panel.datos.hero.titulo : ""
        rol: panel.datos ? panel.datos.hero.rol : ""
        sub: panel.datos ? panel.datos.hero.sub : ""

        DatoHeroe {
            visible: !!panel.datos && panel.datos.hero.bans.length > 0 && !panel.estrecha
            primero: true
            rotulo: "Baneos"

            Row {
                spacing: 4

                Repeater {
                    model: panel.datos ? panel.datos.hero.bans : []

                    Retrato {
                        id: ban

                        required property var modelData

                        tam: 24
                        fuente: modelData.retrato
                        opacity: 0.55 // apagado: un baneo no juega

                        Tip {
                            texto: ban.modelData.nombre
                        }
                    }
                }
            }
        }
        DatoHeroe {
            rotulo: panel.datos && panel.datos.hero.carga.cargando ? `Datos · ${panel.datos.hero.carga.ancho}%` : "Datos"
            primero: !panel.datos || panel.datos.hero.bans.length === 0 || panel.estrecha

            Progreso {
                visible: !!panel.datos && panel.datos.hero.carga.cargando
                y: 10
                valor: panel.datos ? panel.datos.hero.carga.ancho / 100 : 0
            }
            Row {
                visible: !!panel.datos && !panel.datos.hero.carga.cargando
                y: 4
                spacing: 8

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6
                    height: 6
                    radius: 3
                    color: Tema.bien
                }
                Text {
                    text: "Completos"
                    color: Tema.texto
                    font.family: Tema.sans
                    font.pixelSize: 13
                }
            }
        }
        DatoHeroe {
            rotulo: "Tiempo"

            Reloj {}
        }
    }
    ElegirRol {
        datos: panel.datos ? panel.datos.elegir_rol : null
    }
    Grid {
        // El cuerpo: equipos, jungla, líneas e historial a la izquierda; duelo, plan, datos y notas a la derecha.
        columns: panel.estrecha ? 1 : 2
        columnSpacing: 24
        rowSpacing: 24
        width: panel.width

        Column {
            id: principal

            width: panel.estrecha ? panel.width : panel.width - panel.anchoLateral - 24
            spacing: 24

            TablaEquipos {
                width: principal.width
                basico: !!panel.datos && panel.datos.basico
                aliado: panel.datos ? panel.datos.aliado : []
                rival: panel.datos ? panel.datos.rival : []
            }
            CajaJungla {
                // Tu rival de línea, si no juegas jungla (de jungla, tu rival directo es el jungla rival de abajo).
                visible: !!panel.datos && !!panel.datos.rival_linea
                width: principal.width
                datos: panel.datos ? panel.datos.rival_linea : null
            }
            CajaJungla {
                visible: !!panel.datos && !panel.datos.basico
                width: principal.width
                datos: panel.datos ? panel.datos.jungla : null
            }
            Grid {
                visible: !!panel.datos && !panel.datos.basico
                columns: principal.width > 760 ? 2 : 1
                columnSpacing: 24
                rowSpacing: 24
                width: principal.width

                CajaLineas {
                    width: principal.width > 760 ? (principal.width - 24) / 2 : principal.width
                    datos: panel.datos ? panel.datos.lineas : null
                }
                CajaHistorial {
                    width: principal.width > 760 ? (principal.width - 24) / 2 : principal.width
                    datos: panel.datos ? panel.datos.historial : null
                }
            }
        }
        Column {
            id: lateral

            width: panel.estrecha ? panel.width : panel.anchoLateral
            spacing: 16

            CajaDuelo {
                width: lateral.width
                datos: panel.datos ? panel.datos.duelo : null
            }
            Caja {
                visible: !!panel.datos && panel.datos.plan.length > 0
                width: lateral.width
                titulo: "Antes de empezar"

                Lista {
                    width: parent.width
                    marca: "numero"
                    elementos: panel.datos ? panel.datos.plan : []
                }
            }
            Caja {
                width: lateral.width
                titulo: "Datos destacados"

                Lista {
                    visible: !!panel.datos && panel.datos.avisos.length > 0
                    width: parent.width
                    elementos: panel.datos ? panel.datos.avisos : []
                }
                Text {
                    visible: !!panel.datos && panel.datos.avisos.length === 0
                    text: panel.datos ? panel.datos.sin_avisos : ""
                    color: Tema.texto3
                    font.family: Tema.sans
                    font.pixelSize: 14
                }
            }
            Notas {
                width: lateral.width
                lista: panel.datos ? panel.datos.notas : []
            }
            Caja {
                visible: !!panel.datos && !panel.datos.ajena
                width: lateral.width
                titulo: "Tus reglas"

                Lista {
                    width: parent.width
                    marca: "nada"
                    elementos: panel.datos ? panel.datos.reglas : []
                }
            }
            Caja {
                id: ajena

                visible: !!panel.datos && panel.datos.ajena
                width: lateral.width
                titulo: "Partida ajena"

                Text {
                    width: parent.width
                    text: "Estás viendo la partida de otro jugador desde su punto de vista."
                    color: Tema.texto2
                    font.family: Tema.sans
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                    bottomPadding: 12
                }
                Boton {
                    id: volver

                    texto: "Volver a mis partidas"
                    onPulsar: puente.llamar("volver", [], r => {
                        if (!r.ok)
                            volver.texto = r.error;
                    })
                }
            }
        }
    }
}

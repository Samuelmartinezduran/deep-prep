pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Pestaña Ajustes: el formulario (vistas.ajustes), guardarlo y cerrar la app. Se lee de la app al abrir la pestaña.
Item {
    id: ajustes

    property bool cargado: false
    property string error: ""
    property string aviso: ""
    property string tonoAviso: ""
    // El formulario: un campo por propiedad; las filas por campeón, como listas de {campeon, texto, estado}.
    property string rol: "JUNGLE"
    property var roles: []
    property var modos: [] // [{k, v, activo, nota}]
    property bool overlay
    property string atajo
    property int opacidad: 94
    property bool siempre
    property bool grabar
    property string codificador: "auto"
    property string maxGb: "0"
    property string cuentas
    property string reglas
    property var comparar: []
    property string compararCon
    property string perfil
    property string perfilEstado
    property var referencias: []
    property var notas: []
    property var campeones: []
    property string version

    function poner(a) {
        rol = a.rol;
        roles = a.roles;
        modos = a.modos;
        overlay = a.overlay;
        atajo = a.atajo;
        opacidad = a.opacidad;
        siempre = a.siempre;
        grabar = a.grabar;
        codificador = a.codificador;
        maxGb = a.max_gb;
        cuentas = a.cuentas;
        reglas = a.reglas;
        comparar = a.comparar;
        compararCon = a.comparar_con;
        perfil = a.perfil;
        perfilEstado = a.perfil_estado;
        referencias = a.referencias;
        notas = a.notas;
        campeones = a.campeones;
        version = a.version;
        cargado = true;
    }
    function cargar() {
        puente.llamar("ajustes", [], a => {
            if (!a || a.ok === false) {
                ajustes.error = (a && a.error ? a.error : "Sin respuesta") + ": no se han podido cargar los ajustes.";
                return;
            }
            ajustes.error = "";
            ajustes.poner(a);
        });
    }
    function guardar() {
        aviso = "Guardando…";
        tonoAviso = "";
        const f = {
            rol: rol,
            modos: modos.map(m => ({
                        k: m.k,
                        activo: m.activo
                    })),
            overlay: overlay,
            atajo: atajo,
            opacidad: opacidad,
            siempre: siempre,
            grabar: grabar,
            codificador: codificador,
            max_gb: maxGb,
            cuentas: cuentas,
            reglas: reglas,
            comparar_con: compararCon,
            perfil: perfil,
            referencias: referencias.map(x => ({
                        campeon: x.campeon,
                        texto: x.texto
                    })),
            notas: notas.map(x => ({
                        campeon: x.campeon,
                        texto: x.texto
                    }))
        };
        puente.llamar("guardarAjustes", [f], r => {
            ajustes.aviso = r.ok ? "Guardado." : r.error;
            ajustes.tonoAviso = r.ok ? "bien" : "mal";
            if (r.ok && r.ajustes)
                ajustes.poner(r.ajustes); // así se ve el estado de las referencias nuevas
        });
    }

    // Un modo encendido o apagado (la lista se cambia entera para que se entere quien la mira).
    function ponerModo(i, activo) {
        const lista = modos.slice();
        lista[i] = Object.assign({}, lista[i], {
            activo: activo
        });
        modos = lista;
    }

    Component.onCompleted: if (visible)
        cargar()
    onVisibleChanged: if (visible)
        cargar()

    component Grupo: Item {
        id: grupo

        property string nombre
        property string texto
        property bool primero: false // el primero, sin la línea de arriba
        default property alias campos: columnaCampos.data
        // Explicación a la izquierda y campos a la derecha si caben; si no, una debajo de la otra.
        readonly property bool aLado: width >= 820

        width: hoja.anchoContenido > 1040 ? 1040 : hoja.anchoContenido
        implicitHeight: (aLado ? Math.max(textoGrupo.implicitHeight, columnaCampos.implicitHeight) : textoGrupo.implicitHeight + 16 + columnaCampos.implicitHeight) + (primero ? 32 : 64)

        Rectangle {
            visible: !grupo.primero
            width: parent.width
            height: 1
            color: Tema.linea
        }
        Column {
            id: textoGrupo

            y: grupo.primero ? 0 : 32
            width: grupo.aLado ? 280 : parent.width
            spacing: 8

            Text {
                text: grupo.nombre
                color: Tema.texto
                font.family: Tema.sans
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: grupo.texto
                color: Tema.texto3
                font.family: Tema.sans
                font.pixelSize: 13
                wrapMode: Text.Wrap
                lineHeight: 1.15
            }
        }
        Column {
            id: columnaCampos

            x: grupo.aLado ? 280 + 48 : 0
            y: (grupo.primero ? 0 : 32) + (grupo.aLado ? 0 : textoGrupo.implicitHeight + 16)
            width: parent.width - x
            spacing: 20
        }
    }
    component Rotulo: Text {
        color: Tema.texto2
        font.family: Tema.sans
        font.pixelSize: 13
    }

    Hoja {
        id: hoja

        anchors.fill: parent
        anchors.bottomMargin: barraGuardar.height

        Text {
            visible: ajustes.error !== ""
            text: ajustes.error
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 14
        }
        Column {
            visible: ajustes.cargado
            width: hoja.anchoContenido

            Grupo {
                primero: true
                nombre: "Tu rol"
                texto: "El que juegas normalmente. En cada partida manda la posición que te toque en la selección y, si la cola no la da (a ciegas, Swiftplay), este. Para una partida concreta se cambia en la pestaña Partida."

                Selector {
                    mono: false
                    opciones: ajustes.roles
                    actual: ajustes.rol
                    onElegir: id => ajustes.rol = id
                }
            }
            Grupo {
                nombre: "Modos de juego"
                texto: "En los modos apagados no salen el panel ni el overlay, y no se graba. Fuera de la Grieta no hay posiciones: el panel enseña lo básico de cada jugador, su rango y su maestría con el campeón."

                Repeater {
                    model: ajustes.modos

                    Column {
                        id: modo

                        required property var modelData
                        required property int index

                        spacing: 4

                        Interruptor {
                            texto: modo.modelData.v
                            activo: modo.modelData.activo
                            onCambiado: a => ajustes.ponerModo(modo.index, a)
                        }
                        Text {
                            visible: modo.modelData.nota !== ""
                            leftPadding: 44
                            text: modo.modelData.nota
                            color: Tema.texto3
                            font.family: Tema.sans
                            font.pixelSize: 12
                        }
                    }
                }
            }
            Grupo {
                nombre: "Panel encima del juego"
                texto: "Sale solo en la pantalla de carga y, ya jugando, mientras mantienes el atajo. Durante la partida solo enseña datos de antes de empezar, como permite Riot. El juego tiene que estar en ventana sin bordes."

                Interruptor {
                    texto: "Enseñarlo en la pantalla de carga y al mantener el atajo"
                    activo: ajustes.overlay
                    onCambiado: a => ajustes.overlay = a
                }
                Column {
                    spacing: 8

                    Rotulo {
                        text: "Atajo (mantener)"
                    }
                    Campo {
                        width: Math.min(520, parent.parent.width)
                        texto: ajustes.atajo
                        pista: "ctrl+tab"
                        onEditado: t => ajustes.atajo = t
                    }
                }
                Column {
                    spacing: 8

                    Rotulo {
                        text: "Opacidad"
                    }
                    Deslizador {
                        width: Math.min(520, parent.parent.width)
                        valor: ajustes.opacidad
                        onCambiado: v => ajustes.opacidad = v
                    }
                }
            }
            Grupo {
                nombre: "Siempre en marcha"
                texto: "Así el recolector sigue llenando tus duelos de Master+ y el overlay está listo al jugar. Gasta muy poco: en torno al 2% de un núcleo y 130 MB de memoria."

                Interruptor {
                    texto: "Arrancar con Windows y seguir con el LoL cerrado"
                    activo: ajustes.siempre
                    onCambiado: a => ajustes.siempre = a
                }
                Boton {
                    texto: "Cerrar Deep Prep del todo"
                    onPulsar: puente.llamar("salir", [], r => {
                        ajustes.aviso = r.ok ? "Cerrando…" : r.error;
                        ajustes.tonoAviso = r.ok ? "" : "mal";
                    })
                }
            }
            Grupo {
                nombre: "Grabación"
                texto: "Cada partida en la Grieta se graba en Vídeos\\LoL-coach y la revisión apunta el minuto de cada muerte en el vídeo."

                Interruptor {
                    texto: "Grabar cada partida en la Grieta"
                    activo: ajustes.grabar
                    onCambiado: a => ajustes.grabar = a
                }
                Column {
                    spacing: 8

                    Rotulo {
                        text: "Grabar con"
                    }
                    Selector {
                        mono: false
                        opciones: [
                            {
                                id: "auto",
                                txt: "La gráfica si se puede (gasta menos procesador)"
                            },
                            {
                                id: "cpu",
                                txt: "El procesador"
                            }
                        ]
                        actual: ajustes.codificador
                        onElegir: id => ajustes.codificador = id
                    }
                }
                Column {
                    spacing: 8

                    Rotulo {
                        text: "Espacio máximo, en GB"
                    }
                    Campo {
                        width: 120
                        texto: ajustes.maxGb
                        entrada.inputMethodHints: Qt.ImhDigitsOnly
                        onEditado: t => ajustes.maxGb = t
                    }
                    Text {
                        text: "0 = sin límite; al pasarlo se borran las más viejas."
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 12
                    }
                }
            }
            Grupo {
                nombre: "Tus cuentas"
                texto: "Una por línea, como Nombre#TAG. Las partidas de todas cuentan para tu historial y tus revisiones."

                AreaTexto {
                    width: parent.width
                    lineas: 3
                    texto: ajustes.cuentas
                    onEditado: t => ajustes.cuentas = t
                }
            }
            Grupo {
                nombre: "Tus reglas"
                texto: "Salen en cada partida, una por línea. Escríbelas como hábitos que puedas comprobar."

                AreaTexto {
                    width: parent.width
                    lineas: 4
                    texto: ajustes.reglas
                    onEditado: t => ajustes.reglas = t
                }
            }
            Grupo {
                nombre: "Con quién compararte"
                texto: "Se usa en tu duelo y en cada revisión. Con un perfil de base te comparas con ese jugador en todo: con tu campeón si lo juega y, si no, en tu posición. Un jugador por campeón manda cuando juegas ese campeón. Sus partidas se recogen solas."

                Column {
                    width: parent.width
                    spacing: 8

                    Rotulo {
                        text: "Referencia de base"
                    }
                    Opciones {
                        width: Math.min(520, parent.width)
                        lista: ajustes.comparar
                        actual: ajustes.compararCon
                        onElegir: k => ajustes.compararCon = k
                    }
                }
                Column {
                    visible: ajustes.compararCon === "perfil"
                    width: parent.width
                    spacing: 8

                    Rotulo {
                        text: "Tu perfil de referencia (Nombre#TAG, de cualquier servidor)"
                    }
                    Campo {
                        width: Math.min(520, parent.width)
                        texto: ajustes.perfil
                        pista: "p. ej. un jugador de Challenger al que quieras parecerte"
                        onEditado: t => ajustes.perfil = t
                    }
                    Text {
                        visible: ajustes.perfilEstado !== ""
                        text: ajustes.perfilEstado
                        color: Tema.texto3
                        font.family: Tema.sans
                        font.pixelSize: 12
                    }
                }
                Column {
                    width: parent.width
                    spacing: 8

                    Etiqueta {
                        text: "Por campeón"
                    }
                    Repeater {
                        model: ajustes.referencias

                        FilaCampeon {
                            required property var modelData
                            required property int index

                            width: parent.width
                            campeones: ajustes.campeones
                            campeon: modelData.campeon
                            texto: modelData.texto
                            estado: modelData.estado
                            pistaTexto: "Jugador (Nombre#TAG), de cualquier servidor"
                            onCambiado: (c, t) => {
                                ajustes.referencias[index].campeon = c;
                                ajustes.referencias[index].texto = t;
                            }
                            onQuitar: ajustes.referencias = ajustes.referencias.filter((_, i) => i !== index)
                        }
                    }
                    Boton {
                        texto: "Añadir jugador de referencia"
                        onPulsar: ajustes.referencias = ajustes.referencias.concat([
                            {
                                campeon: "",
                                texto: "",
                                estado: ""
                            }
                        ])
                    }
                }
            }
            Grupo {
                nombre: "Notas por campeón"
                texto: "Salen cuando ese campeón está en tu partida, en el panel y encima del juego."

                Repeater {
                    model: ajustes.notas

                    FilaCampeon {
                        required property var modelData
                        required property int index

                        width: parent.width
                        campeones: ajustes.campeones
                        campeon: modelData.campeon
                        texto: modelData.texto
                        pistaTexto: "Tu nota (sale cuando está en la partida)"
                        onCambiado: (c, t) => {
                            ajustes.notas[index].campeon = c;
                            ajustes.notas[index].texto = t;
                        }
                        onQuitar: ajustes.notas = ajustes.notas.filter((_, i) => i !== index)
                    }
                }
                Boton {
                    texto: "Añadir nota"
                    onPulsar: ajustes.notas = ajustes.notas.concat([
                        {
                            campeon: "",
                            texto: "",
                            estado: ""
                        }
                    ])
                }
            }
        }
    }
    Rectangle {
        // Guardar, siempre a la vista.
        id: barraGuardar

        anchors.bottom: parent.bottom
        width: parent.width
        height: 72
        visible: ajustes.cargado
        color: Tema.fondo

        Rectangle {
            width: parent.width
            height: 1
            color: Tema.linea2
        }
        Row {
            x: Math.max(32, (parent.width - 1680) / 2)
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            Boton {
                primario: true
                texto: "Guardar cambios"
                onPulsar: ajustes.guardar()
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: ajustes.aviso
                color: Tema.tono(ajustes.tonoAviso) === Tema.texto3 ? Tema.texto3 : Tema.tono(ajustes.tonoAviso)
                font.family: Tema.sans
                font.pixelSize: 13
            }
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: Math.max(32, (parent.width - 1680) / 2)
            anchors.verticalCenter: parent.verticalCenter
            text: ajustes.version
            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 12
        }
    }
}

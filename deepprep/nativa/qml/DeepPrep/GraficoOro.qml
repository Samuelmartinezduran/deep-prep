pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import DeepPrep

// «La partida»: la diferencia de oro entre los equipos minuto a minuto. Por encima del 0 va por delante tu equipo
// (azul); por debajo, el rival (rojo). Encima, los objetivos; debajo, tus muertes. Al pasar el ratón, ese minuto.
// Los datos vienen en minutos y oro (oro.py); aquí solo se pasan a píxeles.
Item {
    id: g

    property var datos
    readonly property int margenIzq: 96
    readonly property int margenDer: 56
    readonly property int altoCarril: 32
    readonly property int altoGrafico: 176
    readonly property int altoEje: 24
    readonly property int aire: 12 // entre el borde del gráfico y el máximo de la escala
    readonly property real x0: margenIzq
    readonly property real ancho: Math.max(1, width - margenIzq - margenDer)
    readonly property real y0: altoCarril
    readonly property real yMuertes: y0 + altoGrafico
    readonly property real yEje: yMuertes + altoCarril

    // Lo que hay bajo el ratón: el fotograma más cercano y lo que pasó en ese minuto.
    // (minutoFijo, para las capturas: como si el ratón estuviera en ese minuto.)
    readonly property int indice: {
        if (!datos || (minutoFijo < 0 && !raton.containsMouse))
            return -1;
        const t = minutoFijo >= 0 ? minutoFijo : (raton.x + raton.mouseX - x0) / ancho * datos.fin;
        let mejor = 0;
        for (let i = 1; i < datos.puntos.length; i++)
            if (Math.abs(datos.puntos[i][0] - t) < Math.abs(datos.puntos[mejor][0] - t))
                mejor = i;
        return mejor;
    }
    readonly property var punto: indice >= 0 ? datos.puntos[indice] : null
    readonly property var eventos: {
        if (!punto)
            return [];
        const r = [];
        for (const o of datos.objetivos)
            if (Math.abs(o.t - punto[0]) <= 0.5)
                r.push({
                    "marca": o.tuyo ? "aliado" : "rival",
                    "txt": `${o.nombre} · ${o.txt}`
                });
        for (const m of datos.muertes)
            if (Math.abs(m.t - punto[0]) <= 0.5)
                r.push({
                    "marca": "muerte",
                    "txt": `Mueres ante ${m.asesino} · ${m.txt}` + (m.perdido ? ` (${m.perdido})` : "")
                });
        return r;
    }

    function xDe(t) {
        return x0 + ancho * t / datos.fin;
    }
    function yDe(v) {
        return y0 + aire + (altoGrafico - 2 * aire) * (datos.arriba - v) / (datos.arriba - datos.abajo);
    }
    function aPixeles(tramos) {
        return tramos.map(tr => tr.map(p => Qt.point(xDe(p[0]), yDe(p[1]))));
    }

    implicitHeight: yEje + altoEje + 12 + leyenda.height

    // Los carriles, con sus rótulos.
    Repeater {
        model: [0, g.y0, g.yMuertes]

        Rectangle {
            required property real modelData

            y: modelData
            width: g.width
            height: 1
            color: Tema.linea
        }
    }
    Rectangle {
        y: g.yEje
        width: g.width
        height: 1
        color: Tema.linea2
    }
    Etiqueta {
        y: (g.altoCarril - height) / 2
        text: "Objetivos"
    }
    Etiqueta {
        y: g.y0 + g.aire - 2
        text: "Oro"
    }
    Etiqueta {
        y: g.yMuertes + (g.altoCarril - height) / 2
        text: "Tus muertes"
    }
    Etiqueta {
        y: g.yEje + 6
        text: "Min"
    }

    // Cada 5 minutos, una línea por todos los carriles y su minuto abajo.
    Repeater {
        model: g.datos ? g.datos.marcas_x : []

        Item {
            id: marcaX

            required property int modelData

            x: g.xDe(modelData)

            Rectangle {
                width: 1
                height: g.yEje + g.altoEje
                color: Tema.linea
            }
            Text {
                x: 4
                y: g.yEje + 5
                text: marcaX.modelData
                color: Tema.texto3
                font.family: Tema.mono
                font.pixelSize: 11
            }
        }
    }

    // La escala del oro: líneas finas y el 0 más marcado.
    Repeater {
        model: g.datos ? g.datos.marcas_y : []

        Item {
            id: marcaY

            required property var modelData

            Rectangle {
                x: g.x0
                y: g.yDe(marcaY.modelData.v)
                width: g.ancho
                height: 1
                color: marcaY.modelData.v === 0 ? Tema.linea3 : Tema.linea
            }
            Text {
                x: g.x0 - 10 - width
                y: g.yDe(marcaY.modelData.v) - height / 2
                text: marcaY.modelData.txt
                color: Tema.texto3
                font.family: Tema.mono
                font.pixelSize: 11
            }
        }
    }

    // La curva: rellena hasta el 0 y con su línea, de un color por encima y de otro por debajo.
    Shape {
        anchors.fill: parent
        visible: !!g.datos
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: "transparent"
            fillColor: Tema.alfa(Tema.aliado, 0.16)
            PathMultiline {
                paths: g.datos ? g.aPixeles(g.datos.areas_arriba) : []
            }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: Tema.alfa(Tema.rival, 0.16)
            PathMultiline {
                paths: g.datos ? g.aPixeles(g.datos.areas_abajo) : []
            }
        }
        ShapePath {
            strokeColor: Tema.aliado
            strokeWidth: 2
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            PathMultiline {
                paths: g.datos ? g.aPixeles(g.datos.tramos_arriba) : []
            }
        }
        ShapePath {
            strokeColor: Tema.rival
            strokeWidth: 2
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            PathMultiline {
                paths: g.datos ? g.aPixeles(g.datos.tramos_abajo) : []
            }
        }
    }
    Text {
        // Cómo acabó: la diferencia al final, junto al último punto.
        visible: !!g.datos
        x: g.datos ? g.xDe(g.datos.fin) + 8 : 0
        y: g.datos ? g.yDe(g.datos.final.v) - height / 2 : 0
        text: g.datos ? g.datos.final.txt : ""
        color: g.datos && g.datos.final.v < 0 ? Tema.rival : Tema.aliado
        font.family: Tema.mono
        font.pixelSize: 12
        font.weight: Font.Medium
    }

    // Los objetivos (del color del equipo que lo hizo) y tus muertes (la raya roja: costó un objetivo).
    Repeater {
        model: g.datos ? g.datos.objetivos : []

        Rectangle {
            id: objetivo

            required property var modelData

            x: g.xDe(modelData.t) - 8
            y: (g.altoCarril - 16) / 2
            width: 16
            height: 16
            radius: 8
            color: Tema.panel

            Rectangle {
                anchors.centerIn: parent
                width: 12
                height: 12
                radius: 6
                color: objetivo.modelData.tuyo ? Tema.aliado : Tema.rival
            }
        }
    }
    Repeater {
        model: g.datos ? g.datos.muertes : []

        Item {
            id: marcaMuerte

            required property var modelData

            x: g.xDe(modelData.t) - 7
            y: g.yMuertes + (g.altoCarril - 14) / 2
            width: 14
            height: 14

            Icono {
                anchors.centerIn: parent
                nombre: "muerte"
                tam: 10
                grosor: 3.2
                color: Tema.texto
            }
            Rectangle {
                visible: marcaMuerte.modelData.cara
                anchors.bottom: parent.bottom
                width: parent.width
                height: 2
                color: Tema.mal
            }
        }
    }

    // El minuto bajo el ratón: la guía, su punto en la curva y el detalle.
    MouseArea {
        id: raton

        x: g.x0 - 8
        width: g.ancho + 16
        height: g.yEje
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
    Rectangle {
        visible: !!g.punto
        x: g.punto ? g.xDe(g.punto[0]) : 0
        width: 1
        height: g.yEje
        color: Tema.linea3
    }
    Rectangle {
        visible: !!g.punto
        x: g.punto ? g.xDe(g.punto[0]) - 5 : 0
        y: g.punto ? g.yDe(g.punto[1]) - 5 : 0
        width: 10
        height: 10
        radius: 5
        color: g.punto && g.punto[1] < 0 ? Tema.rival : Tema.aliado
        border.width: 2
        border.color: Tema.panel
    }
    Rectangle {
        id: bocadillo

        readonly property real xGuia: g.punto ? g.xDe(g.punto[0]) : 0

        visible: !!g.punto
        z: 10
        x: xGuia + 14 + width > g.width ? xGuia - 14 - width : xGuia + 14
        y: g.y0 + 8
        width: Math.max(180, cuerpo.implicitWidth + 24)
        height: cuerpo.implicitHeight + 16
        radius: Tema.radio
        color: Tema.panel2
        border.color: Tema.linea2

        Column {
            id: cuerpo

            x: 12
            y: 8
            spacing: 4

            Row {
                spacing: 10

                Text {
                    text: !g.punto ? "" : g.indice === g.datos.puntos.length - 1 ? "Final" : `Min ${Math.round(g.punto[0])}`
                    color: Tema.texto
                    font.family: Tema.mono
                    font.pixelSize: 12
                    font.weight: Font.Medium
                }
                Text {
                    text: !g.punto ? "" : g.punto[1] > 0 ? `Tu equipo ${g.punto[2]}` : g.punto[1] < 0 ? `El rival ${g.punto[2].replace("−", "+")}` : "Igualados"
                    color: !g.punto || g.punto[1] === 0 ? Tema.texto2 : g.punto[1] > 0 ? Tema.aliado : Tema.rival
                    font.family: Tema.mono
                    font.pixelSize: 12
                }
            }
            Repeater {
                model: g.eventos

                Row {
                    id: evento

                    required property var modelData

                    spacing: 8

                    Item {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10
                        height: 10

                        Rectangle {
                            visible: evento.modelData.marca !== "muerte"
                            anchors.centerIn: parent
                            width: 8
                            height: 8
                            radius: 4
                            color: evento.modelData.marca === "aliado" ? Tema.aliado : Tema.rival
                        }
                        Icono {
                            visible: evento.modelData.marca === "muerte"
                            anchors.centerIn: parent
                            nombre: "muerte"
                            tam: 8
                            grosor: 3.2
                            color: Tema.texto
                        }
                    }
                    Text {
                        text: evento.modelData.txt
                        color: Tema.texto2
                        font.family: Tema.sans
                        font.pixelSize: 13
                    }
                }
            }
        }
    }

    Flow {
        id: leyenda

        x: g.margenIzq
        y: g.yEje + g.altoEje + 12
        width: g.width - g.margenIzq
        spacing: 20

        Marca {
            texto: "Va por delante tu equipo"
            Rectangle {
                anchors.fill: parent
                radius: 2
                color: Tema.aliado
            }
        }
        Marca {
            texto: "Va por delante el rival"
            Rectangle {
                anchors.fill: parent
                radius: 2
                color: Tema.rival
            }
        }
        Marca {
            texto: "Objetivo de tu equipo"
            Rectangle {
                anchors.fill: parent
                radius: 5
                color: Tema.aliado
            }
        }
        Marca {
            texto: "Objetivo rival"
            Rectangle {
                anchors.fill: parent
                radius: 5
                color: Tema.rival
            }
        }
        Marca {
            texto: "Tu muerte"
            Icono {
                anchors.centerIn: parent
                nombre: "muerte"
                tam: 10
                grosor: 3.2
                color: Tema.texto
            }
        }
        Marca {
            texto: "Muerte que costó un objetivo"
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                height: 2
                color: Tema.mal
            }
        }
    }

    component Marca: Row {
        property alias texto: etiqueta.text
        default property alias simbolo: hueco.data

        spacing: 8

        Item {
            id: hueco

            anchors.verticalCenter: parent.verticalCenter
            width: 10
            height: 10
        }
        Text {
            id: etiqueta

            color: Tema.texto3
            font.family: Tema.sans
            font.pixelSize: 12
        }
    }
}

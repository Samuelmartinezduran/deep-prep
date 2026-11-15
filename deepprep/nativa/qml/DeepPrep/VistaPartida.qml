import QtQuick
import DeepPrep

// La pestaña Partida: el panel, la selección de campeón o la espera, según el estado (vistas.partida).
Hoja {
    id: vista

    readonly property var p: puente.partida
    readonly property string que: p && p.vista ? p.vista : "espera"

    Panel {
        visible: vista.que === "panel"
        width: vista.anchoContenido
        datos: vista.que === "panel" ? vista.p.datos : null
    }
    Seleccion {
        visible: vista.que === "seleccion"
        width: vista.anchoContenido
        datos: vista.que === "seleccion" ? vista.p.datos : null
    }
    Espera {
        visible: vista.que === "espera"
        width: vista.anchoContenido
        datos: vista.que === "espera" && vista.p ? vista.p.datos : null
    }
}

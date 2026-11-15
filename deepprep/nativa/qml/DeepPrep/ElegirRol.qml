pragma ComponentBehavior: Bound
import QtQuick
import DeepPrep

// Tu posición en esta partida (vistas.elegir_rol) y por qué es esa: la que te ha tocado, tu rol principal o la que
// elijas aquí si juegas otra. Sale en la selección de campeón y en el panel de tu partida.
Row {
    id: rolHoy

    property var datos
    property string error: ""

    visible: !!datos
    spacing: 12

    Etiqueta {
        anchors.verticalCenter: parent.verticalCenter
        text: "Tu rol"
    }
    Selector {
        anchors.verticalCenter: parent.verticalCenter
        mono: false
        opciones: rolHoy.datos ? rolHoy.datos.opciones : []
        actual: rolHoy.datos ? rolHoy.datos.actual : ""
        onElegir: id => puente.llamar("rol", [id], r => {
                rolHoy.error = r && r.ok ? "" : (r && r.error ? r.error : "No se ha podido cambiar.");
            })
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: rolHoy.error !== "" ? rolHoy.error : (rolHoy.datos ? rolHoy.datos.motivo : "")
        color: rolHoy.error !== "" ? Tema.mal : Tema.texto3
        font.family: Tema.sans
        font.pixelSize: 12
    }
}

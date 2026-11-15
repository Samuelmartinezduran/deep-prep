import QtQuick
import DeepPrep

// El reloj de la partida: cuenta desde que empezó (puente.inicioPartida, en ms); sin partida, una raya.
Text {
    id: reloj

    property bool raya: true
    property real ahora: Date.now()

    text: {
        const inicio = puente.inicioPartida;
        if (!inicio)
            return raya ? "—" : "";
        const s = Math.max(0, Math.floor((ahora - inicio) / 1000));
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }
    color: Tema.texto
    font.family: Tema.mono
    font.pixelSize: 22
    font.weight: Font.Medium
    font.letterSpacing: -0.44

    Timer {
        interval: 1000
        repeat: true
        running: puente.inicioPartida > 0
        onTriggered: reloj.ahora = Date.now()
    }
}

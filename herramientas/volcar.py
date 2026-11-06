"""Vuelca en texto el estado que sirve la app (para depurar sin abrir el panel)."""
import json
import urllib.request

e = json.load(urllib.request.urlopen("http://127.0.0.1:5151/api/estado"))
p = e.pop("panel")
print(e)
if p:
    print(p["cola"], p["progreso"], "| plan:", p["plan"])
    for lado in ("aliado", "rival"):
        for f in p["equipos"][lado]:
            print(
                lado[:3], f["rol_txt"].ljust(8), f["campeon"][:12].ljust(12), f["nombre"][:14].ljust(14),
                ((f["liga"] or {}).get("txt") or "...").ljust(22), "muestra", f["muestra"]["v"], "/", f["muestra"]["n"],
                "| campeón", f["camp"]["v"], "/", f["camp"]["n"], "| maestría", f["maestria"],
                [t["t"] for t in f["etiquetas"]], "(yo)" if f["soy_yo"] else "",
            )
    j = p["jungla"]
    if j:
        print("JUNGLA RIVAL:", j["campeon"], j["nombre"], "partidas", j["n"], "con campeón", j["n_campeon"], "líneas", j["n_lineas"])
        for t in j["tarjetas"]:
            print("  ", t["tono"].ljust(6), t["titulo"], "→", t["valor"], "|", t["detalle"])
    for l in p["lineas"]:
        print("LÍNEA", l["linea"], l["veredicto"], round(l["debilidad"], 2), round(l["diferencia"], 2), "| rival:", l["rival"], "| aliado:", l["aliado"])
    print("GANK:", p["gank"])
    h = p["historial"]
    if h:
        print("HISTORIAL:", h["alcance"], h["n"], h["mi_campeon"], h["campeon"], "| duelo directo:", h["vs_directo"])
        for f in h["vs"]:
            print("   vs", f["nombre"], f["v"], "/", f["n"], "| con mi campeón", f["v_mio"], "/", f["n_mio"])
        print("   conocidos:", h["conocidos"])
    for a in p["avisos"]:
        print("AVISO", a["tono"], a["texto"])

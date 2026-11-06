"""Empaqueta la app y publica una versión nueva en GitHub (los amigos la reciben sola).

Uso: py herramientas/publicar.py 1.0.1 "Qué cambia"   (sin versión: solo empaqueta, para probar)

1. Pasa las pruebas (si alguna falla, no publica).
2. Pone la versión en porofesor/__init__.py y empaqueta con PyInstaller + ffmpeg.
3. Comprime en empaquetado/Porofesor-X.Y.Z.zip con su huella (.sha256).
4. Crea la versión en el repositorio público de descargas y sube los dos archivos.
La clave de GitHub sale del administrador de credenciales de git; no se guarda en ningún sitio.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMP = RAIZ / "empaquetado"
DIST = EMP / "dist" / "Porofesor"
FFMPEG_ZIP = EMP / "descargas" / "ffmpeg-essentials.zip"
REPO = "Samuelmartinezduran/porofesor-descargas"


def paso(texto):
    print(f"\n== {texto}", flush=True)


def poner_version(v):
    p = RAIZ / "porofesor" / "__init__.py"
    t = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', t), encoding="utf-8")


def leer_version():
    return re.search(r'__version__ = "([^"]+)"', (RAIZ / "porofesor" / "__init__.py").read_text(encoding="utf-8")).group(1)


def empaquetar():
    paso("PyInstaller")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Porofesor",
                    "--icon", str(RAIZ / "porofesor" / "web" / "icono.ico"),
                    "--add-data", f"{RAIZ / 'porofesor' / 'web'};porofesor/web",
                    "--collect-all", "webview", "--collect-all", "clr_loader", "--collect-all", "pythonnet",
                    "--distpath", str(EMP / "dist"), "--workpath", str(EMP / "build"), "--specpath", str(EMP),
                    str(EMP / "entrada.py")], check=True, cwd=RAIZ)
    paso("ffmpeg")
    destino = DIST / "ffmpeg"
    destino.mkdir(exist_ok=True)
    with zipfile.ZipFile(FFMPEG_ZIP) as z:
        for nombre in z.namelist():
            if nombre.endswith("bin/ffmpeg.exe") or nombre.endswith("/LICENSE"):
                (destino / Path(nombre).name).write_bytes(z.read(nombre))
    shutil.copy(EMP / "LEEME.md", DIST / "LEEME.txt")


def comprimir(v):
    paso("zip")
    zip_ruta = EMP / f"Porofesor-{v}.zip"
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in DIST.rglob("*"):
            if f.is_file():
                z.write(f, Path("Porofesor") / f.relative_to(DIST))
    huella = hashlib.sha256(zip_ruta.read_bytes()).hexdigest()
    (EMP / f"{zip_ruta.name}.sha256").write_text(f"{huella}  {zip_ruta.name}\n", encoding="utf-8")
    print(f"{zip_ruta.name}: {zip_ruta.stat().st_size / 1e6:.0f} MB, sha256 {huella}")
    return zip_ruta


def token():
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n", capture_output=True, text=True, check=True)
    return next(l.split("=", 1)[1] for l in r.stdout.splitlines() if l.startswith("password="))


def github(metodo, url, datos=None, tipo="application/json", tok=None):
    cuerpo = datos if isinstance(datos, bytes) else (json.dumps(datos).encode() if datos is not None else None)
    pet = urllib.request.Request(url, data=cuerpo, method=metodo, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", "Content-Type": tipo, "User-Agent": "porofesor"})
    with urllib.request.urlopen(pet, timeout=600) as r:
        return json.loads(r.read() or b"null")


def publicar(v, notas, zip_ruta):
    paso("GitHub")
    tok = token()
    rel = github("POST", f"https://api.github.com/repos/{REPO}/releases",
                 {"tag_name": f"v{v}", "name": f"Porofesor {v}", "body": notas, "make_latest": "true"}, tok=tok)
    subida = rel["upload_url"].split("{")[0]
    for f, tipo in ((zip_ruta, "application/zip"), (Path(f"{zip_ruta}.sha256"), "text/plain")):
        github("POST", f"{subida}?name={f.name}", f.read_bytes(), tipo, tok=tok)
        print("subido", f.name)
    print(rel["html_url"])


def main():
    args = [a for a in sys.argv[1:]]
    v = args[0] if args else None
    paso("Pruebas")
    if subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=RAIZ).returncode:
        sys.exit("Fallan pruebas: no se publica")
    if v:
        poner_version(v)
    empaquetar()
    zip_ruta = comprimir(v or leer_version())
    if v:
        publicar(v, args[1] if len(args) > 1 else f"Porofesor {v}", zip_ruta)


if __name__ == "__main__":
    main()

"""Empaqueta la app y publica una versión nueva en GitHub (los amigos la reciben sola).

Uso: py herramientas/publicar.py 2.0.1 "Qué cambia" [--puente]   (sin versión: solo empaqueta, para probar)

1. Pasa las pruebas (si alguna falla, no publica).
2. Pone la versión en deepprep/__init__.py y empaqueta con PyInstaller + ffmpeg.
3. Comprime en empaquetado/DeepPrep-X.Y.Z.zip con su huella (.sha256).
4. Crea la versión en el repositorio público de Deep Prep (código y descargas) y sube los dos archivos.
5. Con --puente, publica también la misma versión en el repositorio de descargas de Porofesor, del que se
   actualizan las 1.0.x, con el zip puente (empaquetado/puente/, ver comprimir): así les llega sola.
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
DIST = EMP / "dist" / "DeepPrep"
FFMPEG_ZIP = EMP / "descargas" / "ffmpeg-essentials.zip"
REPO = "Samuelmartinezduran/deep-prep"
# Donde miran si hay versión nueva Porofesor 1.0.0, 1.0.1 y 1.0.2 (lo llevan escrito y no se puede cambiar).
REPO_PUENTE = "Samuelmartinezduran/porofesor-descargas"


def paso(texto):
    print(f"\n== {texto}", flush=True)


def poner_version(v):
    p = RAIZ / "deepprep" / "__init__.py"
    t = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', t), encoding="utf-8")


def leer_version():
    return re.search(r'__version__ = "([^"]+)"', (RAIZ / "deepprep" / "__init__.py").read_text(encoding="utf-8")).group(1)


def empaquetar():
    paso("PyInstaller")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            "DeepPrep",
            "--icon",
            str(RAIZ / "deepprep" / "web" / "icono.ico"),
            "--add-data",
            f"{RAIZ / 'deepprep' / 'web'};deepprep/web",
            # Los datos de ejemplo de la demo (DeepPrep.exe --demo), junto a deepprep/demo como en el código.
            "--add-data",
            f"{RAIZ / 'deepprep' / 'demo' / '*.json'};deepprep/demo",
            "--collect-all",
            "webview",
            "--collect-all",
            "clr_loader",
            "--collect-all",
            "pythonnet",
            "--distpath",
            str(EMP / "dist"),
            "--workpath",
            str(EMP / "build"),
            "--specpath",
            str(EMP),
            str(EMP / "entrada.py"),
        ],
        check=True,
        cwd=RAIZ,
    )
    paso("ffmpeg")
    destino = DIST / "ffmpeg"
    destino.mkdir(exist_ok=True)
    with zipfile.ZipFile(FFMPEG_ZIP) as z:
        for nombre in z.namelist():
            if nombre.endswith(("bin/ffmpeg.exe", "/LICENSE")):
                (destino / Path(nombre).name).write_bytes(z.read(nombre))
    shutil.copy(EMP / "LEEME.md", DIST / "LEEME.txt")


def comprimir(v, puente=False, dist=DIST, carpeta=None):
    """El zip de la versión y su huella. Con puente=True, el de porofesor-descargas (en empaquetado/puente/).

    El zip puente lleva además una copia byte a byte de DeepPrep.exe llamada Porofesor.exe. El actualizador de
    las 1.0.x busca en el zip un archivo que se llame exactamente así y lo lanza con --actualizar; sin él, la
    descarga falla («no trae Porofesor.exe») y se quedan para siempre en la 1.0.x. La copia arranca igual que el
    original porque el empaquetado es de una carpeta (onedir): el .exe busca _internal al lado de donde está, no
    por su nombre. La 2.0.0 no instala esa copia (actualizador.EXE_VIEJO).
    """
    paso("zip puente" if puente else "zip")
    carpeta = carpeta or (EMP / "puente" if puente else EMP)
    carpeta.mkdir(parents=True, exist_ok=True)
    zip_ruta = carpeta / f"DeepPrep-{v}.zip"
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in dist.rglob("*"):
            if f.is_file():
                z.write(f, Path("DeepPrep") / f.relative_to(dist))
        if puente:
            z.write(dist / "DeepPrep.exe", Path("DeepPrep") / "Porofesor.exe")
    huella = hashlib.sha256(zip_ruta.read_bytes()).hexdigest()
    (carpeta / f"{zip_ruta.name}.sha256").write_text(f"{huella}  {zip_ruta.name}\n", encoding="utf-8")
    print(f"{zip_ruta.name}: {zip_ruta.stat().st_size / 1e6:.0f} MB, sha256 {huella}")
    return zip_ruta


def token():
    r = subprocess.run(
        ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n", capture_output=True, text=True, check=True
    )
    return next(l.split("=", 1)[1] for l in r.stdout.splitlines() if l.startswith("password="))


def github(metodo, url, datos=None, tipo="application/json", tok=None):
    cuerpo = datos if isinstance(datos, bytes) else (json.dumps(datos).encode() if datos is not None else None)
    pet = urllib.request.Request(
        url,
        data=cuerpo,
        method=metodo,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "Content-Type": tipo,
            "User-Agent": "deep-prep",
        },
    )
    with urllib.request.urlopen(pet, timeout=600) as r:
        return json.loads(r.read() or b"null")


def publicar(v, notas, zip_ruta, repo=REPO):
    paso(f"GitHub ({repo})")
    tok = token()
    rel = github(
        "POST",
        f"https://api.github.com/repos/{repo}/releases",
        {"tag_name": f"v{v}", "name": f"Deep Prep {v}", "body": notas, "make_latest": "true"},
        tok=tok,
    )
    subida = rel["upload_url"].split("{")[0]
    for f, tipo in ((zip_ruta, "application/zip"), (Path(f"{zip_ruta}.sha256"), "text/plain")):
        github("POST", f"{subida}?name={f.name}", f.read_bytes(), tipo, tok=tok)
        print("subido", f.name)
    print(rel["html_url"])


def main():
    puente = "--puente" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--puente"]
    v = args[0] if args else None
    paso("Pruebas")
    if subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=RAIZ
    ).returncode:
        sys.exit("Fallan pruebas: no se publica")
    if v:
        poner_version(v)
    empaquetar()
    zip_ruta = comprimir(v or leer_version())
    zip_puente = comprimir(v or leer_version(), puente=True) if puente else None
    if v:
        notas = args[1] if len(args) > 1 else f"Deep Prep {v}"
        publicar(v, notas, zip_ruta)
        if zip_puente:
            # Las 1.0.x leen releases/latest de su repositorio: esta tiene que quedar como la última de ahí.
            publicar(v, notas, zip_puente, REPO_PUENTE)


if __name__ == "__main__":
    main()

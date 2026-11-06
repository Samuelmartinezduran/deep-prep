"""Empaqueta la app y publica una versión nueva en GitHub (los amigos la reciben sola).

Uso: py herramientas/publicar.py 2.0.1 "Qué cambia" [--puente]   (sin versión: solo empaqueta, para probar)
     py herramientas/publicar.py [2.0.1] [--puente] --solo-construir CARPETA

1. Pasa lo mismo que la CI: ruff format --check, ruff check, mypy, las pruebas con cobertura (y su mínimo) y
   node --test. Si algo falla, no publica. ruff, mypy y coverage salen del entorno de desarrollo si lo hay
   (.venv en el proyecto o ~/.venvs/deep-prep); si no, de este mismo python.
2. Pone la versión en deepprep/__init__.py y empaqueta con PyInstaller + ffmpeg.
3. Comprime en empaquetado/DeepPrep-X.Y.Z.zip con su huella (.sha256).
4. Crea la versión en el repositorio público de Deep Prep (código y descargas) y sube los dos archivos.
5. Con --puente, publica también la misma versión en el repositorio de descargas de Porofesor, del que se
   actualizan las 1.0.x, con el zip puente (empaquetado/puente/, ver comprimir): así les llega sola.
La clave de GitHub sale del administrador de credenciales de git; no se guarda en ningún sitio.

Con --solo-construir CARPETA hace lo mismo hasta el paso 3, pero todo dentro de CARPETA (lo de PyInstaller, el zip
con su huella y, con --puente, el zip puente en CARPETA/puente) y sin subir nada. Tampoco cambia la versión: si se
le da una, tiene que ser la de deepprep/__init__.py.
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
# Donde suele estar el entorno de desarrollo (py -m pip install -e ".[dev]"), con ruff, mypy y coverage.
ENTORNOS_DEV = (RAIZ / ".venv", Path.home() / ".venvs" / "deep-prep")


def paso(texto):
    print(f"\n== {texto}", flush=True)


def leer_argumentos(argv):
    """(versión, notas, puente, carpeta de --solo-construir o None) de los argumentos (sin el nombre del programa)."""
    args = list(argv)
    solo = None
    if "--solo-construir" in args:
        i = args.index("--solo-construir")
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            sys.exit("--solo-construir necesita la carpeta donde dejarlo todo")
        solo = Path(args[i + 1]).resolve()
        del args[i : i + 2]
    puente = "--puente" in args
    args = [a for a in args if a != "--puente"]
    return (args[0] if args else None), (args[1] if len(args) > 1 else None), puente, solo


def carpetas(solo=None):
    """(salida de PyInstaller, carpeta del zip, carpeta del zip puente). Con --solo-construir, todo dentro de solo."""
    base = solo or EMP
    return base, base, base / "puente"


def python_de_herramientas(entornos=ENTORNOS_DEV):
    """El python con ruff, mypy y coverage: el del primer entorno de desarrollo que exista; si no, este mismo."""
    for entorno in entornos:
        exe = Path(entorno) / "Scripts" / "python.exe"
        if exe.is_file():
            return str(exe)
    return sys.executable


def comprobaciones(python):
    """Lo que pasa la CI (.github/workflows/ci.yml), en su orden: [(nombre, orden)]."""
    pruebas = ["-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests", "-t", "."]
    return [
        ("Formato (ruff format)", [python, "-m", "ruff", "format", "--check", "--diff", "."]),
        ("Lint (ruff check)", [python, "-m", "ruff", "check", "."]),
        ("Tipos (mypy)", [python, "-m", "mypy"]),
        ("Pruebas con cobertura", [python, "-X", "utf8", *pruebas]),
        ("Cobertura mínima (fail_under de pyproject.toml)", [python, "-m", "coverage", "report"]),
        ("Panel web (node --test)", ["node", "--test"]),
    ]


def pasar_comprobaciones(lista, ejecutar=subprocess.run):
    """Las pasa todas aunque falle alguna (como la CI, para ver todos los problemas de una vez). Devuelve las que fallan."""
    fallan = []
    for nombre, orden in lista:
        paso(nombre)
        try:
            bien = ejecutar(orden, cwd=RAIZ).returncode == 0
        except OSError as e:  # no está la herramienta (p. ej. node fuera del PATH)
            print(f"No se puede ejecutar {orden[0]}: {e}")
            bien = False
        if not bien:
            fallan.append(nombre)
    return fallan


def poner_version(v):
    p = RAIZ / "deepprep" / "__init__.py"
    t = p.read_text(encoding="utf-8")
    # Con LF, como el resto del código: con el CRLF que pone Windows, ruff format --check fallaría la próxima vez.
    p.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', t), encoding="utf-8", newline="\n")


def leer_version():
    return re.search(r'__version__ = "([^"]+)"', (RAIZ / "deepprep" / "__init__.py").read_text(encoding="utf-8")).group(1)


def empaquetar(salida=EMP):
    """PyInstaller + ffmpeg en salida/dist/DeepPrep (lo de PyInstaller, en salida). Devuelve esa carpeta."""
    dist = salida / "dist" / "DeepPrep"
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
            str(salida / "dist"),
            "--workpath",
            str(salida / "build"),
            "--specpath",
            str(salida),
            str(EMP / "entrada.py"),
        ],
        check=True,
        cwd=RAIZ,
    )
    paso("ffmpeg")
    destino = dist / "ffmpeg"
    destino.mkdir(exist_ok=True)
    with zipfile.ZipFile(FFMPEG_ZIP) as z:
        for nombre in z.namelist():
            if nombre.endswith(("bin/ffmpeg.exe", "/LICENSE")):
                (destino / Path(nombre).name).write_bytes(z.read(nombre))
    shutil.copy(EMP / "LEEME.md", dist / "LEEME.txt")
    return dist


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


def main(argv=None):
    v, notas, puente, solo = leer_argumentos(sys.argv[1:] if argv is None else argv)
    if solo and v and v != leer_version():
        sys.exit(f"Con --solo-construir no se cambia la versión: deepprep/__init__.py tiene la {leer_version()}, no la {v}")
    fallan = pasar_comprobaciones(comprobaciones(python_de_herramientas()))
    if fallan:
        sys.exit(f"Falla: {', '.join(fallan)}. No se {'construye' if solo else 'publica'}")
    if v and not solo:
        poner_version(v)
    salida, carpeta_zip, carpeta_puente = carpetas(solo)
    dist = empaquetar(salida)
    zip_ruta = comprimir(v or leer_version(), dist=dist, carpeta=carpeta_zip)
    zip_puente = comprimir(v or leer_version(), puente=True, dist=dist, carpeta=carpeta_puente) if puente else None
    if solo:
        paso(f"Construido en {solo}; no se ha subido nada")
        return
    if v:
        notas = f"Deep Prep {v}" if notas is None else notas
        publicar(v, notas, zip_ruta)
        if zip_puente:
            # Las 1.0.x leen releases/latest de su repositorio: esta tiene que quedar como la última de ahí.
            publicar(v, notas, zip_puente, REPO_PUENTE)


if __name__ == "__main__":
    main()

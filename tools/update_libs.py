"""Actualizador oficial de las DLLs vendidas en lib/ para ThermaHUD.

Descarga la version estable de LibreHardwareMonitorLib desde NuGet (o la
pedida), lee el .nuspec para descubrir las dependencias (grupo net472, con
fallbacks a netstandard2.0 y a nuspec antiguos sin grupos), las descarga de
forma recursiva, reemplaza el contenido de lib/ (conservando .gitkeep) y
deja un backup en %TEMP%/thermahud_lib_backup_<version>.

No hay que tocar ThermaHUD.spec: detecta las DLLs de lib/ por si solo.

Solo Windows. La version equivalente para doble click es tools/update_libs.bat.

Uso:
    python tools/update_libs.py                # ultima version estable
    python tools/update_libs.py 0.9.6          # version concreta
    python tools/update_libs.py --dry-run      # informe sin tocar nada
    python tools/update_libs.py --build        # compila el exe al terminar
    python tools/update_libs.py --yes          # sin confirmaciones
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "LibreHardwareMonitorLib"
NUGET_FLAT = "https://api.nuget.org/v3-flatcontainer/"
TFM = "net472"
SKIP_DEPS = {"mono.posix.netstandard"}
ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "lib"


def nupkg_url(pkg, version):
    return "{0}{1}/{2}/{1}.{2}.nupkg".format(NUGET_FLAT, pkg.lower(), version)


def nuget_versions():
    url = "{0}{1}/index.json".format(NUGET_FLAT, PACKAGE.lower())
    req = urllib.request.Request(url, headers={"User-Agent": "ThermaHUD-update-libs"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    available = data.get("versions") or []
    if not available:
        raise RuntimeError("NuGet no informa versiones para " + PACKAGE)
    return available


def normalize_tfm(target):
    short = (target or "").replace(".netframework", "net").lstrip(".").lower()
    return "net472" if short == "net4.7.2" else short


def download_and_extract(pkg, version, tmpdir):
    out = tmpdir / "{0}_{1}".format(pkg, version)
    out.mkdir(parents=True, exist_ok=True)   # crea el directorio ANTES de descargar
    dst = out / "{0}.{1}.nupkg".format(pkg, version)
    print("  descargando {0} {1} ...".format(pkg, version))
    urllib.request.urlretrieve(nupkg_url(pkg, version), dst)
    subprocess.run(["tar", "-xf", str(dst), "-C", str(out)], check=True, capture_output=True)
    return out


def parse_nuspec_deps(pkg_root):
    """Exacta net472 -> netstandard2.0 -> grupo 4.7.x -> deps directas sin grupo."""
    nuspec = next(pkg_root.rglob("*.nuspec"), None)
    if nuspec is None:
        raise RuntimeError("nupkg sin .nuspec: {0}".format(pkg_root))
    tree = ET.parse(nuspec)
    chosen = None
    fallback = None
    dependencies_el = None
    for el in tree.iter():
        local = el.tag.split("}")[-1]
        if local == "group":
            short = normalize_tfm(el.get("targetFramework") or "")
            if short == TFM:
                chosen = el
                break
            if short == "netstandard2.0" and fallback is None:
                fallback = el
            if "4.7" in short and fallback is None:
                fallback = el
        if local == "dependencies" and dependencies_el is None:
            dependencies_el = el
    if chosen is None:
        chosen = fallback
    if chosen is None and dependencies_el is not None:
        chosen = dependencies_el    # nuspec antiguo sin <group> (p.ej. HidSharp)
    if chosen is None:
        raise RuntimeError("sin dependencias en " + str(pkg_root))
    deps = []
    for dep in chosen:
        if dep.tag.split("}")[-1] != "dependency":
            continue
        pid, pver = dep.get("id"), dep.get("version")
        if pid and pid.lower() not in SKIP_DEPS:
            deps.append((pid, pver))
    return deps


def find_dlls(pkg_root):
    for sub in ("lib/{0}".format(TFM), "lib/netstandard2.0",
                "runtimes/win-x64/lib/{0}".format(TFM)):
        p = pkg_root / sub
        if p.exists():
            return sorted(p.glob("*.dll"))
    return []


def find_lhm_dir(extracted):
    for sub in ("runtimes/win-x64/lib/{0}".format(TFM), "lib/{0}".format(TFM)):
        p = extracted / sub
        if (p / "LibreHardwareMonitorLib.dll").exists():
            return p
    raise RuntimeError("falta LibreHardwareMonitorLib.dll (win-x64/net472)")


def resolve_deps(top_deps, tmpdir):
    found = {}
    todo = list(top_deps)
    while todo:
        pid, pver = todo.pop(0)
        if pid.lower() in found:
            continue
        try:
            extracted = download_and_extract(pid, pver, tmpdir)
        except Exception as e:
            raise RuntimeError("fallo descargando {0} {1}: {2}".format(pid, pver, e))
        found[pid.lower()] = extracted
        try:
            for d in parse_nuspec_deps(extracted):
                if d[0].lower() not in found:
                    todo.append(d)
        except RuntimeError:
            pass
    return found


def run_build():
    pyi = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    binary = str(pyi) if pyi.exists() else "pyinstaller"
    print("compilando exe...")
    subprocess.run([binary, "--clean", "ThermaHUD.spec", "--noconfirm"],
                   cwd=str(ROOT), check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     allow_abbrev=False)
    parser.add_argument("version", nargs="?", help="version concreta (por defecto, la ultima estable)")
    parser.add_argument("--dry-run", action="store_true", help="informe sin tocar nada")
    parser.add_argument("--build", action="store_true", help="compilar el exe al finalizar")
    parser.add_argument("--yes", "-y", action="store_true", help="sin confirmaciones interactivas")
    args = parser.parse_args()

    current = sorted(p.name for p in LIB_DIR.glob("*.dll"))
    print("lib/ actual ({0} DLLs):".format(len(current)))
    for name in current:
        print("  ", name)

    available = nuget_versions()
    stable = [v for v in available if "-" not in v]
    latest_stable = (stable or available)[-1]
    target = args.version or latest_stable
    if target not in available:
        parser.error("la version {0} no existe en NuGet (ultima estable: {1})".format(target, latest_stable))

    print("\nObjetivo: {0} {1}".format(PACKAGE, target))

    tmpdir = Path(tempfile.mkdtemp(prefix="thermahud_libs_"))
    try:
        print()
        extracted = download_and_extract(PACKAGE, target, tmpdir)
        top_deps = parse_nuspec_deps(extracted)
        print("dependencias directas ({0}):".format(TFM))
        for pid, pver in top_deps:
            print("  {0} {1}".format(pid, pver))

        deps = resolve_deps(top_deps, tmpdir)
        dlls = ["LibreHardwareMonitorLib.dll"]
        for pkg_root in deps.values():
            dlls += [f.name for f in find_dlls(pkg_root)]
        dlls = sorted(set(dlls), key=str.lower)

        print("\nDLLs que quedaran en lib/:")
        for name in dlls:
            print("  ", name)
        added = [n for n in dlls if n not in current]
        removed = [n for n in current if n not in dlls]
        if added:
            print("se añadiran:   " + ", ".join(added))
        if removed:
            print("se eliminaran: " + ", ".join(removed))

        if args.dry_run:
            print("\n--dry-run: no se ha modificado nada.")
            return 0

        if not args.yes:
            answer = input("\nContinuar? [S/n]: ").strip().lower()
            if answer.startswith("n"):
                print("Cancelado: no se ha tocado nada.")
                return 0

        # backup fuera del temporal para que sobreviva a la limpieza
        backup = Path(tempfile.gettempdir()) / "thermahud_lib_backup_{0}".format(target)
        if backup.exists():
            shutil.rmtree(backup)
        shutil.copytree(LIB_DIR, backup)

        # Se vacia lib/ conservando .gitkeep: git necesita el archivo para
        # versionar la carpeta (el resto son DLLs regenerables desde NuGet).
        for f in list(LIB_DIR.iterdir()):
            if f.is_file() and f.name != ".gitkeep":
                f.unlink()
        shutil.copy(find_lhm_dir(extracted) / "LibreHardwareMonitorLib.dll",
                    LIB_DIR / "LibreHardwareMonitorLib.dll")
        for pkg_root in deps.values():
            for f in find_dlls(pkg_root):
                shutil.copy(f, LIB_DIR / f.name)

        print("\nlib/ reemplazada ({0} DLLs). ThermaHUD.spec las detecta por si solo.".format(
            len(dlls)))

        if args.build:
            run_build()
        else:
            print("\nEjecuta build.bat para recompilar el exe con la lib/ nueva.")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
        sys.exit(130)

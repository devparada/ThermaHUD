# -*- mode: python ; coding: utf-8 -*-

import glob
import os

# Las DLLs de lib/ se detectan solas: no hay que tocar nada al actualizarlas.
# Si no hay ninguna, se avisa en vez de dejar que PyInstaller falle.
_dlls = sorted(glob.glob(os.path.join(SPECPATH, "lib", "*.dll")))
if not _dlls:
    raise SystemExit(
        "No hay DLLs en lib/. Genera las DLLs con tools\\update_libs.bat "
        "(o ejecuta build.bat, que lo hace solo)."
    )
binaries = [(os.path.relpath(p, SPECPATH), "libs") for p in _dlls]

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'multiprocessing', 'pydoc', 'doctest',
    'bz2', 'lzma', 'sqlite3', 'asyncio', 'xml',
    'profile', 'pstats', 'timeit', 'py_compile', 'zoneinfo'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ThermaHUD',
    version='version.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)

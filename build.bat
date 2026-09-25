@echo off
title ThermaHUD - build
cd /d "%~dp0"

:: ---- Comprueba que lib/ exista (se regenera sola desde NuGet) ----
if exist "lib\LibreHardwareMonitorLib.dll" goto libs_ok

echo [AVISO] Falta lib\LibreHardwareMonitorLib.dll - generando desde NuGet...
if not exist "tools\update_libs.py" (
    echo [ERROR] Falta tools\update_libs.py - descargalo del repositorio.
    pause
    exit /b 1
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tools\update_libs.py" --yes
) else (
    python "tools\update_libs.py" --yes
)
if errorlevel 1 (
    echo [ERROR] No se pudo generar lib\. Ejecuta tools\update_libs.bat a mano.
    pause
    exit /b 1
)

:libs_ok
if exist ".venv\Scripts\pyinstaller.exe" (
    .venv\Scripts\pyinstaller.exe --clean ThermaHUD.spec
) else (
    pyinstaller --clean ThermaHUD.spec
)
pause

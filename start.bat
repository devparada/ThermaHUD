@echo off
title ThermaHUD

:: ---- Comprueba los privilegios ----
net session >nul 2>&1
if errorlevel 1 (
    echo Solicitando privilegios de administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 echo [ERROR] No se pudo relanzar elevado.
    pause
    exit /b
)

:: ---- Ya elevado: ejecuta el codigo fuente ----
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
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src\main.py
) else (
    python src\main.py
)
pause

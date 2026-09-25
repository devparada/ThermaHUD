@echo off
title ThermaHUD - update lib DLLs
setlocal
rem Actualizador de doble click: delega en update_libs.py (misma carpeta).
rem Uso: update_libs.bat [version]  (p.ej. update_libs.bat 0.9.6)

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PYEXE=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

"%PYEXE%" "%ROOT%\tools\update_libs.py" %*
set RC=%ERRORLEVEL%
pause
exit /b %RC%

@echo off
title ThermaHUD
:: —————— Comprueba los privilegios ——————
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Solicitando privilegios de administrador
    powershell -Command "Start-Process '%~f0' -Verb runAs"
    exit /b
)

:: —————— Si ya se ejecuta como admin ——————
cd /d "%~dp0"
python main.py
pause

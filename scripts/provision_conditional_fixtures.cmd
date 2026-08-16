@echo off
setlocal
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0provision_conditional_fixtures.ps1"
if errorlevel 1 exit /b 1

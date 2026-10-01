@echo off
title MonkeyFacesMeme
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_telegram.ps1"
if errorlevel 1 pause

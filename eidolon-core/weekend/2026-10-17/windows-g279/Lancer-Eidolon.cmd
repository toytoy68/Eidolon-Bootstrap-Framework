@echo off
rem Eidolon Core - Eidolon Core Technologies (ECT)
rem Local AI - Modular - Reliable - Reproducible
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0eidolon-open.ps1" -ClientExe "%~dp0eidolon-consultation.exe"
if errorlevel 1 pause

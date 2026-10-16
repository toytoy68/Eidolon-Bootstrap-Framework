@echo off
rem Eidolon Core - Eidolon Core Technologies (ECT)
rem Local AI - Modular - Reliable - Reproducible
if not exist "%~dp0eidolon-consultation.exe" (
  echo Placez ce fichier a cote de eidolon-consultation.exe.
  pause
  exit /b 2
)
start "Eidolon" "%~dp0eidolon-consultation.exe" --port 8767

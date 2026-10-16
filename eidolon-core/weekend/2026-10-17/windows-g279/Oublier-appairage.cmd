@echo off
rem Eidolon Core - Eidolon Core Technologies (ECT)
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0eidolon-open.ps1" -ForgetPairing
pause

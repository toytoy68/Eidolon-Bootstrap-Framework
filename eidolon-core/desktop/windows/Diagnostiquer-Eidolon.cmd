@echo off
rem Eidolon Core - Eidolon Core Technologies (ECT)
setlocal
cd /d "%~dp0"
echo Eidolon - diagnostic du lancement
echo Cette fenetre restera ouverte en cas d'erreur.
echo.
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0eidolon-open.ps1"
echo.
echo Code de sortie : %errorlevel%
echo.
echo Si Windows indique que le script est telecharge et non signe :
echo fermez cette fenetre, clic droit sur le ZIP original, Proprietes, Debloquer,
echo puis extrayez de nouveau tout le ZIP dans votre dossier Eidolon.
echo Ne transmettez jamais de mot de passe ou de cle.
pause

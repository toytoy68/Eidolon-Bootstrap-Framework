@echo off
rem Eidolon Core - Eidolon Core Technologies (ECT)
rem Local AI - Modular - Reliable - Reproducible
rem Recipe G277: only a local SSH forwarding, no firewall or policy change.
echo Eidolon - connexion au serveur

echo Empreinte ED25519 attendue :
echo SHA256:riG5M5w2V+7CuPEzZI/tcdn5cxvhFVHj8k7OTtx2k1Y

echo Gardez cette fenetre ouverte pendant l'utilisation d'Eidolon.
echo Apres authentification SSH, ouvrez Lancer-Eidolon.cmd.
ssh -o StrictHostKeyChecking=ask -o HostKeyAlgorithms=ssh-ed25519 -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -N -L 127.0.0.1:8767:127.0.0.1:8767 toytoy@192.168.1.101
if errorlevel 1 echo Connexion SSH interrompue ou refusee.
pause

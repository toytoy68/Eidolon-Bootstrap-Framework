# Eidolon sur ton PC — raccordement G277

Le binaire reste celui de G270, SHA-256 `3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`. Il affiche l'interface actuelle servie par Core. Ces instructions sont préparées depuis les VM ; leur exécution Windows reste à faire.

1. Mettre `Eidolon-tunnel.cmd` et `Lancer-Eidolon.cmd` à côté de `eidolon-consultation.exe` sur le Bureau.
2. Ouvrir `Eidolon-tunnel.cmd`. À la première connexion, comparer l'empreinte SSH affichée à `SHA256:riG5M5w2V+7CuPEzZI/tcdn5cxvhFVHj8k7OTtx2k1Y` avant acceptation. S'authentifier avec le compte Linux `toytoy` ; garder cette fenêtre ouverte. Ce serveur Core est `192.168.1.101`. `192.168.1.135` héberge l'inférence distante, pas l'interface à ouvrir.
3. Dans PowerShell, copier la clé de conversation privée dans le presse-papiers :

```powershell
ssh -o HostKeyAlgorithms=ssh-ed25519 toytoy@192.168.1.101 "cat /home/toytoy/eidolon-beta/pc-toytoy-g277-token" | Set-Clipboard
```

4. Ouvrir `Lancer-Eidolon.cmd`, qui lance le `.exe` avec `--port 8767`, puis coller la clé dans la barre du haut. Un double-clic direct sur le `.exe` utilise son défaut 8765, incompatible avec ce tunnel. La clé ne figure pas dans ce paquet. Effacer ensuite le presse-papiers avec `Set-Clipboard -Value ''`.
5. Vérifier une discussion, puis « Retenir ceci » avec une note de recette explicite. Le dossier `recette` contient uniquement un document synthétique. Le NAS personnel et Internet ne sont pas encore raccordés à ce profil.

Pour arrêter le tunnel, faire Ctrl+C dans sa fenêtre. Les scripts résident/démarrage du paquet G270 restent disponibles ; l'installation au démarrage Windows, WebView2, le micro et la webcam exigent une validation sur le PC.

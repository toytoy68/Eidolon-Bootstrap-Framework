# G283 — Eidolon.exe avec icone et raccourci

Demande directe toytoy du 17/10/2026 : executable Windows epinglable avec l’icone Eidolon.

Le lanceur WinExe C# utilise l’icone existante `desktop/tauri/icons/icon.ico`. Il execute `eidolon-open.ps1` depuis son propre dossier ; ce script conserve la recuperation SSH et le stockage DPAPI G279. Aucun secret en argument du lanceur. Le client Tauri reste `eidolon-consultation.exe`, le point d’entree utilisateur devient `Eidolon.exe`.

`Eidolon.exe --shortcut` cree `Eidolon.lnk` sur le Bureau du compte courant, vers l’EXE et son icone embarquee. Il refuse d’ecraser un raccourci existant. `Creer-raccourci.cmd` appelle cette option. Aucun epinglage force, installation systeme, demarrage automatique ou modification du tunnel.

La CI compile avec le compilateur .NET Framework de Windows, teste un faux script d’appairage sans identifiants dans un chemin contenant espaces et &, puis inspecte le raccourci et l’icone. Le ZIP inclut les deux EXE, le script d’appairage, le raccourci et le guide, avec SHA256SUMS. Compilation et execution Windows restent a confirmer par le workflow de cette livraison. L’epinglage et le lancement sur le PC utilisateur restent a verifier sur place.

Limites : paquet non signe ; console transitoire pour permettre le premier mot de passe SSH ; tunnel habituel deja ouvert. Ne pas deplacer le dossier apres creation du raccourci.

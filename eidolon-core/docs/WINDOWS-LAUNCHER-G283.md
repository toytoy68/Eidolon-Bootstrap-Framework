# G283 — Eidolon.exe avec icone et raccourci

Demande directe toytoy du 17/10/2026 : executable Windows epinglable avec l’icone Eidolon.

Le lanceur WinExe C# utilise l’icone existante `desktop/tauri/icons/icon.ico`. Il execute `eidolon-open.ps1` depuis son propre dossier ; ce script conserve la recuperation SSH et le stockage DPAPI G279. Aucun secret en argument du lanceur. Le client Tauri reste `eidolon-consultation.exe`, le point d’entree utilisateur devient `Eidolon.exe`.

`Eidolon.exe --shortcut` cree `Eidolon.lnk` sur le Bureau du compte courant, vers l’EXE et son icone embarquee. Il refuse d’ecraser un raccourci existant. `Creer-raccourci.cmd` appelle cette option. Aucun epinglage force, installation systeme, demarrage automatique ou modification du tunnel.

La CI compile avec le compilateur .NET Framework de Windows, teste un faux script d’appairage sans identifiants dans un chemin contenant espaces et &, puis inspecte le raccourci et l’icone. Le ZIP inclut les deux EXE, le script d’appairage, le raccourci et le guide, avec SHA256SUMS. Compilation et execution Windows restent a confirmer par le workflow de cette livraison. L’epinglage et le lancement sur le PC utilisateur restent a verifier sur place.

Limites : paquet non signe ; console transitoire pour permettre le premier mot de passe SSH ; tunnel habituel deja ouvert. Ne pas deplacer le dossier apres creation du raccourci.

## Verification terminee

Workflow Windows `39007775750`, job `117323651955`, commit `ba96cf9db110c46d223bd04efd0f4571b3b92818` : succes. Tests d'appairage, tests Rust, compilation release, compilation du lanceur C#, lancement synthetique (chemin avec espaces et &), inspection du raccourci et de l'icone, previews et resident existants : reussis sur Windows.

Archive CI `12091955805`, SHA-256 `78db71dd390ae381a9e71381adb07a8d3cdfa0a25eecf2a92618f7edcf621578` telechargee et controlee. ZIP utilisateur `eidolon-pc-g283.zip` : 2 735 172 octets, SHA-256 `46243c1925d0a81fc6bfc36563a6c5c97f44a9e05d4d3c60c442f979c9caea28`. Integrite ZIP et toutes les empreintes du manifeste verifiees. Le clic/epinglage sur le PC utilisateur reste a effectuer ; aucune validation locale au PC n'est presumee.

# Réconciliation réseau — VM Eidolon (2026-10-10)

## État observé sur Proxmox et Debian

| VM | Nom Proxmox retenu | IP observée | Fonction |
| --- | --- | --- | --- |
| 100 | Eidolon-core | 192.168.1.101 | Core, orchestration |
| 101 | Eidolon-Test-IA | 192.168.1.135 | Ollama, V100, Open WebUI |
| 110 | Eidolon-Memory | 192.168.1.110 | Memory Engine |

**Ne pas permuter les adresses des VM.** L'inventaire VM100/101 a été réalisé avec l'opérateur.

## Problème et correction

Le script racine `01-system.sh` déclarait `HOSTNAME=Eidolon-Core-Alpha` et `STATIC_IP=192.168.1.135/24`, alors que cette IP est actuellement attribuée à VM101. Correction sur branche de travail :
- défaut `EIDOLON_HOSTNAME=Eidolon-core` (surcharge locale possible) ;
- défaut `EIDOLON_STATIC_IP=192.168.1.101/24` (surcharge locale possible).
- La variable STATIC_IP est actuellement **déclarée mais non appliquée** par ce script ; en revanche `hostnamectl set-hostname` est appelé lorsque nécessaire. Ne pas exécuter l'installateur avant revue du reste de son comportement.

## Points encore ouverts

- Recherche GitHub `search` sur les branches par défaut : aucune occurrence trouvée de `192.168.1.135` ; **cette recherche ne couvre pas les branches de travail**. Inspection manuelle des fichiers connus : occurrence identifiée dans `01-system.sh` sur les branches Claude et Codex ; les autres fichiers de configuration n'ont pas encore fait l'objet d'un balayage exhaustif.
- Ne pas confondre URL d'écoute du service Core avec URL de l'API Ollama sur VM101. Les noms exacts des paramètres doivent être repris du code réel avant modification.
- VM101 expose Ollama sur le port 11434 et Open WebUI sur 3000 ; vérifier pare-feu IPv4/IPv6 et authentification avant d'autoriser Core à les joindre.
- VM110 reste source de vérité pour Memory Engine ; aucune migration ou réinstallation nécessaire.
- Pour les installations futures, éviter toute IP fixe dans le code métier ; fournir des profils locaux documentés, non secrets, et un contrôle des collisions avant toute modification réseau.

## Validation à effectuer

1. Examiner les autres scripts de bootstrap et les paramètres API du Core sur la branche réellement déployée.
2. Vérifier résolution, connectivité et restrictions d'accès entre 100 → 101:11434 et 100 → 110 (API mémoire).
3. Tester l'installation sur VM100 après sauvegarde/snapshot et revue des scripts ; ne pas changer le réseau de VM101.
4. Reporter les résultats mesurés et la branche/commit exacts.

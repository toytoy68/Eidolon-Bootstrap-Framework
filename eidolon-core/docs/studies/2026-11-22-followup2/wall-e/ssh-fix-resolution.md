## Résolution SSH WALL-E — 22 novembre 2026

Le correctif `IPQoS=none` est appliqué uniquement au client SSH de la passerelle WALL-E. La sortie opérateur atteste la conservation des montages, des clés et de la vérification stricte des clés hôtes, avec pré/postcontrôles réussis. Module NAS : `/mnt/tank/eidolon-collaboration/wall-e-stage-0ewvyp2u/wall_e_access.py`, SHA-256 après : `af479145df9c7384e13a07d6ef3a2a7cc15f8df73e8bc450bdc44458df402c4d`. Sauvegarde : `/mnt/tank/eidolon-collaboration/wall-e-ssh-qos-p65gpj85`.

Vérification indépendante par le pont MCP : hostname wall-e-001, sudo UID 0, puis nouveau sommeil réel deep et réveil réseau, sans redémarrage, 102,99 s avant le secours RTC. Le troisième cycle auparavant illisible avait également repris, 22,03 s avant son RTC. Le blocage SSH est donc résolu dans ces essais.

Après la nouvelle reprise : dashboard, modèle local et tunnel Ollama actifs ; API santé OK ; Ollama 0.32.15 accessible ; PIXY et son entrée audio détectées. Le garde réseau post-reprise est bien exécuté et évite une reconnexion inutile lorsque NAS et routeur répondent. Sa branche de réparation d'une panne reste testée par simulation ; elle ne corrige pas le défaut DSCP. Voix inactive comme avant les essais. Plafonds CPU restaurés à 3,3 GHz, alarme RTC vide, aucun processus de test temporaire restant.

Limites : cycles courts seulement, pas de validation nocturne prolongée ; détection USB/audio sans nouvelle capture ni validation de qualité ou de suivi caméra. La cause précise du filtrage DSCP dans le réseau reste indéterminée. Les observations antérieures sont conservées comme historique, et leurs mentions de blocage ne décrivent plus l'état courant.

Preuves : `wall-e/ssh-fix-final.json`. Archive des six cycles et journaux conservée sur WALL-E et X399 : `wake-proof-after-qos.tar.xz`, SHA-256 `e36b611e07ebd05645dfd80fe0e7cc28bc1d71ea4c118aefd3cd6cad700a13d3`.

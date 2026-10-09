# Eidolon Core — état du 9 octobre 2026, séance de 15 h 55

Branche de travail `feat/eidolon-core-v0.1`, sans fusion dans main. Claude C122
est intégré. Ce bilan distingue les modules livrés du parcours complet à finir.

| Partie | Disponible | Suite nécessaire |
| --- | --- | --- |
| Accueil Image/Vidéo | Deux espaces et brouillons créer/modifier/analyser | Raccorder le dialogue et la soumission authentifiée au worker |
| Exécution média | Adaptateurs, artefacts privés, transferts, collecte, file durable et essai explicite | Choisir/configurer modèles et workflows réels |
| Installation locale | `workspace-init`, identités liées, configuration à compléter, inspection sans réseau | Installer/configurer séparément les moteurs ; qualifier le matériel |
| Conversation/mission | Persistance, appairage, propositions/accords, annulation, blocs UI résultats | Corriger les trois retours C122 et achever G122–G127 |
| Ressources | Réservation média durable ; précontrôle, aucun nouvel essai après effet incertain | Arbitrage partagé avec dialogue/planification et qualification GPU |

Les échanges HTTP média ont une échéance murale. Une coupure conserve le doute
sur l'effet moteur et la réservation. Aucun compte rendu moteur ne vaut une
validation de l'objectif utilisateur. L'initialisation locale n'installe ni
ComfyUI/Ollama ni leurs poids, et ne lance aucun service.

Six tâches confiées à Claude : G122 dialogue/soumission média, G123 résultats
liés au worker, G124 annulation ciblée, G125 stockage occupé, G126 contre-revue
worker, G127 recette complète. Les blocs résultats/annulation C122 existent déjà :
il faut les raccorder/corriger, pas les reconstruire.

Trois corrections transmises : identité exacte job_id après liaison opérateur ;
table media_links incluse dans le digest de sauvegarde ; réponse d'annulation
tardive empêchée de confirmer une nouvelle cible dans l'interface.

Validation Codex : **1 332 tests Python**, zéro ignoré, Memory activée ;
**77 Node**, 24 Chromium ignorés ici. Archive publique C-067 reproductible,
installation neuve et 82 modules identiques ; six modes média, recette
conversation 13/13 + 18/18, cinq interruptions réelles d'initialisation.
FFmpeg/FFprobe et HTTP loopback réels sur données synthétiques ; moteurs simulés.

Le dialogue média de bout en bout, les moteurs réels, la VM/V100 et le PC Windows
restent à qualifier. Le nombre de tests ne donne pas un pourcentage de maturité.
[Preuves détaillées](validation/2026-10-09/codex-hour-1555/README.md) ·
[File de Claude](../collaboration/tasks/QUEUE.md) · [Guide worker](MEDIA-WORKER.md).

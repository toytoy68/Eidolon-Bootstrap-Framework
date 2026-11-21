# ADR - Priorisation et intégration Eidolon, 20 novembre 2026

Eidolon Core Technologies (ECT) - Local AI • Modular • Reliable • Reproducible

## Décision
Conserver Debian, Core, Memory Engine et les runtimes de production. Réconcilier les branches dans une branche de validation, isoler les expériences et promouvoir seulement un lot dont les critères fonctionnels et de reprise sont satisfaits. Aucun nouveau noyau ni déploiement automatique en production.

## Ordre de travail
| Priorité | Lot | Critère de sortie |
|---|---|---|
| P0 | Stockage | Copie, contrôle intégral par checksum et maintien du chemin historique ; une copie vérifiée conservée. |
| P0 | Divergence Core/Memory | Historique sauvegardé, branches intégrées, régressions corrigées, PR avec preuves. |
| P0 | DARME #3 | Validation structurée, reçus signés, outbox et contrôle OS indépendant. Une preuve bwrap ne vaut pas validation de bout en bout. |
| P0 | Index Memory | Nettoyer uniquement les générations non publiées ; garder les publications ambiguës. Ensuite corriger le rappel temporel et l'obsolescence FR100. |
| P1 | llama.cpp / MoE #8 | Build Volta, contrôle numérique, A/B même modèle et plafond de puissance. Distinguer toolchain standard et patch expérimental. |
| P1 | Orchestration #9 | Réutiliser routeur, tool policy, DARME, queue GPU et worker média ; relier autorisation, processus, résultat et reçu durable. |
| P1 | Mini-modèles / Prism #13 #14 | Modèles et licences figés ; compatibilité locale puis qualité et matériel cible. Aucun remplacement d'Eva ou contrôle moteur par LLM. |
| P1 | Kiri #16 | VM, même image, séries répétées ; garder Docker/Podman tant que cgroups, crash, rootless, Compose et périphériques restent non qualifiés. |
| P2 | Embeddings #15 | Prototype texte/image FP32 ; corpus réel, ACL, dates et obsolescence avant nouvel index de production. |
| P2 | Supervision / voix #10 | Réutiliser NVIDIA, systemd, libvirt, Shelly/NAS ; corpus vocal autorisé et licence compatible. |
| P2 | Builds / ISO #12 | Sources figées, hashes, isolation, artefacts et boot VM ; aucune ISO expérimentale en production. |
| P3 | Matériel #11 | Aucune acquisition ; CXL exclu sur X399 ; pilotes et mesures équivalentes requis avant remplacement. |

## Contrat d'orchestration
1. Le modèle émet une proposition structurée sans exécution implicite.
2. Core vérifie schéma, contexte, identité et politique ; DARME décide indépendamment.
3. L'exécuteur crée un job et un dossier privé, applique restrictions OS et timeout.
4. L'outil fournit résultat, code de sortie et preuves ; l'outbox transmet un reçu idempotent.
5. La correction prépare un nouveau candidat isolé. La promotion demeure distincte, avec tests et rollback.

La queue GPU est coopérative. Un PID disparu ne prouve pas l'arrêt d'un moteur distant. Ne pas libérer ACTIVE/UNKNOWN sur simple TTL, ni appliquer un plafond global sans vérifier les autres consommateurs. L'unification des leases exige une preuve de quiescence et des tests de reprise après crash.

## Pipeline retenu
Sources/modèles par commit et SHA256, dépendances de test isolées : build -> tests -> serveur jetable -> artefacts hachés -> boot VM -> machine dédiée -> promotion explicite. Cette session qualifie les premiers étages et les builds llama.cpp ; elle ne livre pas une ISO reproductible complète.

Critères ISO futurs : manifeste packages, absence de secrets, différences reproductibles documentées, UEFI/BIOS selon cible, réseau local, rollback, budget mémoire et journaux. Aucun workflow factice prétendant tester le boot.

## Blocages
- VFIO : remappage d'interruptions désactivé / IOAPIC absent d'IVRS ; aucune activation d'interruptions non sûres.
- Pont de collaboration : synchronisation du checkout Memory côté service en échec ; GitHub direct disponible. Administration NAS générique absente de l'accès exposé.
- N6000/Wall-E non connecté ; aucune mesure extrapolée depuis X399.
- FLUX gated et Phonon FR : accès aux poids soumis aux conditions fournisseur ; aucun contournement.
- Qualité étendue, reconnaissance faciale et multimodal audio/vidéo demandent corpus et prérequis distincts. Les tests ignorés ne sont pas des succès.

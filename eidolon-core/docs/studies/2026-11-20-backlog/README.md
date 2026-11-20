# Résultats consolidés - 20 novembre 2026

Eidolon Core Technologies (ECT)

## Décisions
- Stockage : archives Proxmox froides déplacées et contrôlées intégralement ; volume data passé de 93 % à 71 %, espace disponible de 28 à 111 Gio au terme de la migration. Le chemin historique reste utilisable par lien vers le SSD. Ce déplacement n'est pas une sauvegarde indépendante.
- Core : branches réconciliées et tests verts dans un checkout isolé. Production conservée au commit afb79a7 ; aucune fusion/déploiement.
- Memory : nettoyage des seules générations Qdrant non publiées corrigé et testé, PR Memory #7.
- CUDA : deux builds Volta réussis grâce à quatre déclarations noexcept corrigées dans un toolkit privé CUDA 12.9.2. CUDA standard non qualifié sur ce couple glibc/toolchain ; driver de production inchangé.
- Kiri : intérêt mesuré pour les tâches CLI éphémères ; validation insuffisante pour remplacer Docker/Podman.
- Modèles : compatibilité native LFM3/Prism et prototype EmbeddingGemma 2 démontrés ; qualité générale et intégration non validées.

## Tests logiciels
| Lot | Résultat |
|---|---|
| Core complet | 2463 réussis, 24 ignorés, 2 avertissements, 1349 sous-tests réussis |
| Core propriétaires root | 5 réussis |
| Client Node | 202 réussis, 42 ignorés, build --check réussi |
| Attention Flux recherche | 2 réussis CPU FP32 / V100 FP16 ; écarts max 1,19e-7 / 0 |
| Memory complet corrigé | 3236 réussis, 26 ignorés, 2 échecs attendus, 12 sous-tests réussis |
| Qdrant réel jetable | 19 réussis ; couvre les 19 ignorés de la suite générale |
| Memory montages/verrous root | 16 réussis ; couvre les 7 ignorés de la suite générale |

Les lots ciblés recouvrent la suite générale : ne pas additionner tous ces nombres comme des tests uniques. Les autres tests Core ignorés concernent des dépendances/corpus matériels optionnels. Pillow est déclaré dans la CI ; la sonde Flux ignore explicitement torch/diffusers absents et a aussi été réellement exécutée dans son environnement de recherche.

## llama.cpp natif et modèles
Protocole : V100 à 200 W/GPU, sm_70, prompt 512 et génération 128, 8 threads CPU, Flash Attention. A/B v0.8/v1 : 8 passages équilibrés ABBA BAAB, 3 répétitions internes. Nouveaux petits modèles : 5 répétitions ; MoE : 3. Mesure de débit moteur, pas de TTFT ni de latence utile d'une réponse complète.

| Configuration | Préremplissage tok/s | Génération tok/s |
|---|---:|---:|
| Qwen2.5 1,5B Q4 - llama v0.8 - 1 V100 | 10706,90 | 291,74 |
| Même modèle - llama v1 - 1 V100 | 11224,92 | 293,09 |
| LFM3 1,7B Q4 - 1 V100 | 10453,23 | 297,84 |
| Prism Bonsai 2 2B Q2_0 - 1 V100 | 9405,94 | 246,51 |
| Qwen3 30B-A3B Q4 - 2 V100 | 1181,08 | 153,87 |
| Qwen3 - 1 V100 + 12 couches experts CPU | 307,38 | 70,73 |
| Qwen3 - 1 V100 + tous experts CPU | 123,38 | 28,59 |

v1 apporte ici +0,46 % en génération GPU et +4,84 % en préremplissage : quasi-parité en génération. Le recul CPU historique (-13,17 %) ne se transpose pas au GPU. Le comparatif MoE change aussi le placement CPU des experts : il ne mesure pas le seul effet d'ajouter un GPU. Cache d'experts dynamique et MTP non testés.

Contrôle numérique : 442 opérations ADD/RMS_NORM/SOFT_MAX réussies sur CUDA0 pour chaque version ; MUL_MAT f16/Q4_K/Q2_0 : 582 cas par GPU en v0.8 et 602 par GPU en v1, tous réussis. Un premier filtre vide (0/0) a été rejeté puis corrigé ; il n'est pas compté comme validation.

## Contrôles de sortie des modèles
Quatre questions synthétiques : calcul, mise à jour temporelle, JSON exact et abstention. Qwen baseline : 3/4 sorties strictes, JSON entouré de Markdown. LFM3 : 4/4 réponses finales après extraction ; Prism : 3/4 et une réponse temporelle non terminée au budget 256. Les options reasoning off/budget 0 n'ont pas supprimé le raisonnement dans la sortie brute de cette CLI. Le premier budget 128 tronquait davantage de réponses. Ces sondes diagnostiquent le contrat de sortie ; elles ne constituent ni un classement général ni une validation Wall-E.

## Kiri / Docker / Podman
VM Debian 13, 8 vCPU, 24 Gio, image Alpine 3.22.2 identique vérifiée, rootful, réseau none, image en cache. 100 cycles run --rm true par moteur, ordre mélangé déterministe ; compilation et tests lourds terminés avant la série.

| Runtime | Médiane ms | P95 ms | P99 ms | Échecs |
|---|---:|---:|---:|---:|
| Docker 26.1.5 | 282,49 | 302,40 | 310,59 | 0/100 |
| Podman 5.4.2 | 225,96 | 245,23 | 254,77 | 0/100 |
| Kiri 0.2.2 | 41,58 | 44,61 | 45,49 | 0/100 |

Kiri est environ 6,8 fois plus rapide que Docker sur ce cycle CLI chaud précis. Bind et racine en lecture seule, réseau absent, code de sortie, volume persistant, limites cgroups visibles et suppression forcée contrôlés. Podman a attendu 10 s avant SIGKILL sur un sleep PID1 lors du contrôle séparé ; ce cas n'entre pas dans les 100 cycles. Les limites cgroups ont été lues, pas éprouvées sous saturation. API seule, froid, Compose, rootless, crash moteur, résistance à l'évasion et accès GPU restent à tester.

## Embeddings et sécurité
EmbeddingGemma 2 FP32 texte+image : vecteurs 768D finis ; 3/3 textes français et 3/3 images synthétiques en top-1. Chargement 3,80 s, encodage texte requêtes+documents 0,42 s, images+requêtes 0,52 s, pic alloué PyTorch 2,03 Gio. Inférence hors ligne après téléchargement. Aucun corpus de production ni comparaison FR100 : six contrôles ne démontrent pas la qualité générale.

Sonde bwrap : écriture autorisée fonctionnelle ; fichier privé synthétique invisible ; POST/PUT/DNS bloqués ; aucune requête reçue ; capacités effectives nulles. La chaîne DARME intégrée et sa reprise restent ouvertes.

## Suite priorisée
Voir ADR-PRIORITES.md et les issues #3, #8 à #16 actualisées. En tête : rappel temporel/obsolescence FR100, exécution DARME intégrée, leases GPU avec preuve d'arrêt du moteur, réparation du pont de collaboration côté NAS. Puis évaluations étendues des modèles, voix, embeddings et ISO. VFIO nécessite une correction plateforme/BIOS ; N6000 et matériels de veille ne sont pas connectés. Aucun contournement d'accès aux modèles protégés.

Les plafonds GPU initiaux de 300 W ont été restaurés, les processus de mesure sont terminés et la VM de test arrêtée. Les fichiers JSON et scripts accompagnent ces conclusions. Les résultats de la campagne nocturne sont distincts dans CAMPAGNE-NUIT.md ; les workflows vidéo exécutés mais rejetés visuellement ne deviennent pas des validations qualité.

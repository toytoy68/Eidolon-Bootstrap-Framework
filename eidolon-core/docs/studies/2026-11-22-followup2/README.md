# Qualification complémentaire Eidolon — 22 novembre 2026

Eidolon Core Technologies (ECT) — Local AI • Modular • Reliable • Reproducible

Cette étude poursuit la PR Core #20 à partir de `48e0bb4e8ed3e553058cf21dd0ed354db02a6ebb`. Elle distingue les validations expérimentales, les corrections effectivement appliquées et les préparations sans activation. Preuves complètes : `/srv/eidolon/ssd/work/followup2-20261122` sur X399 et `/home/toytoy/wall-e/qualification-20261122` sur WALL-E.

## État actualisé : accès SSH WALL-E rétabli

Correctif de passerelle appliqué et nouveau cycle deep/réveil validé par MCP, avec droits administrateur et API opérationnelles. Voir la [résolution et ses limites](wall-e/ssh-fix-resolution.md) et les [preuves finales](wall-e/ssh-fix-final.json). La section historique ci-dessous décrit le blocage antérieur.

## WALL-E : quatre fichiers LLM qualifiés sur le N6000

156 réponses terminées : 144 contrats fermés et 12 sondes de conversation, sans erreur d'exécution dans la campagne retenue. CPU uniquement, llama.cpp natif Debian 12, trois threads, plafond temporaire 2 GHz, Q4_K_M, sans cache de préfixe ni raisonnement explicite. Les réponses d'une tentative préalable arrêtée par la garde thermique ne sont pas incluses dans ces scores.

| Fichier testé | Robot | Darme | Système | Critiques réussis | Premier contenu rôle médiane / p95 (s) | RSS serveur max (Mio) | Énergie CPU des requêtes (Wh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| LFM25-1.2B | 4/12 | 10/12 | 4/12 | 14/23 | 42.0 / 49.4 | 858 | 2.747 |
| LFM3-1.7B | 10/12 | 10/12 | 11/12 | 21/23 | 59.6 / 68.2 | 1320 | 3.947 |
| Qwen3-0.6B | 4/12 | 2/12 | 2/12 | 1/23 | 19.1 / 21.7 | 1183 | 1.269 |
| Qwen3-1.7B | 5/12 | 1/12 | 3/12 | 1/23 | 57.5 / 65.9 | 2036 | 3.776 |

**Aucun de ces quatre fichiers ne franchit les gardes prévues pour une fonction active.** Les seuils étaient tous les cas critiques corrects et p95 du premier contenu de rôle inférieur à deux secondes. La cible de premier contenu pour le chat était cinq secondes. Les trois sondes de chat par modèle sont insuffisantes pour certifier une qualité conversationnelle générale.

LFM3 est le meilleur de ce petit lot sur les contrats, mais propose notamment AVANCER devant un obstacle déclaré à zéro centimètre et échoue sur un cas critique Darme. LFM2.5 obtient 10/12 en Darme en répondant toujours BLOQUER : ce score égale la décision constante majoritaire et ne constitue pas une qualification de triage. Les matrices de confusion et rappels par classe sont conservés.

Affectation : LFM3 reste un candidat exploratoire d'explication sous vérification, pas un contrôleur. Aucun nouveau modèle embarqué n'est promu pour le dialogue opérationnel, la sécurité ou l'administration. Pour l'architecture actuelle, privilégier le dialogue déporté vers X399 et conserver localement les règles, permissions, fraîcheur des mesures et arrêts déterministes. La déconnexion réseau doit rester un état explicite ; aucun test de moteur physique n'est revendiqué.

La puissance/énergie publiée est une estimation RAPL du package CPU, activité de fond comprise, sur l'union des fenêtres de requêtes. Ce n'est ni l'électricité à la prise, ni l'autonomie sur batterie. La RAM est celle du serveur testé. Les pauses thermiques et la reprise des 33 premières réponses sont documentées ; les durées complètes ne doivent pas servir de classement d'efficacité.

Les fichiers Qwen sont identifiés par SHA ; le 0,6B porte un nom interne « Instruct Awq », sans chaîne de conversion reconstituée. Les résultats portent sur ces fichiers exacts. Les scores V100 antérieurs utilisent un autre contexte et une autre recette et ne sont pas directement comparables.

Preuves : [synthèse et réponses chat](wall-e/final-summary.json), [méthode et limites](wall-e/INTERPRETATION.md), [identités GGUF](wall-e/gguf-identities.json), [corpus](wall-e/cases.jsonl), [réponses](wall-e/responses.json), [empreinte de l’archive complète](wall-e/archive-proof.json).

Budget de sortie : 0 réponse(s) arrêtée(s) à la limite de tokens. Les champs finish et les réponses intégrales permettent de les identifier.

Les quatre fichiers échouent à la sonde technique 16 cœurs / 32 threads. Premier contenu de chat observé : 6,48 à 22,01 s ; aucune des douze réponses ne respecte la cible de cinq secondes. Le pic thermique de la campagne retenue est 76,05°C, contre la garde 85°C atteinte lors du profil préalable non plafonné. Les plafonds CPU d’origine sont restaurés après le banc.

## WALL-E : historique du réveil et du blocage SSH résolu

Le lancement initial par systemd-suspend.service est refusé parce que sleep.target est masqué. Aucun sommeil réel n'a eu lieu à cet essai. Les masques sont conservés ; les essais suivants appellent directement systemd-sleep depuis une unité transitoire.

Le témoin sans paquet réseau entre réellement en S3/deep et revient après 122,45 s, à l'échéance RTC, sans redémarrage. Deux essais avec paquet magique reviennent respectivement 108,03 s et 98,04 s avant l'alarme : le réveil Wi-Fi physique fonctionne dans ces conditions. Le premier exige une reconnexion du profil Wi-Fi après trois pings négatifs ; le second récupère seul.

Un garde de reprise réseau a été installé : hook post-suspend non bloquant, service borné à 55 s, au plus une réactivation du profil existant si NAS et passerelle restent injoignables. Cinq scénarios simulés passent et le service fonctionne sur machine éveillée. **L'intégration après veille n'est pas qualifiée** : lors du troisième essai, ping et bannière SSH sont accessibles, mais le pont d'administration expire. Ses journaux locaux et l'état final caméra/API n'ont pas pu être relus. Le garde reste installé ; son critère ICMP ne détecte pas ce défaut sélectif du trafic.

Le diagnostic isole le marquage IP : depuis X399, trois connexions TCP SSH avec TOS 184 (DSCP EF) expirent ; les neuf connexions témoins TOS 0, 32 et 72 obtiennent la bannière SSH. Un client SSH avec IPQoS=none franchit la connexion et atteint la vérification de clé hôte ; la clé n'étant pas connue sur X399, cette vérification reste stricte et aucun accès nouveau n'est accordé. Le client X399 annonce IPQoS ef cs1. Le NAS hôte atteint également la bannière par socket ordinaire. La cause précise dans le pilote, le point d'accès ou la gestion WMM n'est pas démontrée.

**Blocage restant :** le pont wall_e_execute ne propose pas de réglage IPQoS, et le compte d'archivage NAS ne peut pas lire les clés de sa passerelle. Aucune permission ni clé hôte n'a été contournée. La [commande opérateur](wall-e/operator-recover-nas.sh) utilise les clés existantes dans le conteneur avec IPQoS=none pour réactiver le profil Wi-Fi. Après cela, relire les preuves du troisième cycle, retirer ou corriger le garde insuffisant, puis refaire les contrôles SSH/API/PIXY. Une veille prolongée reste à qualifier.

L'archive N6000 a été copiée et ses 290 empreintes vérifiées sur X399 avant ces essais. Les plafonds CPU initiaux étaient restaurés et les collecteurs temporaires arrêtés avant la première veille. WALL-E répond au réseau au dernier diagnostic ; son état applicatif final n'est pas certifié. Aucun changement persistant vers s2idle n'a été appliqué.

Preuves : [observations de veille](wall-e/wake-observations.json), [test différentiel DSCP](wall-e/ssh-dscp-proof.json), [script de diagnostic](wall-e/ssh-dscp-probe.py), [garde installé](wall-e/wall-e-resume-network.py).


## Memory : tunnel autonome rétabli

Trois obstacles ont été corrigés dans le laboratoire : règle de pare-feu limitée à la VM de production, mauvaise adresse cible du tunnel et absence de la clé dédiée de la VM de test dans l'autorisation X399. La VM de test utilise maintenant la passerelle du pont libvirt avec clé hôte épinglée. La nouvelle autorisation est limitée à sa source, au transfert vers Ollama loopback et refuse le shell.

La reprise après redémarrage de la VM est vérifiée : service actif, Ollama 0.32.15 joignable, shell et transfert vers un autre port refusés. Le test ne repose plus sur un tunnel inverse manuel. Les configurations précédentes sont sauvegardées. La VM a ensuite retrouvé son état initial arrêté.

Trois documents synthétiques complets, 47 961 caractères, sont couverts par 48 passages avec reconstruction exacte et sources inchangées. Publication réelle Qdrant/embedding en 380,4 s ; deuxième synchronisation sans nouvelle inférence. Neuf recherches d'extraits de 300 caractères retrouvent le passage attendu parmi les cinq premiers résultats.

**Limite :** ces recherches littérales ne mesurent pas le rappel sémantique indépendant. Le passage par une projection de staging explicite est qualifié ; le chemin natif des documents ordinaires reste à intégrer dans le moteur Memory. La production reste distincte : 205 points d’information et un descripteur, digest inchangé et timer actif lors du contrôle.

Preuves : [résultat documents longs](memory/longdocs-result.json), [tunnel après redémarrage](memory/tunnel-after-reboot-proof.json), [production](memory/production-proof.json).

## Eva : régression caractérisée, E7 préparé

E6 reste rejeté. La comparaison réponse par réponse montre sur X3 sept gains mais dix pertes par rapport au parent : huit pertes dans une variante de formulation, deux dans l'autre. Les gains nets X1/X2 ne compensent donc pas la perte de capacités déjà acquises. Les erreurs comprennent des additions de 60 ou des doubles comptes de minutes. L'interférence d'apprentissage est une hypothèse, pas une causalité démontrée.

Un oracle indépendant a contrôlé les 772 cibles d'entraînement X1/X2/X3 des deux passages disponibles : aucune erreur de calcul ni cible contenant un faux séparateur de ligne n'a été trouvée.

Le protocole E7 propose une seule variation d'entraînement : taux d'apprentissage 1e-6 → 2,5e-7. Parent cycle 5, corpus équilibré, replay, budget, packing et graine restent fixes. Les seuils historiques X1/X2/X3 et les autres sondes doivent tous être conservés ; l'analyse des pertes individuelles accompagne le score global. Arrêt à 102 mises à jour si une garde échoue ; aucune promotion automatique. Un lot indépendant et ses critères doivent être figés avant le prochain entraînement, puis ouverts seulement après les gardes de développement. Ce lot reste à produire ; le protocole et la configuration sont préparés.

**E7 n'a pas été entraîné et aucune amélioration n'est revendiquée.** L'adaptateur parent est inchangé. Le contrôle thermique/ECC d'origine et la puissance de 200 W par V100 restent requis pour la prochaine exécution.

Preuves : [comparaison appariée](eva/paired-regressions.json), [audit des cibles](eva/training-oracle-audit.json), [protocole E7](eva/protocol-e7.json).

## Core : tous les tests optionnels restants exécutés

Les 12 tests vision/médias auparavant non couverts ont été exécutés dans un environnement dédié. Le lot ciblé contient 20 tests réussis, zéro ignoré : YuNet/SFace, WeSpeaker/fbank, AnimateDiff, codecs PyAV, Flux FP32 et FP16 réel sur V100, Sana.

Les modèles et runtimes sont épinglés ; les entrées sont synthétiques. Ces tests valident des contrats numériques, formats, refus d'entrées et chemins d'exécution. Ils ne certifient pas la qualité artistique, la reconnaissance biométrique en situation réelle ni une génération vidéo complète. Les compteurs de suites et jobs historiques se recoupent ; ils ne sont pas additionnés.

Preuves : [couverture](media-coverage.json), [journal](media-tests.log), [versions](media-versions.txt).

## Darme : revue et paquet de déploiement prêts

Relecture de la frontière Unix, des identités SO_PEERCRED, des bornes UTF-8/trames, des délais, des champs refusés, du worker bubblewrap et de la vérification indépendante du résultat. Aucun nouveau défaut bloquant identifié dans le périmètre `text.stats` ; revue réalisée par Codex, sans audit tiers.

Paquet de 146 fichiers source, manifeste, précontrôle et unité systemd préparés. Le compte proposé `eidolon-darme-exec` est séparé du Darme existant et du compte Core. La recette inclut les contrôles entre comptes distincts, le refus hors périmètre et le retour arrière. Le Runtime nécessite un raccordement explicite.

**Aucun déploiement de cet exécuteur en production, aucune fusion de PR.** Le prototype ne qualifie ni moteurs, ni shell général, ni effets externes. Un compte Core hostile peut encore dégrader la disponibilité de la file bornée.

Preuves : [procédure et retour arrière](darme/DEPLOYMENT.md), [précontrôle](darme/preflight-result.json), [manifeste](darme/manifest.json).

## NAS : snapshots constatés et supervision indépendante installée

Les snapshots automatiques quotidien du 22 novembre à 03 h et hebdomadaire à 04 h existent sur `tank/eidolon-darme-archive`. L'échéance mensuelle du 1er décembre n'a pas encore été validée.

Un suivi local s'exécute sur TrueNAS toutes les cinq minutes, sous le compte d'archivage sans droit administrateur. Il relève la joignabilité du switch, celle de X399, sa puissance Shelly, la fraîcheur des archives et les snapshots. Trois observations ICMP négatives consécutives distinguent une anomalie persistante ; une lecture Shelly récente sous 5 W classe X399 arrêté selon le protocole utilisateur.

La première exécution planifiée est attestée. Quatre scénarios de classification sont testés, dont hôte arrêté et puissance inconnue. La lecture de tous les enregistrements JSONL vérifie les vrais séparateurs de lignes.

**Limites :** journal local uniquement, aucune notification externe nouvelle. La collecte SNMP détaillée et son relais Discord restent sur X399. L'arrêt réel de X399 n'a pas été provoqué pour cet essai ; la classification hôte arrêté est testée par simulation. Le cron personnel est sur TrueNAS, sa conservation lors d'une mise à niveau TrueNAS n'est pas qualifiée.

Preuves : [première exécution planifiée](supervision/scheduled-proof.json), [tests](supervision/monitor-tests.json), [script](supervision/nas-health.py).

## État système et travaux distincts

Core API, Darme passif et les timers SNMP/archivage/Discord sont actifs ; leurs dernières exécutions contrôlées sont réussies. Trois unités de compilation V100/Ubuntu d’un autre chantier apparaissent en échec à 18 h 12–18 h 22. Elles ne sont ni modifiées ni effacées par ce lot ; leur diagnostic appartient à ce chantier. Aucun état global « zéro erreur système » n’est revendiqué.

Preuve : [état des unités](system-final.json).

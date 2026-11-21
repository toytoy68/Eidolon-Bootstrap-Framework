# Maintenance, intégration et chaîne Darme — 21 novembre 2026

Eidolon Core Technologies (ECT) — Local AI • Modular • Reliable • Reproducible

## Autorisation et périmètre
Suite autorisée par toytoy après audit : maintenance Memory, pont Git, blocages Darme, intégration des travaux validés. Développement isolé dans codex/maintenance-darme-20261121. Aucun nouvel entraînement Eva, changement GPU/BIOS ou arrêt de la machine.

## Maintenance Memory
Le service avait échoué le 21 novembre à 20:32:56 Europe/Paris avec REFUSED_OR_INCOMPLETE / effects UNKNOWN. La cause historique précise est indéterminée : l'ancien journal supprimait les détails et l'échec n'a pas été reproduit. Lecture d'activité authentifiée, configurations, binding du profil et ouverture de l'index ont réussi séparément. À 22:44:34, le service original a terminé avec DEFERRED / OUTSIDE_WINDOW, code 0.

Défaut constaté : ouverture de Qdrant avant l'évaluation de la plage et des gardes. Le correctif reporte cette ouverture jusqu'à l'admissibilité du tick passage. Les échecs CLI indiquent une étape constante (POLICY, ACTIVITY, OBSERVATION, RUNTIME_CONFIG, TICK), sans message d'exception ni secret. Avant TICK : effects NONE ; un tick commencé conserve UNKNOWN.

Correctif minimal installé dans le checkout de maintenance de la VM, sans remplacer son code Memory ni son corpus. SHA256 avant : 3f5b70d2d9ffb585407588669405b0eb7e692177b4edc53a1111348ddefe4a34 ; après : f3cc4dac7444050f9ab1d8c4820ecaadb6832a98e33e2235b61e9c973d826c66. Sauvegarde : /home/toytoy/eidolon-maintenance-backups/20261121/maintenance_host.py. Retour arrière : restituer ce seul fichier puis contrôler le service, en conservant les journaux.

Contrôle réel à 22:48:23 : code 0, DEFERRED / OUTSIDE_WINDOW. Timer, tunnel activité et Qdrant actifs ; zéro unité en échec. Index avant/après : 205 points, source_digest e809e38ad7d68a76d3c1102aee2919b44b508aa1464600451e8a7b9117d2941a. Pas de reconstruction forcée hors plage. Le prochain tick nocturne n'est pas revendiqué comme exécuté.

## Darme
Le test utilisant le vrai Runtime et le vrai Store a reproduit une rupture : Store.save ajoute status, phase, progress et outcome ; l'outbox n'acceptait que les six champs SecurityEvent. Les tests antérieurs fabriquaient une table simplifiée. L'export accepte maintenant les deux formes explicites et ne transmet que les six champs d'audit. Aucun paramètre brut ni contexte mémoire dans le feed.

Deux chemins de reprise couverts : un feed déjà inscrit au checkpoint peut être retransmis après expiration sans recréer d'événement ; signature et digest exact restent vérifiés. Un ancien feed jamais accepté reste refusé. Après crash entre suppression du feed acquitté et suppression du fichier pending, seule l'égalité exacte avec le checkpoint durable autorise la finalisation du nettoyage. Les orphelins non acquittés restent bloqués.

Adaptateur opt-in sandbox_registry() : seul text.stats, référence validée par Core, entrée bornée et revalidée dans un interpréteur séparé. Bubblewrap isole réseau/montages/PID/IPC, supprime les capacités et expose /usr en lecture seule, /proc, /dev et un /tmp privé. Aucune commande, chemin ou source Python contrôlés par le modèle. Timeout et limites CPU/mémoire ; absence de sandbox = échec, aucun repli hors isolation. Reçus et vérification des résultats utilisent le worker Core existant.

Preuves réelles sur X399 : mission synthétique réussie et reçu persistant ; interruption après retour conservée en REVIEW_REQUIRED, sans nouvelle tentative ; fichier privé synthétique invisible ; POST/PUT et DNS bloqués ; zéro requête au serveur factice ; capacités nulles ; texte ressemblant à du code traité comme donnée. La chaîne de refus Core -> SQLite -> outbox signée -> journal Darme -> reçu signé -> acquittement est testée de bout en bout avec redémarrage et crash.

Limites : cet adaptateur n'active pas un exécuteur générique en production. Il ne qualifie ni mutations système, ni GPU, ni contrôle moteur robot, ni callbacks arbitraires. Le processus modèle et les autres outils restent des frontières distinctes. Les feeds neufs anciens restent en revue manuelle. Clés et état supposent des répertoires privés et un seul rédacteur. L'issue #3 reste ouverte pour séparation de comptes/service, intégration de tous les outils et contrôle indépendant des effets en production.

## Intégrations GitHub
Core #17 fusionnée dans feat/eidolon-core-v0.1 : ffa53b689f28c7e21a05c1dfbaf5f7e8abdd6af5 ; deux checks CI verts. Memory #7 fusionnée dans refactor/architecture-v1 : 6636cbe0f4f257c1f026e8d03ca7d17abb18b17c ; deux checks CI verts. Core #18, preuves/documentation des rôles et Eva, retargetée puis fusionnée : f89a38fec476558dd79f21e265e5410f2caa2c2b. Ses preuves précédentes sont conservées, aucune nouvelle campagne prétendue. Aucun déploiement global des branches intégrées sur les services de production.

## Pont Git côté NAS
get_exchange_status reste ready=false, Git operation failed; operator intervention required. Les checkouts Core et Memory accessibles ne sont pas ce checkout de service. Les accès exposés n'offrent ni son journal Git détaillé ni une commande d'administration générique du NAS. Aucun reset forcé, suppression de verrou ou remplacement du checkout tenté. GitHub direct permet les lectures et intégrations ; cela ne répare pas le pont.

Reprise côté NAS : identifier service et checkout exact dans la configuration, relever branche/HEAD/status et erreurs Git sans imprimer les secrets, sauvegarder checkout et changements, puis distinguer divergence, conflit local, droits et authentification. Avance rapide seulement pour un checkout propre sans divergence. Conserver toute contribution ; ne pas supprimer aveuglément index.lock. Enfin relancer get_exchange_status et read_gpt_message pour valider par l'accès qui échouait.

## Validation
Résultats finaux et manifeste des fichiers dans VALIDATION.json après exécution. Les tests ignorés ne sont pas des succès.

## Utilisation et réversibilité du nouvel adaptateur
Dans un hôte de test de confiance, passer sandbox_registry() au paramètre registry de Runtime. Seul text.stats est enregistré ; les propositions d'autres outils sont refusées avant lancement. Le registre habituel reste le défaut et les services existants n'ont pas été reconfigurés. Les anciennes missions gardent leur manifeste ; ne pas changer de backend au milieu d'une mission. Les essais réels utilisent EIDOLON_SANDBOX_INTEGRATION=1 ; un test ignoré sans cet environnement ne prouve aucune isolation. Bubblewrap observé : 0.12.0.

Le correctif déployé de maintenance est versionné séparément sur la VM, branche ops/maintenance-20261121, au-dessus de sa base ancienne. Ne pas avancer ce checkout aveuglément vers toute la branche de développement. La sauvegarde du fichier et de l'unité reste disponible.

Validation exécutée : **2 478 tests réussis, 24 ignorés, 1 349 sous-tests réussis** (308,31 s), puis **35 tests ciblés réussis** sur les fichiers finaux. Les deux avertissements concernent une archive synthétique à doublon et une dépréciation Pillow. Les 24 ignorés concernent des privilèges ou runtimes optionnels ; leurs raisons sont conservées dans le journal. La suite complète a collecté les tests avant l’ajout du cas passage admissible ; ce cas et l’environnement minimal du sandbox sont couverts par le lot ciblé final. Commit local de maintenance déployé : 60cbdba9590331b0bc5ee953edec8bc5aa95dfb4.

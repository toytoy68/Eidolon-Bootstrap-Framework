# G275 — intégration et contre-vérification de l’audit Claude

Codex/GPT, 16 octobre 2026. Demande toytoy 09 h 09 Europe/Paris.
Audit reçu : branche Claude `508db0a`, réponses C192/C193, Core `0480551`, Memory `76d6640`.
Le rapport de Claude et ses patches historiques restent inchangés ; ce document décrit notre intégration.

## Reproduction puis correction

Les sondes originales ont été exécutées avant application avec `--runxfail` :
**13 échecs, 5 réussites**, sur les assertions annoncées. Aucun xfail ne masque
ces défauts après intégration. Jeu retenu : 0011, 0008, 0009, 0012 ; 0007/0010 remplacés.

| Constat | Traitement G275 |
| --- | --- |
| F001, P1 rappel | Requête sur une ligne, 500 caractères, fin du message et limite de mot ; tour et historique inchangés. Aucun appel si la requête normalisée est vide. |
| F002, P1 bibliothèque | Extractions impossibles inventoriées avec diagnostic, retentées ; gros fichiers sans lecture ni SHA. Contre-revue : identité/taille/dates revérifiées, liens/fichiers spéciaux refusés. UI distingue absence d’extrait et absence du fichier. |
| F003, P2 GPU | Retrait des attentes sur erreur avec trois tentatives ; aucune libération ACTIVE/UNKNOWN. Retrait non confirmé signalé. Comptes complets et réserve GPU visibles même si liste tronquée. |
| F004, P2 calibration | À FRR égal, seuil le plus haut puis marge relative de 15 % côté authentiques, conformément aux décisions relayées par Claude. Sélection sur calibration seulement ; aucun seuil activé. |
| F005 | Documentation passages incrémentaux, mémorisation et maintenance alignée dans les deux dépôts. |
| F006 | Memory : 400 REMEMBER_INVALID_REQUEST, effects NONE, uniquement avant writer ; échec d’exécution : 503 REMEMBER_UNAVAILABLE, UNKNOWN. Reprise même commande testée après erreur survenue après écriture. Core reste prudent sur tout échec HTTP. |
| F007 | Import Any ajouté au contrôleur Memory historique. |
| F008/F010 | Bannière inexistante retirée, scripts existants reconnus, paramètres réseau inutilisés retirés. Dépendances PDF/média explicitement rattachées au runtime Core. Aucun installateur exécuté. |
| F009 | SIGTERM suit la fermeture contextuelle, comme Ctrl+C. Retrait des attentes créées par cette instance avant fermeture ; réservations héritées/actives conservées. |
| F011 | Limite de confiance Windows explicitée : empreinte du résident à l’inscription, binaire à chaque lancement ; même compte propriétaire du script/HKCU. Pas de protection promise contre ce compte, ni de changement du sous-paquet Windows. |
| F012 | Job CI dédié avec dépendances identité épinglées, vrai ONNX CPU sur modèle généré et audio synthétique, parité fbank ; aucun poids/personne réel. |

## Contre-vérification indépendante

`tests/test_audit_counterreview_g275.py` : 12 scénarios (avec paramétrages), incluant
remplacement/réécriture de même taille et lien physique sur gros fichiers pendant
scan, ancien schéma consulté sans écriture, reprise après document vide, fichier
spécial, erreur après admission GPU, retrait non confirmé, inventaire tronqué,
100 jeux de calibration comparés à une énumération indépendante, indépendance du
jeu de validation, et processus HTTP réellement arrêté par SIGTERM.

Le scénario SIGTERM conserve une réservation ACTIVE et une attente héritée, annule
seulement l’attente créée par l’instance et constate l’exécution de server_close.
Il ne simule pas systemd, panne machine ou moteur distant. Le scénario de verrou
SQLite transitoire de Claude est conservé.

Memory ajoute cinq cas : quatre refus pré-writer et un scénario HTTP erreur après
écriture → effet UNKNOWN → reprise avec même reçu, un seul souvenir.

Résultat ciblé Core : **69 réussis**, incluant sondes Claude, G273, contre-revue et
HTTP disponibilité. Memory ciblé : **7 réussis** (nouveaux cas + deux existants),
ainsi que 38 tests de pont réussis et une exclusion selon l’UID dans une campagne distincte.
Ces comptes se recouvrent. Les preuves CI finales sont consolidées dans le
[rapport unique](../weekend/2026-10-17/RAPPORT-UNIQUE.md).

Deux erreurs d’édition ont été détectées pendant les essais locaux et corrigées :
un appel de constructeur dans une nouvelle sonde et une substitution trop large
dans cancel_waiting. Les assertions de contrôle sont conservées ; aucune campagne
rouge n’est présentée comme réussie.

## Points restant à mesurer

- H1 : quota CPU fixe 10 % retiré du brouillon ; conserver Nice=10 et mesurer le premier scan avant de fixer un quota. Bornes 30 s/fichiers/octets inchangées.
- H2 : la synchronisation des passages conserve son verrou canonique pendant les embeddings. Le risque de rappel retardé reste à mesurer ; pas de changement transactionnel non qualifié. La période de maintenance et l’arrêt à reprise d’activité restent applicables.
- H3 : arrêt propre testé sur Linux ; SIGKILL, panne et stockage durablement bloqué exigent toujours inventaire/revue. Les réservations incertaines ne sont pas expirées automatiquement.
- H4 : marge de 15 % relative à l’écart de calibration ; pertinence à mesurer sur captures consenties, aucune garantie de taux d’erreur réel.

Les zones non examinées en profondeur par Claude restent identifiées dans son
rapport. Cet audit ne certifie pas l’absence de défaut sur tout Eidolon.
Les 50 contrôles PC/VM restent NOT_RUN. Aucun déploiement, compte, purge ou fusion main.

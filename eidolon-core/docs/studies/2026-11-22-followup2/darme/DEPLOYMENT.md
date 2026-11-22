# Préparation du déploiement Darme — 22/11/2026

Eidolon Core Technologies (ECT) — Local AI • Modular • Reliable • Reproducible

État : paquet préparé et vérifié, pas activé en production. Le registre par défaut du Runtime reste inchangé.

## Contenu vérifié

146 fichiers Python issus du code de la PR #20, archive et manifeste SHA-256, précontrôle en lecture seule et unité systemd. L’archive locale est `executor-source.tar.gz` ; elle doit être comparée au manifeste publié avant toute extraction. Le compte de service proposé `eidolon-darme-exec` est distinct du compte Darme existant et du compte appelant. Sur X399, le précontrôle avec toytoy confirme UID 1000 et bubblewrap disponible ; le service actuel eidolon-core-api.service confirme User=toytoy et Group=toytoy. Le compte doit être revérifié au moment de la bascule.

## Procédure de mise en service préparée

1. Identifier le compte effectif du processus Core à raccorder. Exécuter `python3 preflight.py --core-user COMPTE`. Refuser UID 0 et une identité commune avec le service.
2. Créer un compte système dédié `eidolon-darme-exec`, sans shell de connexion, et le groupe de socket `eidolon-executor`. Ajouter uniquement le compte Core retenu à ce groupe ; une nouvelle session de service sera nécessaire pour prendre en compte le groupe.
3. Vérifier l’archive contre le manifeste depuis un emplacement contrôlé par root. Installer les sources sous `/opt/eidolon-core-executor/48e0bb4/src`, propriétaires root, fichiers 0644, répertoires 0755, sans droit d’écriture accordé à Core ou à l’exécuteur.
4. Créer `/etc/eidolon/darme-executor.env`, root:root 0600, contenant `EIDOLON_CORE_UID=UID_VERIFIE`. Installer l’unité jointe sous `/etc/systemd/system/eidolon-darme-executor.service`. Vérifier avec `systemd-analyze verify`, puis recharger systemd.
5. Démarrer le service seul ; vérifier son UID, ses capacités nulles, le socket 0660 et son répertoire 0750 non modifiable par Core. Relancer les six tests de comptes distincts avec les chemins et UID de la cible, plus refus d’un troisième UID et refus après arrêt du service.
6. Raccorder explicitement une instance de test Runtime à `remote_registry(socket_path, service_uid)` avant toute bascule du processus habituel. Une réponse valide doit produire un reçu VERIFIED ; une interruption incertaine doit rester REVIEW_REQUIRED / UNKNOWN_EFFECT. Aucun repli automatique.
7. Activer au démarrage seulement après cette recette sur la cible. Conserver le paquet précédent et la configuration du processus appelant.

## Retour arrière

Arrêter l’instance Runtime de recette et le service nouvellement installé ; restaurer explicitement le registre précédent dans la configuration de l’opérateur. Ne pas convertir des appels incertains en réussites et ne pas supprimer leurs reçus. Le désactivation du service échoue volontairement sans repli pour un client encore raccordé. Conserver l’archive et les journaux avant nettoyage éventuel des comptes/groupes.

## Revue du code

Relecture de la frontière socket, authentification mutuelle SO_PEERCRED, bornes UTF-8 et de trame, échéance de lecture totale, refus des champs supplémentaires, validation indépendante, exécution bubblewrap et vérification du résultat. Les protections ne reposent pas sur le JSON généré par un LLM. Aucun nouveau défaut bloquant identifié dans ce périmètre restreint ; cette revue est réalisée par Codex, pas par un auditeur indépendant.

La connexion autorisée peut encore occuper une file bornée et provoquer un déni de service : ce mécanisme ne protège pas la disponibilité contre un compte Core hostile. Il ne qualifie que `text.stats`, sans effet externe. Les commandes moteurs, shell, accès réseau et modifications système restent exclus. Une simple installation de l’unité ne raccorderait pas automatiquement le Runtime.

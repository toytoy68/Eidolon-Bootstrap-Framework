# G184 — Validation du registre préparatoire

Auteur : Codex/GPT. Date : 12/10/2026, Europe/Paris.
Base de départ : `6dcd52243b3915dc3c3245c16a65299141680d8a`.
Environnement : conteneur Linux de développement, Python 3.12.14 ; données fictives.
Aucun appel VM, modèle réel, capteur, compte ou corpus personnel.

## Commande exécutée sur le code livré

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src python3 -X dev -m unittest tests.test_profile_plan tests.test_profile_registry tests.test_personality tests.test_conversation_store tests.test_build_beta_bundle -q
```

```text
Ran 111 tests in 5.569s
OK
```

Composition : 13 tests de plan (12 existants + frontières des identifiants),
27 nouveaux tests du registre, 61 tests personnalité/conversation et 10 tests
du constructeur de paquets. Aucun ignoré ni avertissement dans cette exécution.
La suite Core complète n'a pas été relancée pour ce module isolé du Runtime.

## Vérifications qui portent sur des effets réels

- Deux processus concurrents tentent deux plans différents : une publication,
  l'autre opération refusée avec BUSY ou CONFLICT ; aucun mélange.
- Arrêt de processus avec exit 47 avant renommage : aucun instantané partiel,
  résidu privé conservé, reprise refusée avec PENDING.
- Arrêt de processus après renommage : instantané complet, import identique
  confirmé sans réécriture. Ces essais ne simulent pas une coupure électrique.
- Injection d'une erreur au fsync du fichier : aucune publication.
- Injection d'une erreur au fsync du répertoire : COMMIT_UNCERTAIN, inspection
  puis import identique confirmant les synchronisations.
- Écritures courtes complétées, erreur d'écriture nettoyée sans toucher au
  fichier opérateur témoin, permissions 0600 et umask conservé.
- Liens symboliques (fichier et composants), lien physique, FIFO, source trop
  grande, répertoires/fichiers non privés, JSON ambigu et instantané corrompu
  refusés ; ni écrasement ni réparation implicite.
- Simulation et inspection sans création de verrou ; diagnostics JSON sans
  identité, chemin ou empreinte du plan.

## Limites et contre-revue

[Contrat complet](PROFILE-REGISTRY-G184.md). Stockage uniquement préparatoire :
aucune authentification, session, séparation mémoire active, biométrie ou
sauvegarde privée intégrée. VM et fichier réel des profils non vérifiés.
Le propriétaire/root restent de confiance, les autres écrivains doivent
respecter le verrou. La durabilité sur coupure électrique n'est pas qualifiée.
Contre-revue indépendante demandée à Claude dans G185.

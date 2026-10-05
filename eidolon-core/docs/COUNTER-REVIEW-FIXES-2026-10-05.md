# Suite de C-REV-002 — 05/10/2026

Auteur : Codex/GPT. Base : `2474c7cf5a30b4a0eb3d563d61992acaf930976f`.
La contre-revue de Claude, patch `9a368e7796f8566bfdf023674205b454a87693a1`
relayé par toytoy, a été publiée dans `566d39cbdf6b3bf186040f12b883da7db30ee99b`.
Les douze fichiers du patch ont été importés à l'identique, avec attribution et
co-auteur au message de commit. Les résultats ci-dessous concernent l'arbre
corrigé du commit introduisant ce bilan, sous Python 3.12.14/Linux.

## Constats et corrections

[Sondes originales exécutées avant correction](validation/2026-10-05/codex-c-rev-002/before.txt) :
N-01 confirmé (erreur d'outil sans issue de reprise) ; N-02 confirmé (deux effets
après la fin de l'orphelin). Le résidu de profondeur N-04 est aussi reproduit,
à 9 993 niveaux sur cet interpréteur, ainsi que ConnectionResetError (N-05).
Le script et les observations de Claude sont conservés sans réécriture.

| Point | Traitement | Limite |
| --- | --- | --- |
| N-01 | Séparation `error_receipt` / `late_receipt` ; une erreur n'interdit plus la décision humaine `no-effect` ; tentative précédente archivée | Une exception ne prouve jamais l'absence d'effet ; aucune nouvelle tentative automatique |
| N-02 | `lease-v2` : autorisation inscrite dans le verrou avant entrée dans l'outil ; reçu atomique conservé par appel/tentative dans l'état Core ; lecture sous verrou lors de la réconciliation | Processus vivant toujours bloquant ; reçu positif interdit une nouvelle exécution même avec confirmation humaine |
| N-03 | Permission non envoyée et enfant arrêté : annulation directe ou blocage reprenable, tentative non exécutée tracée | Mort brutale du parent ou envoi ambigu restent en revue |
| N-04 | Profondeur du plan bornée à 32 conteneurs avant parsing, en ignorant les crochets dans les chaînes | Pas une limite de coût globale du fournisseur Python |
| N-05 | EOF/OSError de la poignée de main traités sans trace d'exception de connexion | Les erreurs disque conservent leur diagnostic d'échec/effet inconnu |
| N-06 | `receipt_origin` dans les preuves finales ; SHA-256 recalculé avant succès, y compris dans le store | Cohérence locale, pas authenticité face à un acteur modifiant aussi les empreintes |
| N-07 | `use-receipt` sélectionne la valeur exacte conservée ; une sortie humaine contradictoire est refusée avant adoption | Le vérificateur reste obligatoire ; aucune source mémoire n'est promue en fait confirmé |
| N-08 | Délais des tests concernés portés de 0,5/1 s à 2 s ; annulation pendant outil synchronisée sur son entrée réelle | Deux tests concernés revalidés sous charge ciblée, pas une garantie sous saturation arbitraire ni une recette VM |

Le nouveau reçu persistant remplace le transit temporaire **pour l'exécution
outil seulement**. Rappel/modèle/vérification gardent des reçus temporaires.
L'écriture du marqueur et du reçu est synchronisée ; aucun essai de coupure
électrique n'a été réalisé. Le dossier d'état entier forme l'unité de conservation.

## Règles de réconciliation

- Tant que l'enfant tient le verrou : aucune décision permettant une reprise.
- Reçu positif présent : `no-effect` refusé, même avec `--confirm-no-effect`.
  `use-receipt` prépare une vérification ; `abandon` clôt avec incertitude.
- Reçu d'erreur : `no-effect` reste une décision humaine explicite après examen,
  conservée avec acteur/motif. L'erreur et l'ancienne tentative ne sont pas effacées.
- Aucun reçu, autorisation connue ou inconnue : `no-effect` exige une confirmation
  distincte `--confirm-no-effect` après investigation. Sans preuve d'absence
  d'effet, rester en revue ou abandonner. La confirmation ne vaut pas preuve
  technique et ne permet pas d'ignorer un reçu positif.
- Avec `lease-v2`, verrou disponible et marqueur vide : l'outil n'est pas entré
  dans le fournisseur selon le protocole local ; réconciliation explicite possible.
- Un ancien `lease-v1` n'ayant pas marqué l'autorisation reste « inconnu ».
  Sans aucun protocole de verrou, les restrictions anciennes restent applicables.
- Marqueur partiel ou reçu illisible : refus de reprise ; abandon reste possible.

Les hypothèses restent celles d'écrivains coopératifs et de fichiers locaux
intacts. Ne pas supprimer les verrous/reçus, déplacer un état actif ou restaurer
SQLite seul. Pas de contrôle des descendants, pas d'attestation du service
externe, pas d'authentification de `actor`, pas de promesse exactement une fois.

## Validation exécutée par Codex

```sh
# Depuis eidolon-core/
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  python -m unittest tests.test_core tests.test_review_regressions tests.test_counter_review -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  python docs/validation/2026-10-05/codex-c-rev-002/load_check.py
```

- **58 tests Core réussis**, 44,408 s : [journal complet](validation/2026-10-05/codex-c-rev-002/core-tests.txt).
  Les 11 nouveaux tests couvrent erreur/reprise/historique, format ancien,
  orphelin terminé, reçu manquant ou corrompu, annulation avant autorisation,
  panne de persistance du lancement, profondeur, connexion coupée, origine et
  cohérence des preuves, réconciliation CLI sans recopier le reçu.
- **2 tests ciblés réussis sous charge**, 9,826 s : [journal](validation/2026-10-05/codex-c-rev-002/targeted-load.txt).
  Affinité restreinte à deux CPU pour le pilote et ses enfants, six processus
  concurrents de calcul, nettoyés en fin d'essai. Ce sont les deux méthodes
  qui échouaient chez Claude ; la suite entière n'a pas été relancée sous charge.
- **6 intégrations Memory Engine réussies**, 1,043 s : [journal](validation/2026-10-05/codex-c-rev-002/memory-integration.txt).
  Même copie isolée au commit `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, corpus
  synthétiques temporaires, services coordonnés, dépôt moteur propre. Ce n'est
  pas une revalidation de la dernière tête distante du moteur.
- **Démonstration CLI humaine réussie** : [sortie](validation/2026-10-05/codex-c-rev-002/demo-human.txt),
  70 caractères et 72 octets vérifiés ; source UNVERIFIED conservée.

Les 47 tests sous Python 3.13.16 de Claude concernent `2474c7c`, avant ce lot.
Aucune nouvelle validation Python 3.13, VM, Windows, NAS, Internet ou modèle réel.

## Suite

C-001 reste la prochaine tranche fonctionnelle : critères de mission indépendants
et cas T-1/T-3/T-4/A-2 proposés par Claude. Les contrats métier A–D ne sont pas
implémentés par cette correction. La contre-revue ciblée C-REV-003 est préparée
pour les traces par tentative et la confirmation distincte, sans supposer de
réponse ou de session automatique.

Avant de gros connecteurs : magasin d'artefacts, budgets, rétention/nettoyage
coordonnés des reçus et verrous restent à faire. `attempt_history` croît avec
les reprises explicites ; pas de budget global ni de purge automatique livrés.

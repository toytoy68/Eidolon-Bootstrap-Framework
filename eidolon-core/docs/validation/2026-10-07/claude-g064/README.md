# C-TASK-G064 — Contre-revue du lecteur d'archives C-028 et de l'initialisation C-029

Claude, 08/10/2026. Données synthétiques et dossiers temporaires uniquement.
Aucune source Core modifiée.

- C-028 : `e0365f2`. C-029 : `896bb0e` (premier commit contenant
  `tests/test_research_initialization.py`). Arbre `src` examiné : `6f04eeb`,
  identique en `56aa33f`.
- Rejoué sur la dernière branche `6f46219`. `research_archive.py` y ajoute seulement
  un délai coopératif. Résultats identiques, sauf le nombre de `ARCHIVE_INDEX_BUSY`
  en L5 qui dépend de l'ordonnancement.

```sh
python3 probes_g064.py <src figé 896bb0e> <src figé e0365f2>   # → probes.txt
```

Méthode :

- Les exports sont produits par le prototype de rotation G063 sur ces sources.
- Le lecteur est appelé par sa CLI dans un sous-processus.
- Chaque refus vérifie :
  - code 2 ;
  - stdout vide ;
  - aucune trace d'erreur Python ;
  - aucun texte privé ni chemin ;
  - empreinte du dossier identique (noms, modes, tailles, inodes, mtime, contenus).
- Les coupures sont des `os._exit` en sous-processus. La coupure de recherche tue
  à la fois le worker « spawn » et le runtime, après l'INTENT de garde
  (`sitecustomize` temporaire).

## Lecteur (R) — rien à corriger

- Les exports v2 et v1 (sans `released_operations`) sont acceptés.
- Les drapeaux restent faux : `authenticity_verified`, `live_journal_checked`,
  `committed_status_known`, `authorizes_execution`.
- 45 cas hostiles sont refusés avec le code attendu. Aucun ne produit de sortie
  partielle ni de mutation.
  - JSON ambigu : clé dupliquée (y compris dans `body`), NaN, 2^53, 1.0, `true`,
    5000 chiffres, BOM, octet non UTF-8, imbrication 100 000, surrogate isolé.
  - Contenu altéré : texte nettoyé modifié ou retiré, événement final ≠ corps,
    un seul événement, séquences inversées, INTENT seule, `removed_ids` faux,
    `released_operations` vide ou en trop.
  - Chaîne incomplète : export du milieu ou premier export retiré, renommage,
    export d'une autre garde, recherche répétée même après rechaînage.
  - Fichiers spéciaux : lien sur l'export ou le dossier, FIFO (sans blocage),
    sous-dossier, droits 0644/0755, `.partial`, nom invalide.
  - Volume : 2 049 entrées, export creux de 16 Mio + 1, total et nombre bornés
    (bornes abaissées en processus), argument NUL.
  - Courses : même contenu sous un nouvel inode, ajout d'un export, `utime`,
    allongement pendant la lecture → `ARCHIVE_CHANGED_DURING_READ`.
- Cohérence ≠ authenticité (comportement documenté, reproduit) :
  - la troncature du dernier export est acceptée ;
  - deux réécritures cohérentes sont acceptées : horodatage modifié, recherche
    retirée puis chaîne recalculée.
  - Le lecteur ne peut détecter ni l'une ni l'autre sans ancre externe.

## liste.md (L)

- Création :
  - fichier en 0600, avec en-tête, appartenant à l'utilisateur ;
  - liens limités aux trois noms d'export ;
  - aucun texte de requête, adresse, `operation_id` ni `guard_id` ;
  - exports inchangés.
- Idempotence : second `index` → `index_changed=false`. Dossier identique,
  inode et mtime compris.
- Refus sans mutation :
  - liste manuscrite, en 0644, en lien symbolique (cible externe intacte) ou en FIFO ;
  - verrou en 0644, verrou en lien symbolique (cible non créée) ;
  - verrou détenu → `ARCHIVE_INDEX_BUSY`. `inspect` reste possible pendant ce temps.
- Concurrence : 8 `index` simultanés donnent des `OK` ou `BUSY`, et une liste finale exacte.
- Coupure avant publication :
  - l'ancienne liste est gardée (ou absente si elle n'existait pas) ;
  - un `.liste-*.tmp` en 0600 reste (documenté) ;
  - l'`index` et l'`inspect` suivants réussissent.
- Coupure après publication : la nouvelle liste est en place, sans temporaire.
- **G064-1 (faible)** — fenêtre entre contrôle et remplacement :
  - un écrivain qui ignore le verrou et écrit `liste.md` entre la vérification de
    signature et `os.replace` voit son texte écrasé ;
  - le cas reproduit est un manuscrit sans marqueur ;
  - correctif minimal proposé : le documenter. Un vrai échange atomique
    (`renameat2(RENAME_EXCHANGE)`, puis contrôle et retour) est réservé à Linux.
- **G064-2 (faible)** — une liste périmée garde son affirmation :
  - après altération d'un export, `index` refuse ;
  - l'ancienne `liste.md` reste et affiche toujours « Cohérence vérifiée » ;
  - proposition : écrire « Cohérence vérifiée à la génération » et ajouter la
    date de génération.
- Le marqueur n'authentifie pas : un manuscrit qui commence par l'en-tête est
  remplacé. C'est documenté.

## Initialisation C-029 (I)

- Coupure pendant la recherche (INTENT enregistrée), puis éléments retirés :
  - dossier entier → `RESEARCH_PAUSES_MISSING` ;
  - garde → `RESEARCH_GUARD_NOT_FOUND` ;
  - verrou → `RESEARCH_GUARD_UNAVAILABLE` ;
  - pauses → `RESEARCH_PAUSES_MISSING`.
- Dans chaque cas rien n'est créé. Après restauration, l'INTENT est conservée et la
  reprise donne `REVIEW_REQUIRED / UNKNOWN_EFFECT`, sans relance.
- Garde seule restaurée *avant* l'INTENT (même identité) : elle est acceptée, mais
  la reprise reste `REVIEW_REQUIRED` et aucune recherche n'est lancée. L'absence
  d'INTENT n'entraîne aucune relance.
- Restauration conjointe Store + garde + pauses : acceptée (hors garantie,
  documenté).
- **G064-3 (moyen)** — l'identité des pauses n'est pas liée :
  - une pause `ACCESS_DENIED` active est créée par le scénario bloqué ;
  - on remplace `pauses.sqlite3` par une base vide valide ;
  - le runtime se construit et la pause a disparu, sans levée tracée.
  - Contrairement à la garde, rien ne lie cette base au Store.
  - Correctif minimal proposé : une ligne d'identité dans la base des pauses, liée
    dans `sync_metadata` comme `research_fixture_guard_id`, avec refus
    `RESEARCH_PAUSES_CHANGED`. Les bases existantes sans identité seraient adoptées
    une fois.
  - Un retour en arrière d'une copie de même identité resterait hors détection.
- Initialisations coupées :
  - dossier de garde seul ou garde sans pauses → refus durable
    `RESEARCH_PAUSES_MISSING`, aucun ajout ;
  - coupure après construction mais avant la liaison → adoption à la réouverture.
  - Il n'existe pas de commande de réparation : l'opérateur doit retirer le
    dossier. À indiquer dans le message d'erreur ou le guide.
- Six processus initialisent le même Store neuf : une seule identité et un seul journal.
- Missions C-021 :
  - adoption avec missions identiques à l'octet ;
  - identités contradictoires → `RESEARCH_BACKEND_CHANGED`, sans liaison ni
    réécriture.
- **G064-4 (faible)** — erreurs SQLite brutes à la construction :
  - Store tenu par un autre écrivain → `sqlite3.OperationalError: database is
    locked` après 5 s ;
  - délai du balayage historique dépassé (20 001 missions, horloge simulée) →
    `OperationalError: interrupted`.
  - La CLI les ramène à `STORAGE_UNAVAILABLE`, mais l'API Python les laisse
    passer bruts.
  - Proposition : un code stable, par exemple `RESEARCH_BINDING_BUSY` ou
    `RESEARCH_BINDING_SCAN_TIMEOUT`.
- I10 : sous un écrivain actif, `show` échoue aussi en profil `text` et dans la
  base e0365f2. Ce n'est donc pas une régression de C-029.

## Limites

- POSIX local uniquement.
- Le stockage réel, les coupures électriques, Windows et les VM ne sont pas éprouvés.
- Exports de 257 recherches non construits ; seule la borne en a été lue.
- Aucune authentification n'est revendiquée.

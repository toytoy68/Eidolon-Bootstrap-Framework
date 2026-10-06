# Suivi G024/G025 — disponibilité, comptage et découverte

Auteur : Codex/GPT, 06/10/2026, Europe/Paris.
Base : f18053a, après intégration G022–G025 de Claude (9147f82).
Sources : research.py, research_pauses.py ; [empreintes](source-hashes.json),
[environnement](environment.json). Ni raccordement HTML ni fournisseur réel.

## Changements

- C-G024-1 : 256 pauses **actives**, les lignes RELEASED conservent identité,
  révision et audit. Réobservation = nouvelle place + révision suivante ; pas
  de purge ni d'ancienne validation redevenue valable.
- C-G024-2 : refus connu du précontrôle de capacité répété avec la même cause,
  sans prétendre qu'une écriture aurait été tentée. Une panne de stockage ou
  une observation perdue après échange garde le blocage prudent de l'instance.
- F-W07 partiel : corps SHA-256 identiques comptés une fois, reçus/provenance
  gardés, DUPLICATE_CONTENT et duplicate_of. Comparaison exacte, sans affirmer
  l'indépendance éditoriale. URL de requête/cache jamais amputées.
- F-W14/W15 : discovery_status précise HITS_FOUND/EMPTY/UNAVAILABLE/INCOMPLETE,
  séparément du statut de lecture existant.

## Vérification avant/après

18 nouvelles méthodes dans tests/test_research_availability.py. Sur sources
f18053a figées : [4 échecs et 9 erreurs de cas](before.txt) ; les comparateurs
positifs restent présents. Après correction : [97 tests ciblés réussis](targeted.txt),
incluant neuf tests G023 de Claude, pauses, budgets et recherche existante.

Les anciennes fixtures de capacité comptaient volontairement RELEASED ; elles
sont actualisées au nouveau contrat avec de vraies pauses ACTIVE. L'essai
redirection garde une seule place active et refuse le second saut à deux origines.
Un autre test remplit la dernière place pendant l'appel fournisseur pour vérifier
que l'origine est bloquée avant sa lecture. Pas de suppression des protections.
Deux anciennes fixtures de test_research_disclosure utilisaient le même corps
pour deux pages supposées distinctes ; elles ont désormais deux textes différents
pour garder leur objet initial (cache interrompu et identifiants d'URL distincts).
Les assertions restent inchangées. Le premier passage complet a exposé ces deux
attentes incompatibles ; la validation finale suit leur mise à jour.

Deux processus démarrés ensemble pour la dernière place : un commit, un refus,
un seul audit. Révisions après RELEASED, corruption d'une ligne historique,
rollback de deux périmètres et garde après vraie erreur SQLite couverts.

[Sondes G024 inchangées rejouées](g024-current.txt) : section 2b, 256 lignes dont
2 levées, accès au nouveau fournisseur et à la nouvelle origine redevenu possible.
Les libellés historiques du script parlent encore de nombre total de lignes ;
ce sont les sorties observées qui font foi, pas ces commentaires.

[Cas W14/W15 du corpus G025](g025-selected.json) : indisponible et vide distincts.
W07 original garde deux HTML non pris en charge ; son oracle « une seule requête »
n'est PAS satisfait par cette correction. Le corps texte identique est éprouvé
par les nouvelles régressions et la démo. Aucun ancien oracle réécrit.

[Démo JSON](demo.json) et [humaine](demo-human.txt) exécutées : deux URL/deux reçus,
un seul contenu, cache normal, table à 256 ACTIVE, deux refus cohérents, levée
explicite et nouvelle recherche sans reconstruire le coordinateur.

Suite complète finale : **493 tests découverts, 487 réussis, six intégrations
Memory Engine sautées**, 110,153 s. [Journal](full-suite.txt).

## Reproduire

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m unittest tests.test_research_availability tests.test_research tests.test_research_pauses tests.test_review_followup tests.test_abandon_verification -v
PYTHONPATH=src:. python -m unittest discover -s tests -v
PYTHONPATH=src:. python -m examples.research_availability_demo --format human
PYTHONPATH=src:. python docs/validation/2026-10-06/claude-g024/probes_g024.py
PYTHONPATH=src:. python docs/validation/2026-10-06/codex-web-availability/g025_selected.py
```

## Réserves

L'historique et le journal peuvent grandir ; décompte validé linéaire, pas de
quota disque ni de purge. Ce contrôle reste un précontrôle sans réservation
entre requêtes. Crash après réponse/avant pause non résolu. Requêtes sortantes
encore verbatim vers les adaptateurs de confiance ; F-W20 reste ouvert.
Pas de garantie sur les contenus presque identiques, HTML ou vérité des textes.
G022 : rapport lu, tests de restauration dans la suite ; sondes longues de
Claude non intégralement reproduites. G023 : tests reproduits, aucun service réel.
VM, Windows, GPU, moteur mémoire réel et Internet hors validation.

## Publication

Un push des commits d'intégration et de la file a été refusé par le contrôle
automatique d'approbation : destination GitHub jugée non vérifiée/autorisation
non reconnue pour ce transfert. Aucun contournement tenté. Travail conservé
sur la branche locale feat/eidolon-core-v0.1 ; confirmation utilisateur nécessaire
avant nouvel essai. Les nouvelles fiches ne sont donc pas annoncées accessibles
à Claude sur le dépôt distant.

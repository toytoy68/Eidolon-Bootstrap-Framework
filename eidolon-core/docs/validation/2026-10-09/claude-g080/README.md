# G080 — Contre-revue des bornes de rotation C-046

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G080.
Base examinée : `09bfd55` (branche Claude, qui contient C-046 de Codex,
`0b439f0`). Fichiers examinés **sans modification** :
[rotation.py](../../../proposals/2026-10-07-research-retention/rotation.py) (producteur, prototype v5)
et [research_archive.py](../../../../src/eidolon_core/research_archive.py) (lecteur Core).

## Méthode

Sondes indépendantes : [probes_g080.py](probes_g080.py). Elles réutilisent le
journal synthétique de Codex (`probes_g057.build` : ResearchGuard inchangé,
7 recherches, dont une liée à une mission et une résolue).

Pour chaque borne, la sonde vérifie le producteur à la **valeur exacte** et à
**une unité au-delà**. Elle vérifie aussi que :

- le lecteur Core relit ce que le producteur accepte ;
- chaque refus a lieu **avant toute publication** : journal et dossier
  d'archives identiques octet pour octet.

La taille de l'export suivant est mesurée sur une **copie** du journal.

```sh
G062_SRC="$PWD/src" python3 -m unittest discover -s docs/validation/2026-10-09/claude-g080 -p 'probes_*.py' -v
```

## Résultats exécutés

- Sondes G080 : **9/9** ([probes-g080.txt](probes-g080.txt)).
- Suite de Codex rejouée sur la même base : 37/37.

| Sonde | Résultat |
| --- | --- |
| Taille unitaire = limite | publiée et relue par le lecteur |
| Taille unitaire = limite − 1 | `ARCHIVE_TOO_LARGE` avant publication, rien de modifié |
| Volume cumulé = limite | publié ; le lecteur accepte aussi à l'égalité |
| Volume cumulé = limite − 1 | `ARCHIVE_TOTAL_LIMIT` avant publication |
| Nombre = limite (3) | 3 exports relus ; le 4ᵉ refusé (`TOO_MANY_EXPORTS`) sans effet |
| Entrées du dossier | refus conservateur d'**une** entrée (voir écart E1) |
| Nom refusé seulement par le lecteur (`research-archive-notes.txt`) | refus `INVALID_ARCHIVE_FILENAME` avant publication |
| Horodatage de type `Date.now()` (1 760 000 000 000) | accepté et relu |
| Horloge qui recule (1 après 1,76e12) | accepté et relu (voir écart E2) |
| `2**53`, `2.0**53`, `False`, `None` | `INVALID_CLOCK`, rien de modifié |
| Export orphelin (coupure après publication) | `verify` et `rotate` refusent (`UNCOMMITTED_EXPORT`) ; le lecteur le relit avec `committed_status_known: false` |
| Orphelin, puis nouvelle recherche dans le journal, puis reprise | seules les lignes exportées sont retirées ; la nouvelle recherche reste |
| Orphelin au-delà de la limite unitaire | reprise refusée, orphelin conservé ; reprise acceptée ensuite dans la borne |
| Retrait | lignes retirées = runs de l'export, à l'identique ; reste du journal identique ; exportés + restants = journal d'origine |

## Écarts constatés

Aucun défaut bloquant trouvé : aucun retrait sans export relisible, aucune
perte de ligne.

- **E1, marge du dossier** (connu, conservateur). Le producteur réserve deux
  entrées (partiel et final), alors que l'état publié n'en ajoute qu'une. À
  `MAX_DIRECTORY_ENTRIES` − 1 entrées présentes, il refuse un état que le
  lecteur accepterait. Sans risque, rien n'est retiré. À dire dans la
  documentation opérateur.
- **E2, horodatage non monotone** (observation). Ni le producteur ni le
  lecteur n'exigent que `created_at_ms` croisse d'un export au suivant. La
  chaîne d'empreintes fixe l'ordre, pas l'heure. Si l'interface affiche ces
  dates comme une chronologie, il faudrait le dire, ou refuser un recul.
  Décision à Codex.
- **E3, reprise bloquée par un changement** (connu, documenté par Codex). Si
  une ligne exportée change entre publication et commit (`JOURNAL_CHANGED`),
  l'orphelin ne correspond plus. La reprise est alors refusée
  (`EXPORT_DOES_NOT_MATCH_JOURNAL`) et toute rotation reste bloquée jusqu'à
  une revue manuelle. C'est sûr, mais il manque une procédure opérateur
  écrite (que faire de l'orphelin).

## Limites

- Les bornes sont abaissées par `patch` pour rester rapides. La limite réelle
  de 1 000 exports est couverte par le banc `catalog-capacity` de Codex, que
  je n'ai pas rejoué.
- Conteneur seulement : pas de disque réel plein, pas de NAS, pas de coupure
  électrique.
- Prototype hors runtime : le schéma 3 est toujours refusé par la garde Core.
  Aucune activation n'est proposée ici.

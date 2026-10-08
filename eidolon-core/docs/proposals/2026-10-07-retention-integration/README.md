# Intégration de la rotation — banc de compatibilité et qualification (C-TASK-G068)

Claude, 08/10/2026. Statut : **PROPOSITION, rien d'activé**.
Base Core : `1e9d8b8` (lecteur C-028/C-030 courant, `src` figé).

- Producteur : le prototype isolé [rotation.py v4](../2026-10-07-research-retention/README.md).
- Lecteur : `eidolon_core.research_archive`, **importé** (aucun second lecteur).
- `research_guard`, `query_history` et `research_archive` ne sont pas modifiés.
- Aucun vrai journal n'est touché.

```sh
python3 bench_g068.py <src figé>    # code 1 si un contrôle échoue → bench.txt
```

## Résultats ([bench.txt](bench.txt) : 0 échec)

| Contrôle | Résultat |
| --- | --- |
| 123 recherches, cible 100 | 100 actives, 23 archivées en 0,06 s. Le lecteur Core accepte la chaîne. Conservation octet pour octet ; second appel idempotent ; `liste.md` générée |
| Missions non terminales (les plus anciennes) | restent actives ; la mission déclarée terminale est archivée et listée dans `released_operations` |
| 105 recherches de missions non terminales | aucun retrait, aucun export ; dépassement signalé `above_target=5` |
| Journal en WAL | rotation lue par Core et conservation ; le journal reste WAL. La garde Core actuelle refuse le schéma 3 (`UNSUPPORTED_RESEARCH_GUARD`), sans usage silencieux |
| Coupure à chacune des 4 frontières | trois reprises successives ; état final lu par Core et conservation. Juste après une coupure en écriture partielle, Core refuse (`PARTIAL_EXPORT_PRESENT`) jusqu'à la reprise |
| Retour au schéma 2 depuis les exports | journal reconstruit identique à l'origine, ligne pour ligne. La garde Core actuelle le rouvre |

## Écarts producteur / lecteur à corriger avant activation

| Limite | Producteur (prototype) | Lecteur Core | Conséquence |
| --- | --- | --- | --- |
| Octets par export | 32 Mio | 16 Mio | un export de 16 à 32 Mio serait publié puis refusé en lecture |
| Nombre d'exports | 4 096 | 1 000 | au 1 001ᵉ export, tout le catalogue devient illisible (reproduit avec la borne lecteur abaissée à 3) |
| Octets cumulés | aucune | 64 Mio | même effet, sur le volume total |
| Horodatage | `clock_ms` non contrôlé | ≤ 2^53 − 1 | export à 2^53 accepté par le producteur, refusé par le lecteur (reproduit) |
| Recherches par export | 256 | 256 | aligné |

Mesures :

- Une recherche synthétique pèse environ 2,3 Ko dans un export. 256 recherches
  restent donc très loin de 16 Mio.
- Le risque réaliste est le **nombre** d'exports : une rotation après chaque
  recherche produit un export d'une seule recherche, soit environ 1 000 recherches
  avant le blocage du lecteur.

Corrections proposées, à intégrer par Codex :

1. Le producteur importe les bornes du lecteur (`MAX_ARCHIVE_BYTES`,
   `MAX_ARCHIVES`, `MAX_TOTAL_BYTES`). Il refuse **avant** publication tout export
   que le lecteur refuserait.
2. Valider `clock_ms` entre 0 et 2^53 − 1.
3. Archiver par lots : déclencher seulement si l'excédent atteint un seuil (par
   exemple 25) ou si un âge est dépassé. Cela laisse environ 25 000 recherches
   avant la borne des 1 000 exports. Au-delà, une lecture segmentée avec ancrage
   est à concevoir (déjà signalée par C-028).

## Migration schéma 2 → 3, réversible avant tout retrait définitif

1. Créer la table `archives` dans la même transaction que le premier retrait.
   Avant tout retrait, la base reste en schéma 2.
2. Le schéma 3 est refusé par la garde actuelle. Une ancienne version ne peut donc
   pas réutiliser silencieusement un journal amputé.
3. Retour arrière, prouvé par le banc (section R) :
   - réinsérer les lignes des exports validés par le lecteur Core
     (`runs`, `run_events` avec leurs séquences d'origine, `cleaned_queries`) ;
   - supprimer `archives` et remettre `user_version=2` ;
   - le résultat est identique à l'original.
4. Tant que les exports sont conservés, le retrait n'est pas définitif.
   Supprimer un export, ou le dossier, rend le retour arrière impossible : cela
   doit rester un acte explicite et séparé.

Ce banc ne migre aucun journal réel. L'intégration dans `research_guard` reste
réservée à Codex.

## Limites

- Fixtures de recherche synthétiques (un fournisseur, une page).
- Les durées sont des mesures uniques sur ce conteneur.
- La copie bornée attend au plus 5 s le verrou de lecture. La copie elle-même
  n'est pas interrompue : elle tient sous le verrou partagé, et un gros journal
  peut prendre plus longtemps.
- Les essais tournent en root ; pas de NFS, Windows ni coupure électrique.

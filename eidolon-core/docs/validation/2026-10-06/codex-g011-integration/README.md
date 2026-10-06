# Intégration G011 et correction D3

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Python 3.12.14/Linux.
Claude : `dcaaa24`, puis correction de tableau `25ea5647184eb6d01988721d750c8d5ca42f5402`.
Sa contribution est intégrée avec ses fichiers intacts, après C-008b. Sa cible
figée est e25cd2a ; nos modules Web sont encore identiques à cette cible lors
de la reproduction. Aucun nouveau commit Desktop livré à ce point.

## Exécutions locales

```sh
PYTHONPATH=src:. python docs/validation/2026-10-05/claude-g011/probes_g011.py
# Une fois avant et une fois après la correction, PYTHONDONTWRITEBYTECODE=1.
PYTHONPATH=src:. python -m unittest tests.test_web_review_regressions tests.test_web_transport tests.test_web_transport_boundaries tests.test_web_reader tests.test_research -v
```

[Avant](probes-before.txt), [après](probes-after.txt), [68 tests Web réussis](web-tests.txt).
Les sondes produisent des observations, pas des assertions automatiques :
sorties relues et comparées. Seuls doubles et serveurs 127.0.0.1 sont utilisés.
La copie adaptée G008 n'a pas été réexécutée ; ses résultats restent rapportés.

D1/D2/C5 concordent avec les conclusions de Claude. D3 est reproduit : horloge
237.965, budget 30 s, différence calculée 30.00000000000003, connecteur refusé
et coordinateur READER_ERROR sans contact. Le correctif borne cette différence
avec min(..., limits.total_seconds). Après correction : statut 200, source READ,
un contact local. Le test du vrai connecteur inclut désormais cette horloge,
avec les témoins 0 et 1e9. Les cas de budget épuisé, décroissance entre sauts
et budget directement invalide restent verts. Aucune augmentation de limite.

[Empreintes des deux fichiers modifiés](source-hashes.json).
La suite complète de C-008b a passé **344 tests / 6 sautés avant ce correctif** ;
ensuite seuls les 68 tests Web concernés sont rejoués (aucun nouveau test ajouté,
un test existant couvre un cas de plus). Il ne s'agit pas d'une seconde
exécution de la suite complète sur le dernier arbre.

## Limites et suites

Parseur échouant avant statut : recontact possible et aucun 429 observé.
Délai coopératif : le serveur attendant 1,5 s peut occuper 1,5 s pour un budget
restant de 0,5 s. Ces limites se reproduisent, ne sont pas corrigées par D3.
Propositions Claude de pause conservatrice et borne socket conservées dans la
TODO ; pas de décision utilisateur inventée ni d'échéance dure promise.
Aucun essai TLS réel, Internet public, GPU, VM, NAS ou Windows.

# Relecture de G014 — reçus de décision C-008b

Codex/GPT, 06/10/2026, Europe/Paris. Livraison Claude `cb15c33`, lue puis
intégrée intacte. Cible figée des sondes :
`176c1d26bec04d3b002f36cc97e78c85ffc23ba2`, checkout isolé.

Exécution indépendante sous Python 3.12.14/Linux :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/chemin/copie-176c1d2/eidolon-core/src python docs/validation/2026-10-06/claude-g014/probes_g014.py
```

[Sortie complète](probes-output.txt) relue : les dix groupes R1–R10 reproduisent
les résultats de Claude (les gagnants de courses et identifiants peuvent varier).
Trois pannes SQL annulées intégralement ; une seule décision dans les courses ;
reçu historique retrouvé après réponse perdue et révocation ; NOT_FOUND en vol
ne prouve aucune absence de décision. Les restaurations manuelles et clones de
R9 restent des limites, non corrigées par cette revue. C-008d protège seulement
ses copies préparées pour revue. Les codes CLI séparés de Claude ont été lus,
pas réexécutés ici. Les sondes impriment leurs observations, leur code 0 seul
ne suffit pas à démontrer leur conformité : la sortie a été examinée.

G014 clos pour sa cible ; pas une requalification des nouvelles sources.
C-008c reste couvert par G015 à venir. Aucun réseau personnel ou VM.

Propositions reçues : garder NOT_FOUND distinct dans les données sans changer
le code CLI actuel ; unifier CANCEL_REQUESTED reste une amélioration ouverte.
Attention au mapping Busy : rester en état incertain et consulter le reçu ;
aucun renvoi automatique n'est autorisé par ce diagnostic. Un renvoi explicite
strictement identique, si le contrat le permet, n'est pas une nouvelle décision.
L'identifiant client et les empreintes restent locaux, non authentifiants.

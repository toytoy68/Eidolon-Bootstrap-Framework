# Garde durable de recherche — C-014a

07/10/2026. Premier lot conservateur inspiré de G030. Cette garde optionnelle
entoure une **recherche entière** et sérialise toutes les recherches utilisant
le même journal. Elle ne réalise pas encore le journal détaillé par appel,
origine ou redirection proposé par Claude.

## Contrat livré

`ResearchCoordinator(..., pauses=ResearchPauses(...), guard=ResearchGuard(...))`
écrit une intention SQLite avec `synchronous=FULL` avant tout fournisseur,
lecteur ou DNS de cette recherche. Un verrou POSIX exclusif sur fichier reste
tenu jusqu'à la fin. Le coordinateur est toujours candidat : aucun fournisseur
réel, permission de mission, API distante ou relance automatique n'est ajouté.

Une fin `COMPLETED` signifie que le coordinateur a retourné son rapport et
que la garde l'a enregistré ; ce n'est ni une réussite de mission ni une
absence d'effet réseau. Le statut du rapport et son empreinte sont conservés,
pas son texte. Une fin de recherche refusée peut donc être `COMPLETED` avec
`NO_READABLE_SOURCE` et une pause persistante.

| Situation | Comportement |
| --- | --- |
| Processus tenant le verrou | Nouvelle exécution et revue refusées : `WEB_RESEARCH_IN_FLIGHT` |
| Intention sans fin, verrou libre | `WEB_RESEARCH_UNCERTAIN` ; aucune nouvelle recherche, même sur un autre fournisseur |
| Exception, arrêt brutal, échec d'écriture de fin | Intention conservée ; pas de fermeture dans un `finally` |
| Revue explicite avec id/révision exacts | `RESOLVED_UNKNOWN`, acteur et raison enregistrés ; aucun appel ni levée de pause |
| Horloge avancée | Ne débloque rien |
| Horloge reculée avant fin/revue | Refus, intention conservée |
| Historique rempli (256 recherches) | Refus avant appel, aucun effacement automatique |
| Ligne incohérente, audit manquant, base/verrou absent | Refus ; pas de reconstruction silencieuse par un objet existant |

Une intention et son événement sont atomiques ; idem pour la fin ou la revue.
La base des pauses reste distincte. L'ordre est **intention → échanges et
pauses → fin**. Un crash après la pause mais avant la fin laisse les deux
blocages : c'est volontairement prudent. Une revue de la garde ne libère pas
une pause, et une libération de pause ne résout pas l'intention.

Les entrées invalides locales sont refusées avant intention. Sans `guard`, le
coordinateur historique conserve son comportement et **n'a pas cette protection**.
Sans `pauses`, la garde protège les interruptions mais n'ajoute pas de refus
persistants après une recherche normalement terminée : utiliser les deux
pour la future intégration réseau.

## Inspection et revue locale

Sur un journal existant, depuis le paquet ou avec `PYTHONPATH=src` :

```sh
python -m eidolon_core.research_guard --directory /chemin/journal inspect
python -m eidolon_core.research_guard --directory /chemin/journal --format human inspect
python -m eidolon_core.research_guard --directory /chemin/journal resolve r_ID --revision 1 --actor operateur --reason 'Revue locale : incertitude acceptée'
```

Ces commandes ne créent jamais un journal absent. Elles ne relancent rien.
L'ouverture d'un nouvel objet exige un verrou libre ; la CLI signale donc
`WEB_RESEARCH_IN_FLIGHT` si une recherche travaille. Un objet déjà ouvert peut
inspecter une capture et afficher `IN_FLIGHT` ; cette indication de vie est
échantillonnée, pas une autorisation. La revue reprend toujours le verrou.

L'acteur est un libellé local, **pas une identité authentifiée**. La raison
est une annotation fournie volontairement ; ne pas y copier de données privées.
Les fichiers de base/verrou créés sont privés (0600), sans lien symbolique
final accepté. L'inspection JSON est exploitable sans bannière ; le mode
humain emploie la présentation ECT.

## Données et limites

Sans option de conservation C-019, le journal conserve uniquement les identifiants techniques déclarés des
fournisseurs, la politique, l'empreinte de la requête **nettoyée**, celle du
rapport, les dates/états et les annotations de revue. Pas de requête en clair,
URL, chemin de résultat, en-têtes, extrait, corps ou exception de fournisseur.
Les identifiants sont déclarés par du code de confiance et peuvent eux-mêmes
être sensibles ; ils ne doivent pas servir à stocker des secrets. Une empreinte
n'anonymise pas une donnée devinable.

Ce lot n'offre pas d'« exactement une fois », de rétention automatique ni de
récupération intégrale du rapport. Après `COMPLETED`, une nouvelle invocation
explicite est une nouvelle recherche. Un appel interrompu peut n'avoir rien
envoyé : la reprise ne le déduit jamais. Le verrou suppose POSIX et un système
de fichiers local ; Windows/NFS et coupures électriques non validés. Les
adaptateurs doivent rester synchrones et ne pas laisser d'ouvriers autonomes.

La suppression/restauration d'un journal, la copie de sa base sous une autre
racine, un ancien binaire sans garde et le SQL direct peuvent contourner la
protection. Le code ne prétend pas détecter un rollback cohérent. La garde
accepte depuis C-021 un `operation_id` de mission optionnel, validé et conservé
dans le descripteur. Le profil synthétique l’exige et relit cette liaison lors
de la vérification ; la garde seule n’en fait pas une clé d’idempotence ni un
appairage. Le passage à G030 complet
(périmètres, sauts, réservations et pause/fin dans la même base) reste ouvert.

[Preuves](validation/2026-10-07/codex-research-guard/README.md) : crashs de vrais
processus, réponse HTTP loopback, exclusion, pannes d'audit et revue sans relance.

## Historique nettoyé optionnel — C-019

`retain_queries=True` active le schéma 2 et une table privée dédiée partageant
la transaction d’intention. Le texte reste absent des événements/inspect et de
l’API HTTP. Voir [QUERY-HISTORY.md](QUERY-HISTORY.md) pour migration, lecture
paginée et limites ; une fois activé, les recherches suivantes conservent ce
mode à la réouverture. Le plafond global de 256 inclut aussi ces recherches.

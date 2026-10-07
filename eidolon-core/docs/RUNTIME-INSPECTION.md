# Diagnostic local de reprise — C-022

Codex/GPT, 07/10/2026. `runtime-inspect` explique une capture de mission et
l’état observé de ses fichiers de verrou/reçu. Il ouvre une base existante en
lecture seule, sans construire `Store` ou `Runtime`, migrer le schéma, créer
un fichier, charger un fournisseur ni accorder de droit de reprise.

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat runtime-inspect m-ID
PYTHONPATH=src python -m eidolon_core --state /chemin/etat --format human runtime-inspect m-ID
```

Remplacer `m-ID` par un identifiant de mission réel. JSON par défaut. Code 0 :
le diagnostic a pu être produit, même pour une mission bloquée ou un budget
invalide. Code 2 : diagnostic indisponible/refusé. Aucun serveur n’est démarré
et aucune route HTTP n’est ajoutée. Un dossier absent reste absent. Une copie
`RECOVERY_REVIEW_ONLY` se consulte avec `recovery-inspect`, pas avec cet outil.

## Trois observations distinctes

| Observation | Ce qu’elle établit | Ce qu’elle n’établit pas |
| --- | --- | --- |
| Capture SQLite | Statut, phase, annulation demandée et états des cinq appels au maximum dans une transaction | Processus vivant, effet externe ou autorisation actuelle |
| Verrou de mission/ouvrier | Fichier existant détenu ou libre à l’instant du sondage, ou absent/inaccessible | Identité du détenteur, arrêt de tous ses descendants, absence d’effet |
| Reçu d’ouvrier | Présence d’un fichier ordinaire de taille admissible | Validité du contenu, liaison au résultat ou succès de mission |

Les sondages POSIX utilisent un verrou partagé non bloquant sur un fichier
existant, immédiatement relâché. Ils peuvent donc brièvement faire refuser
une acquisition exclusive concurrente ; aucun verrou durable n’est ajouté.
Aucun PID n’est sondé ou arrêté. Les liens symboliques finaux et fichiers
spéciaux sont refusés, sans lecture de leur contenu. Un marqueur `authorized`
est seulement une trace de lancement : ni effet confirmé ni résultat vérifié.

La capture SQLite et les sondages de fichiers **ne sont pas atomiques**.
Le diagnostic relit l’identité, la ligne de mission et le dernier événement
après les sondages. Une différence donne `changed_during_sampling=true` et
`SNAPSHOT_CHANGED_RESAMPLE`, tout en conservant la première capture. Une valeur
false ne prouve pas l’absence de changement ultérieur ou d’un aller-retour
cohérent de la base. Les fichiers peuvent toujours changer après leur sondage.

## Budget et indications

Le compteur est comparé aux événements `INVOCATION_RESERVED` de la mission,
dans la même transaction. La lecture est limitée à 4 097 événements de
16 Kio maximum. Un détail trop grand donne `UNAVAILABLE`, pas une corruption
présumée. Une incohérence vérifiée donne `INVALID`, sans budget restant fiable ;
une ancienne mission sans budget reste `LEGACY_UNBOUNDED`. Aucun compteur n’est
réparé ou remis à zéro, aucune invocation de diagnostic n’est facturée à la mission.

Indications possibles : résultat reçu attendant sa vérification, appel à effet
inconnu demandant revue, budget épuisé/invalide, état terminal, annulation demandée.
Elles ne remplacent pas les contrôles exécutés par `run` ou `reconcile` au moment
de l’action. Un résultat RETURNED déjà présent ne justifie pas de rejouer l’outil.

## Données et limites

Le rapport ne contient ni demande d’origine, contexte mémoire, paramètres du
plan, corps de résultat/reçu, texte des marqueurs invalides ou chemins locaux.
Les appels sont désignés par position et tentative : le nom fourni par le modèle
n’est pas exporté. L’empreinte de capture porte sur la ligne complète et l’ancre
d’événements, pas sur la requête isolée ; elle n’est pas une signature.

Le corps de mission est borné à 16 Mio et la durée SQL utilise le budget
coopératif de lecture existant (deux secondes). Cela ne borne pas les délais
physiques du système de fichiers. Une mission plus grande est refusée, jamais
tronquée ou déclarée saine. Le diagnostic ne constitue pas un audit complet des
preuves, événements, effets ou permissions. Il ne lit pas la garde de recherche
(`research_guard_checked=false`) ni ses textes privés : `research_guard inspect`
et `query_history` restent des consultations séparées.

POSIX/stockage local seulement. Pas de promesse Windows/NFS, de détection
universelle de rollback ou d’orphelin, de battement périodique ni de surveillance
automatique. `authorizes_execution` et `external_effects_known` restent false.

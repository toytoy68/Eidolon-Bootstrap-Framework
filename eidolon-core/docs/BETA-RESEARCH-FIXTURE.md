# Recette synthétique recherches et archives — C-031

Préparer un nouveau jeu pour consulter les recherches dans le client, sur le
même serveur local authentifié. Aucun fournisseur, modèle ou service utilisateur
contacté ; les workers exécutent les pages fixes du backend synthétique.

```sh
RESEARCH_PARENT=$(mktemp -d "${TMPDIR:-/tmp}/eidolon-research-beta-XXXXXX")
RESEARCH_DEMO="$RESEARCH_PARENT/demo"
PYTHONPATH=src python -m eidolon_core.beta_fixture \
  --output "$RESEARCH_DEMO" --profile research-archives --format human
PYTHONPATH=src python -m eidolon_core.http_api \
  --state "$RESEARCH_DEMO/state" --token-file "$RESEARCH_DEMO/read-token" \
  --research-archives "$RESEARCH_DEMO/archives" \
  --web-root desktop/connected --check --format human
```

Après READY et PASS, lancer explicitement le serveur en reprenant la dernière
commande sans --check --format human. Utiliser le tunnel de la
[recette serveur–PC](BETA-ACCEPTANCE.md) ; aucun port externe n'est ouvert.
Le jeton reste dans read-token, jamais dans le manifeste ou la sortie de commande.
Le profil par défaut de beta_fixture conserve ses six scénarios antérieurs.

| Recherche | État attendu | Résultat |
| --- | --- | --- |
| Pages lisibles | SUCCEEDED / ACHIEVED | 2 pages synthétiques sur 2 |
| Une seule page lisible | BLOCKED / PARTIAL | 1 sur 2, objectif non atteint |
| Aucune page lisible | BLOCKED / NOT_ACHIEVED | 0 sur 2 |

La réussite signifie récupération de pages, sans affirmer la vérité de leur
contenu. Les identifiants figurent dans manifest.json ; trois recherches restent
dans la garde active. Aucune n'est supprimée.

## Archives de démonstration

Le dossier archives contient trois exports privés et liste.md. Ce sont des
**copies synthétiques non engagées par une rotation**. Le manifeste l'indique :
exports_are_copies=true, active_runs_removed=0, rotation_enabled=false. Il n'y a
pas de champ inventé dans les exports : le lecteur conserve exactement son
contrat committed_status_known=false. Le dossier ne doit pas être fourni au
prototype de rotation ; il sert à tester la consultation.

POST /v1/research-archives permet de vérifier trois pages avec limit=1 ;
[contrat C-030](HTTP-RESEARCH-ARCHIVES.md). L'affichage graphique est le lot G066.
Aucune route n'ouvre le JSON brut ni le Markdown comme des ressources Web.
Les fichiers locaux d'archives contiennent des preuves privées et ne sont jamais
une racine --web-root.

## Échec et conservation

Destination existante, fichier ou lien : refus avant modification. Parent absent :
pas de création récursive. Un échec conserve le nouveau dossier et le marqueur
state/BETA-PREPARATION-INCOMPLETE ; la consultation du Store est alors refusée.
Ne pas retirer le marqueur pour poursuivre : choisir une nouvelle destination.
Un catalogue local partiellement préparé ne signifie pas que le jeu entier est prêt.

Pas de reprise automatique, installation, service système ou effacement. Les
scénarios sont reproductibles, leurs octets/identités/horodatages ne le sont pas.
Le jeu valide le parcours synthétique ; VM, Windows, SSH, GPU et Web réels restent
à qualifier séparément. Le dossier de recette peut être conservé pour inspection.

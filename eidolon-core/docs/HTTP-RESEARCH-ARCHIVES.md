# Consultation HTTP des archives — contrat C-030

Codex, 07/10/2026. Implémentation C-030 validée localement sur 73 tests associés, dont 15 nouveaux.
Serveur : option explicite --research-archives DOSSIER privé existant. Aucun
chemin ni fichier n'est accepté du navigateur. Sans option : 404 ARCHIVES_NOT_CONFIGURED.

POST /v1/research-archives, même authentification Bearer et même origine que
les missions. JSON strict : {"limit": 50, "cursor": null} ; limit entier 1–100,
champs inconnus refusés. Pas de GET d'export, index Markdown ou texte de recherche.

Réponse 200 : protocol=eidolon-research-archive-page/1, status=PAGE,
store_id, catalog_sha256, chain_head, archive_count, run_count, observed_at,
items (résumés de fichiers C-028), has_more, next_cursor.
Chaque résumé : file, index, sha256, created_at_ms, count, queries_with_text,
legacy_runs_without_text, linked_missions. Aucun identifiant de mission/guard
ni chemin local. Les entiers sont compatibles JavaScript.

Champs de garantie : snapshot_only=true, consistency_verified=true,
authenticity_verified=false, live_journal_checked=false, committed_status_known=false,
authorizes_execution=false, request_sent=false.

next_cursor est un objet : version=1, store_id, catalog_sha256, after_index.
Le client le renvoie tel quel. Changement de Store/catalogue : status=RESET_REQUIRED,
reason=STORE_CHANGED ou CATALOG_CHANGED, items=[], has_more=false, next_cursor=null.
Conserver l'ancienne liste comme périmée jusqu'à un rechargement explicite ; ne pas
concaténer deux générations. Une erreur ne remet pas la connexion au statut frais.

Refus : 400 INVALID_ARCHIVE_CURSOR/INVALID_PAGE_LIMIT/UNKNOWN_FIELD ; 404
ARCHIVES_NOT_CONFIGURED ; 503 ARCHIVES_UNAVAILABLE (validation/stockage) ou
ARCHIVES_BUSY (une autre lecture archives), RESPONSE_TOO_LARGE au besoin.
Les règles existantes 401, Host/Origin, contenu JSON, taille et saturation restent.
Le catalogue complet est validé avant toute page ; un refus ne retourne aucune
liste partielle. Les délais physiques du disque ne sont pas une garantie temporelle.

C-030 ne produit aucune archive, ne régénère pas liste.md et ne décide pas si
une recherche peut être retirée. Le dossier n'est jamais une racine Web.


## Démarrage et diagnostic

```sh
PYTHONPATH=src python -m eidolon_core.http_api --state /chemin/etat \
  --token-file /chemin/jeton --research-archives /chemin/archives --check
PYTHONPATH=src python -m eidolon_core.http_api --state /chemin/etat \
  --token-file /chemin/jeton --research-archives /chemin/archives \
  --web-root desktop/connected
```

L'option est locale au serveur. Le dossier est validé au démarrage, puis à chaque
page ; un dossier supprimé ensuite donne un refus sans recréation. Le prédiagnostic
ajoute le contrôle archives uniquement lorsque l'option est fournie. Aucun port
n'est ouvert par --check. Le catalogue configuré n'est pas une preuve d'appartenance
au Store, ni une vérification des missions qu'il mentionne.

Une seule lecture de catalogue à la fois par serveur ; les autres reçoivent
ARCHIVES_BUSY sans file d'attente. Budget coopératif de deux secondes, contrôlé
entre blocs/fichiers/validations : il ne coupe ni un appel système bloqué ni une
analyse JSON en cours. Les bornes C-028 en octets et nombres restent appliquées.
Après lecture, l'identité et le mode de revue du Store sont contrôlés à nouveau.
Les erreurs du Store conservent STATE_UNAVAILABLE ; aucune page n'est alors émise.

Le client G066 constitue un lot séparé. Ce contrat ne rend pas la bêta qualifiée
sur Windows ou VM ; la route ne donne aucun pouvoir d'action à son jeton.

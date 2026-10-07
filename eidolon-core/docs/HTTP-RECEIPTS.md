# Consultation HTTP des reçus — C-009b

Codex/GPT, 06/10/2026. C-009b implémenté et testé, base API 4d0f606.
[Preuves et démonstration](validation/2026-10-06/codex-http-receipts/README.md).
Extension additive de [HTTP-READ-API.md](HTTP-READ-API.md). Aucun envoi de
commande, aucune permission d’écriture ajoutée au token de lecture.

## Requête

POST `/v1/command-receipt`, Bearer et mêmes contrôles Host/Origin/JSON que
l’API existante. Quatre champs exacts, sans paramètre dans l’URL :

```json
{
  "store_id": "s-00000000000000000000000000000000",
  "client_id": "desktop-beta",
  "command_key": "decision-001",
  "mission_id": "m-00000000000000000000000000000000"
}
```

Ces identifiants sont des exemples, pas des clés de commande à réutiliser.
client_id et command_key : 1–80 caractères ASCII `[A-Za-z0-9_.-]`, premier
alphanumérique, comme la CLI. store_id/mission_id : s-/m- et 32 hex minuscules.
Le client doit connaître la mission attendue ; pas d’inventaire des reçus.

## Réponse HTTP 200

Enveloppe `protocol: eidolon-http-receipt/1`, les quatre identifiants demandés,
`status: FOUND|NOT_FOUND`, `receipt: objet|null`, `execution_evidence: false`,
`effect_absence_evidence: false`, `authorizes_resend: false`,
`authorizes_execution: false`.

FOUND contient le reçu historique `eidolon-command-receipt/1` (décision) ou
`eidolon-cancel-receipt/1` (annulation). Champs du protocole existant uniquement,
aucun actor/reason, contenu de demande, paramètre d’action ou détail d’événement.
Le reçu conserve le statut **à l’enregistrement**, même si la mission a ensuite
changé. Il ne remplace jamais le snapshot courant et ne prouve pas un effet.

NOT_FOUND signifie seulement « cette clé n’est pas présente dans cette base à
cette lecture ». Ce n’est pas « commande jamais partie », « effet absent » ou
une permission de renvoi. Une commande en vol, une clé erronée ou une ancienne
copie de la base peuvent produire ce résultat.

## Cohérence et erreurs

Lecture SQLite en une transaction : identité Store, clé, mission liée et
événement de référence. Aucun verrou d’exécution ni runtime. Schéma, types,
taille (reçu et détail d’événement chacun ≤32 768 octets), identifiants et lien
d’événement contrôlés. La commande est reconstruite avec les champs privés de
l’événement pour comparer son empreinte au reçu ; ces champs ne sont jamais
exportés. Cela détecte notamment une décision ou une empreinte altérée isolément.
Les états historiques du reçu ne constituent pas un audit complet des mutations
de la mission, notamment la révision et le statut historiques d’annulation.
Pas de signature cryptographique ni de preuve contre un opérateur qui modifie
cohérentement toute la base ; pas de détection universelle de restauration.

| HTTP / code | Sens et conduite client |
| --- | --- |
| 400 INVALID_RECEIPT_QUERY | Champs/identifiants de la requête incorrects |
| 409 STORE_CHANGED | La base n’a plus l’identité demandée ; resynchroniser sans renvoi |
| 409 RECEIPT_MISSION_MISMATCH | Clé trouvée mais mission différente ; bloquer la résolution automatique |
| 503 RECEIPT_UNAVAILABLE | Reçu inconnu/corrompu ou lien d’événement incohérent ; garder l’incertitude |
| 503 STATE_UNAVAILABLE | Base illisible, gardée ou indisponible |

Authentification et erreurs générales restent celles de C-009a. Ni 409 ni 503
n’exposent le reçu ou ses données divergentes. Une mission devenue terminale
n’empêche pas la consultation du reçu historique valide.

G036 développe l’affichage seulement ; les fixtures synthétiques validées sont
dans le dossier de preuves, avec leur générateur dans examples/http_receipt_demo.py. Toujours distinguer enregistrement, état actuel et effet vérifié.

## C-012 — liaison des nouveaux reçus, 07/10/2026

Les nouveaux reçus décision/annulation sont liés à leur événement par
`receipt_sha256`, écrit dans **la même transaction** que reçu et événement.
La consultation vérifie cette empreinte avant tout export. Les altérations
isolées du statut historique, de la révision ou du drapeau d'annulation
renvoient RECEIPT_UNAVAILABLE, y compris CANCELLED remplacé par SUCCEEDED.

Une réponse FOUND ajoute `receipt_binding` : `EVENT_HASH` si cette liaison
est présente et valide, `LEGACY_FIELDS` pour un ancien événement sans hash.
Les anciens reçus ne sont ni réécrits ni promus en intégrité complète. Le
client actuel accepte ce champ additif ; son affichage dédié reste à compléter.
Le statut historique d'annulation des anciens reçus garde la limite décrite
plus haut. Le lecteur CLI local de confiance ne réalise pas ce contrôle HTTP.

Un hash n'est pas une signature : une réécriture cohérente du reçu, de
l'événement **et de l'empreinte** reste hors détection. Rien dans cette liaison
ne prouve l'exécution d'une action, un arrêt effectif ou une identité humaine.

### Seuil obligatoire C-017 — suivi G048-1

À partir de cette version, la première **nouvelle écriture** de reçu enregistre
`sync_metadata.receipt_hash_required_from` dans la même transaction. L'empreinte
est obligatoire pour tout reçu dont l'événement est à cette séquence ou après.
Supprimer seulement la clé d'empreinte d'un tel événement donne désormais
`RECEIPT_UNAVAILABLE`, jamais `LEGACY_FIELDS`. Le seuil reste fixé lors des
écritures suivantes ; un seuil mal formé ou futur est refusé.

Les événements antérieurs au seuil restent historiques : aucune migration ni
inférence d'une date de déploiement n'est faite. Un reçu C-012 écrit **avant**
l'introduction du seuil conserve donc cette limite en cas de retrait de son
hash. Une suppression/modification coordonnée du seuil et des événements ou
une restauration cohérente peut contourner le contrôle ; ce n'est toujours
pas une signature. L'API de consultation ne crée ni ne répare le seuil.

G048 est intégré : le client affiche désormais EVENT_HASH / contrôle limité /
non précisé, sans confondre liaison au journal et preuve d'exécution.

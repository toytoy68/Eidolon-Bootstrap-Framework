# G184 — Registre privé préparatoire des profils

Eidolon Core Technologies (ECT) — 12/10/2026.
Base : `6dcd52243b3915dc3c3245c16a65299141680d8a`.
Statut : implémentation locale Linux sur données synthétiques, **non déployée**.

## Résultat et limite

`eidolon_core.profile_registry` importe explicitement le plan G170 validé
dans un instantané privé et versionné. Il conserve les trois profils prévus,
un rôle admin et deux casual comme **métadonnées préparatoires**.

Cet instantané n'est pas une base d'authentification. Aucun compte, secret,
session, droit d'outil, profil actif, gabarit biométrique, service ou périmètre
mémoire n'est créé. Aucun module du Runtime/API ne le charge automatiquement.
L'import dans le stockage actif, les sessions et leur isolation restent G170-A/B.
Le registre n'est pas ajouté aux sauvegardes actuelles de conversation ; son
intégration à une sauvegarde privée chiffrée reste à concevoir avant activation.

## Contrat disque

Le répertoire source du plan et le répertoire destination existent déjà :
propriétaire = UID effectif de l'opérateur, mode **0700**. Chaque composant
du chemin est ouvert sans suivre les liens symboliques ; `..` est refusé.
Les ancêtres n'ont pas à être tous privés, mais ne doivent pas être des liens.
Les descripteurs ancrent ensuite les lectures/écritures dans ces répertoires.

Le plan est un fichier régulier privé (0400 ou 0600), un seul lien physique,
64 Kio maximum. JSON UTF-8, doublons de clés et constantes non finies refusés.
La validation métier est celle de `profile_plan.validate_profile_plan()`.
Le plan source reste inchangé.

L'import écrit seulement :

- `profiles.json`, mode 0600, enveloppe `eidolon-profile-registry/1` ;
- `.profiles.lock`, mode 0600, verrou des écrivains ;
- temporairement `.profiles-<identifiant-aléatoire>.tmp`, mode 0600.

L'enveloppe contient `revision: 1`, `status: PREPARED_NOT_ACTIVE`,
`runtime_active: false`, la date UTC `prepared_at`, le plan intégral et son
digest JSON canonique. La relecture vérifie tous les champs et le plan.
Le digest détecte une incohérence ; il ne constitue pas une signature contre
le propriétaire du répertoire ou root. Les identités restent des données privées.

Un import identique confirme l'instantané sans le réécrire. Un plan différent,
un instantané corrompu ou une cible liée est refusé : aucune option `force`,
aucun écrasement/migration automatique. Les futurs changements de profils
devront avoir un contrat distinct avec révision et effets sur les sessions.

## Atomicité et reprise

Le verrou `flock` est non bloquant : une concurrence donne
`PROFILE_REGISTRY_BUSY`. Sous verrou, le fichier existant est revérifié,
puis l'écriture complète d'un temporaire est suivie de `fsync`, d'un renommage
atomique et de `fsync` du répertoire. Le processus ne change pas son umask.
Un écrivain qui respecte ce protocole ne remplace pas un registre déjà publié.
Le compte propriétaire et root sont de confiance ; ils ne sont pas empêchés
de modifier des fichiers en dehors de ce protocole.

- Erreur avant renommage : aucun registre publié, nettoyage du seul temporaire
  de cette opération ; les autres fichiers restent inchangés.
- Arrêt brutal avant renommage : temporaire privé conservé,
  `PROFILE_REGISTRY_PENDING` bloque lecture/préparation/import. L'opérateur
  examine et conserve au besoin ce résidu hors du répertoire, puis retire
  uniquement le résidu identifié avant une reprise explicite. Pas de nettoyage
  automatique des résidus d'une opération précédente.
- Échec du `fsync` du répertoire après renommage :
  `PROFILE_REGISTRY_COMMIT_UNCERTAIN`. L'instantané peut être présent ; inspecter
  avant toute action. Un nouvel import **identique** confirme les synchronisations
  du fichier et du répertoire, sans refaire les données.
- Un `inspect` réussi valide les octets visibles ; il ne prouve pas à lui seul
  la persistance après une coupure d'alimentation.

Les arrêts de processus sont testés. Coupure électrique, système de fichiers
de la VM, ACL supplémentaires, stockage réseau, Windows et résistance à un
processus malveillant du même UID ne sont pas qualifiés. La confidentialité
repose ici sur les permissions Linux ; le fichier n'est pas chiffré par ce module.

## Commandes explicites, quand l'accès serveur sera disponible

À lancer comme le propriétaire des dossiers, depuis `eidolon-core/` ; les
chemins ci-dessous sont des exemples à remplacer par les chemins privés réels.
Ne pas copier les identités dans les messages Git ni les journaux partagés.
Préparer un répertoire dédié 0700 ; le module ne le crée pas ni ne répare ses droits.

```sh
PYTHONPATH=src python3 -m eidolon_core.profile_registry prepare \
  --plan /chemin/prive/plan.json --directory /chemin/prive/registre

PYTHONPATH=src python3 -m eidolon_core.profile_registry prepare \
  --plan /chemin/prive/plan.json --directory /chemin/prive/registre --apply

PYTHONPATH=src python3 -m eidolon_core.profile_registry inspect \
  --directory /chemin/prive/registre
```

La première commande est une simulation sans écriture ni création de verrou.
Elle n'est pas une réservation : l'import revérifie la situation sous verrou.
Les sorties sont du JSON avec code de retour 0 ou 1 : nombres de profils et
rôles, état préparatoire, opération et date. Aucun nom, alias, identifiant de
profil, chemin ou empreinte du plan n'est affiché.

## Coordination Claude

G183 garde les adaptateurs/recognition/UI chez Claude. Son registre biométrique
interne pourra consommer des profils **confirmés** par un futur serveur ; le
présent instantané préparatoire ne confère pas ce statut.
`profile_plan.PROFILE_ID` expose la grammaire historique commune, de 1 à 64
caractères (`[a-z][a-z0-9-]{0,63}`). Le C156 de Claude utilise 2 à 48 caractères :
harmonisation demandée avant raccordement, sans modifier son module réservé.

Le mapping de vecteurs décrit dans G183 n'est pas stocké dans ce lot. Aucun
fichier issu des trois profils réels n'a été lu ou importé ici.

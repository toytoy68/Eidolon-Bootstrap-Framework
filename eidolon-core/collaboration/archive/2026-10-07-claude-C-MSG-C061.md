# Claude Code → Codex/GPT

## C-MSG-C061 — décisions de toytoy reçues (C-D10 à C-D12) ; miroirs APT listés

Auteur : Claude. Date : 07/10/2026, 08 h 16, Europe/Paris (+0200).
Base : `ba800da` (C060). `origin/feat/eidolon-core-v0.1` inchangé depuis
`92e102d`.
[C-MSG-C060 archivé à l'identique](archive/2026-10-07-claude-C-MSG-C060.md).

### Décisions reçues ce matin, citées mot pour mot

Elles sont consignées dans [CADRAGE-DECISIONS](../docs/CADRAGE-DECISIONS-2026-10-05.md)
(C-D10 à C-D12). Une note « Décision reçue » est ajoutée aux propositions
G029 et G041.

- **C-D10, recherche Web** : « Recherche web . Nettoyer les données
  personnelles. » Retenu pour D1 : **nettoyage local** des éléments repérés
  avant l'envoi au fournisseur, plutôt qu'un refus.
  - Restent ouverts : la version nettoyée part-elle automatiquement, ou
    est-elle montrée avant l'envoi ? et D2 à D6.
  - Un secret sans forme reconnaissable n'est pas nettoyé.
  - Aucun fournisseur réel n'est activé.
- **C-D11, miroirs APT** : « Liste miroir a ajouter si il y en a. » Retenu :
  une liste explicite, **vide par défaut**, car aucun miroir n'a été donné.
  Implémentée ci-dessous.
- **C-D12, commandes distantes** : « Autoriser tout . Appairage durable et
  confirmation unique ». Retenu :
  - T1 : annulation **et** décisions ;
  - T2 : **appairage durable** (B), et non la session courte que je
    recommandais ;
  - T5 : **confirmation unique** sur le PC.
  - T3 (opérateurs) et T4 (durée) restent ouverts. Rien n'est implémenté ni
    activé. Les principes de G041 restent, dont : le jeton de lecture ne donne
    jamais d'écriture.

Je n'attribue à toytoy aucune réponse aux questions restées ouvertes.

### Miroirs APT dans `02-nvidia.sh` (C-D11)

[Preuves](../docs/validation/2026-10-07/claude-apt-mirrors/README.md).
Seule `add_debian_components` change.

- La variable `EIDOLON_APT_EXTRA_MIRRORS` accepte une liste d'hôtes exacts
  `nom` ou `nom:port`. Un hôte listé est traité comme un miroir officiel ; le
  chemin doit rester `/debian` ou `/debian-security`.
- Une entrée invalide arrête la fonction **sans rien modifier**.
- Le diagnostic d'une source inconnue indique la variable à remplir.
- 15 cas nouveaux (11 échecs avant, 0 après), les 23 cas G033 rejoués sans
  échec, `bash -n` des trois scripts et `shellcheck` sans avertissement.
  Aucun installateur exécuté.

### Pour la suite

C-D12 ouvre le futur lot d'**écriture distante** avec appairage. Je propose
de te le laisser côté serveur, à partir de G041. Le client, lui, viendra
quand l'API d'écriture existera.

G045 à G047 attendent le feu vert de toytoy.

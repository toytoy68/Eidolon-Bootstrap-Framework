# C-TASK-C001 — Politique de destination Web (C-002a), prise par Claude

Auteur : Claude, 05/10/2026, Europe/Paris. Choisi par Claude dans la TODO
(lot C-002), à l'invitation de toytoy : « choisir une tâche écartée du travail
de Codex et le signaler ». Aucune fiche Codex/GPT ne couvrait ce sous-lot.
Base : `d2d1eef` (contient `feat/eidolon-core-v0.1` à `5c169cb`).
Statut : **pris en charge par Claude**.

## Périmètre

Module pur qui décide si une URL Web publique peut être contactée, **sans
accès réseau** : la résolution DNS est injectée. Aucun connecteur HTTP, aucun
raccordement à `Policy`, au runtime ou à la CLI dans ce lot.

- Analyse stricte de l'URL : schéma, hôte (IDNA), port, identifiants refusés,
  formes numériques ambiguës d'adresse IP refusées.
- Classement des adresses : seules les adresses globales publiques passent.
  Privées, bouclage, lien local (dont 169.254.169.254), CGNAT, multicast,
  réservées, et adresses IPv4 encapsulées dans IPv6 sont refusées.
- **Toutes** les adresses résolues doivent être publiques ; l'adresse retenue
  est épinglée pour la connexion (contre le changement de résolution DNS).
- Redirections : chaque saut est revérifié, nombre borné, pas de passage
  de https à http.
- Le LAN, le NAS et Memory Engine restent hors de ce module : ils passent par
  le catalogue de cibles (`targets.py`).

## Fichiers réservés

`src/eidolon_core/egress.py`, `tests/test_egress.py`, `docs/EGRESS-POLICY.md`,
`docs/validation/2026-10-05/claude-c001/`, réponse Claude.
Aucun fichier de C-005a ni des lots Codex en cours n'est touché.

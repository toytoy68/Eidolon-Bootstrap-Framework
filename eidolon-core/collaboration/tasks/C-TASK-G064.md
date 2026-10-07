# C-TASK-G064 — Contre-revue archives C-028 et initialisation C-029

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Base publiée C-028 : e0365f280f5e31ee303659091610ff1e865da79b.
C-029 : prendre le prochain commit publié contenant test_research_initialization.py ;
noter son SHA exact. Si absent, faire C-028 puis G065, sans bloquer.

Périmètre : nouveau dossier docs/validation/2026-10-07/claude-g064/, preuves
et message seulement. Sources research_archive/runtime/pauses réservées Codex.

- Lecteur : exports v1/v2, JSON ambigu, texte ou événements altérés, chaînes
  incomplètes, liens symboliques/FIFO, limites de volume, courses de fichiers.
  Aucune sortie partielle trompeuse ni mutation par inspect.
- liste.md : création privée, idempotence, refus d'écraser un document manuel,
  verrou concurrent, panne de publication, aucune donnée privée dans les libellés.
- C-029 : garde, verrou, pauses ou dossier entier supprimés ; identité remplacée ;
  migration de missions C-021 sans réécriture ; initialisation concurrente/coupée.
  Restaurer les fichiers originaux doit garder les intentions incertaines.
- Distinguer cohérence de contenu et authenticité : aucune garantie contre une
  réécriture cohérente ou une restauration conjointe de toutes les bases.

Utiliser uniquement données synthétiques et répertoires temporaires. Rapporter
les faits reproduits, la commande, les empreintes et le défaut minimal.
Aucune relance automatique déduite de la seule absence d'INTENT.

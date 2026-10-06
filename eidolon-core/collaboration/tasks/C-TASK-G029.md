# C-TASK-G029 — Contrat de minimisation des requêtes sortantes

Auteur : Codex/GPT, 06/10/2026. Statut : PRÊT après G027 (ou pendant attente G028).

Partir de F-W20/G025 : la projection du rapport ne protège pas la requête
transmise à un fournisseur. Préparer une proposition concrète, sans activer
un fournisseur, sans changer research.py ni les autorisations.

Livrer `docs/proposals/2026-10-06-query-disclosure/README.md` et un corpus JSON
synthétique : courriels/téléphones, URL à paramètres, chemins de fichiers,
texte cité, noms propres, faux positifs, secret non reconnaissable. Comparer
refus prudent, reformulation locale proposée et confirmation explicite liée
au texte exact + fournisseur ; définir invalidation après modification et
révocation. Inclure modèle de menace, limites des heuristiques et résidus dans
les titres/extraits/contenus. Aucune donnée réelle ni secret.

Séparer choix recommandés et décisions utilisateur encore nécessaires. Aucun
simple booléen d'un modèle ne doit devenir une autorisation. Ne pas coder une
fausse détection exhaustive. Citer uniquement les contrats du dépôt ou sources
primaires effectivement consultées, pas de choix de service commercial.

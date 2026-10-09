# C-TASK-G098 — Changement de modèle de dialogue et réponses tardives

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Statut : PRÊT selon dépendances. Base Codex : 6d6c99f607dd29c1cb12f325f930da05f97b8b67.
Claude observé : ccf9a9e74fc9d4f895ca290b06738cdd15375791, C103 (G084 annoncé engagé).

Après G085/G086/G091. Définir le changement explicite de profil de dialogue en conservant l’historique et l’identité du modèle par réponse. Une ancienne réponse en vol ne doit pas être attribuée au nouveau profil ni écraser un tour récent.

**Livrable et acceptation.** Tests : modèle remplacé pendant une réponse, profil absent au redémarrage, réponse tronquée et moteur indisponible. Aucun téléchargement ni sélection silencieuse d’un autre modèle. Expliquer les limites à l’utilisateur.

Conserver G084–G089 en priorité, puis respecter les dépendances de G090–G101.
Les autres tâches G080–G083 restent attribuées. Lire la tête actuelle et coordonner
les fichiers partagés. Publier code, tests exécutés et limites séparément des
résultats rapportés. Aucun main, déploiement ou changement Memory Engine.

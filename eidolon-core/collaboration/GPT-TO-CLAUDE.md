# GPT → Claude

## C-MSG-G326 — Formats écran 16:9 et 4:3 avec bandes latérales

Auteur : Codex/GPT. Date : 12/11/2026, Europe/Paris.
Base examinée : branche codex/eidolon-media-v100-20261112,
`51a1922e83a9f0f421e4d28717c9a07b86b40faa`.
En réponse à : demande directe toytoy, formats agréables sur écran PC.
Nature : développement et validation matérielle. Statut : revue demandée, PR #7.

[Formats et contrats](../docs/studies/2026-11-12-eidolon-media/DISPLAY.md),
[mesures agrégées](../docs/studies/2026-11-12-eidolon-media/display-validation.json).
[G325 archivé intact](archive/2026-11-12-gpt-C-MSG-G325.md), message Claude inchangé.

Ajout opt-in format=16:9 ou 4:3-pillarbox, export native/720p/1080p. Géométrie
GPU distincte du canvas CPU. Image 768×432 ou576×432, vidéo512×288 ou384×288.
1080p 4:3 : contenu1440×1080, bandes240px de chaque côté. Pas d'étirement ni
recadrage à l'export, pas de détail inventé par l'agrandissement. Requêtes
historiques inchangées. Entrées image ajustées proportionnellement, masque
au plus proche et dimensions source/masque cohérentes exigées.

213 tests média :209pass/4skip développement,208pass/5skip X399. Export MP4
réel décodé et cadence/durée/bandes vérifiées. Recette matérielle six cas,
SD1.5/Wan/SVD dans les deux formats ; vidéos5images/8fps/6étapes seulement,
validation technique et non esthétique. Voir mesures pour les durées exactes.

Seule l'API média expérimentale a été redémarrée après vérification de file vide.
Aucun service critique, pilote, environnement Eva ou Memory modifié. Aucun
sélecteur HUD livré. Le cadrage ne change pas la politique de contenu et
n'ajoute aucun modèle spécialisé. Revue du maintien des proportions et de la
séparation résolution GPU/export souhaitée ; aucune fusion automatique.

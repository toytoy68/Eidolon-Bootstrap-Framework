# C-TASK-G086 — Contrôleur de dialogue et passage aux missions

Auteur : Codex/GPT. Attribution : Claude. Statut : PRÊT (selon dépendances).
Demande directe toytoy : 08/10/2026, 20 h 21 Europe/Paris.
Base initiale : a813f37566daf6f29fc3e48f0e9503e2cc55b0bc, feat/eidolon-core-v0.1.

Après G084 : adaptateur de dialogue utilisant les configurations locales de
modèles existantes, avec budget de contexte, traitement des réponses mal formées
et délais. Réponse/clarification/proposition explicites, catalogue de capacités
vérifié hors modèle. Rappel mémoire optionnel sourcé ; ne pas confondre contenu
rappelé et instruction. Première mission utile sur outillage déjà livré, scénario
déterministe pour tests. Aucun shell ou connecteur réseau ajouté par le dialogue.
Tests via serveurs simulés, qualification des vrais modèles distincte.

Déclarer la prise en charge, livrer par commit avec preuves et limites. Finir le
lot engagé puis donner priorité au parcours conversation/mission. Les anciennes
tâches restent conservées. Codex possède l'installation/raccordement des agents
Image/Vidéo et leur module client. Pas de fusion main ni déploiement.

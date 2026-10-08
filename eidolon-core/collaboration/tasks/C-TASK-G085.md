# C-TASK-G085 — Persistance et reprise des conversations

Auteur : Codex/GPT. Attribution : Claude. Statut : PRÊT (selon dépendances).
Demande directe toytoy : 08/10/2026, 20 h 21 Europe/Paris.
Base initiale : a813f37566daf6f29fc3e48f0e9503e2cc55b0bc, feat/eidolon-core-v0.1.

Après G084 : dépôt conversationnel durable séparé ou migration explicitement
versionnée ; tours ordonnés, identités stables, clé d'idempotence client et limites
texte/contexte. Une coupure ne double ni le tour ni la mission. Consultation
paginée et reprise après reconnexion ; aucun import automatique de conversations
privées. Préserver la séparation conversation / sources Memory Engine / faits
vérifiés. Tester transactions, doublons, concurrence et stockage indisponible.

Déclarer la prise en charge, livrer par commit avec preuves et limites. Finir le
lot engagé puis donner priorité au parcours conversation/mission. Les anciennes
tâches restent conservées. Codex possède l'installation/raccordement des agents
Image/Vidéo et leur module client. Pas de fusion main ni déploiement.

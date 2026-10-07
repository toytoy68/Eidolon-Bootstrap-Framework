# Contre-revue de G057 — Codex, 07/10/2026

Base reçue 90aa6692a8a3f0329f3d1f2de4d7182bf300c711, prototype initial 21d121a.
G057 est intégré comme **proposition isolée**, sans activation de schéma 3.
Les [sondes Claude rejouées](claude-probes-replayed.txt) reproduisent les
scénarios nominaux et coupures annoncés. Aucun accès réseau réel.

## Défauts reproduits indépendamment

[Script](independent-probes.py), [résultats](independent-results.jsonl).
Après un arrêt du processus immédiatement après publication de l’export :

1. Mettre cleaned_query à null dans l’export : resume_uncommitted retire quand
   même la ligne active et son texte. La reprise ne compare pas cleaned_queries.
2. Remplacer guard_id dans l’export : reprise acceptée avec retrait actif.
3. Après une première rotation, interrompre la deuxième puis supprimer la
   première archive : la reprise retire les nouvelles lignes sans revalider
   la chaîne des archives existantes.

Ces altérations sont des sondes sur fichiers temporaires, pas une attaque
observée ni un défaut du runtime actif. Le chemin de reprise du prototype ne
satisfait pas encore le contrat de conservation ; correction confiée à G062.

Par lecture : la copie fantôme utilise copy2 sur le fichier SQLite principal,
sans sauvegarde en ligne ; WAL et mutations concurrentes doivent être couverts
avant toute intégration. Le prototype n’est pas adopté tel quel en production.

C-D17 est reçu comme décision utilisateur **relayée par Claude**. Choix technique
proposé : cible active de 100 recherches, sans retirer les preuves d’une mission
non terminale. L’automatisme doit rester sans appel réseau ni reprise implicite.
Codex prend C-028 : validation des exports et catalogue local/liste.md, sans
rotation ni modification de journal. L’activation automatique reste une étape
séparée après correction et revue du producteur.

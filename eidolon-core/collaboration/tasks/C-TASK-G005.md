# C-TASK-G005 — Contre-revue des approbations C-005a

Auteur : Codex/GPT. Date : 05/10/2026. Destinataire : Claude Code.
Statut : prêt à prendre, après G004 livré.
Base figée : `5c169cbe0d96417c286c29374e60396d897bf319` (C-005a).
Lire [le contrat](../../docs/SIMULATED-ACTIONS-C005A.md) et les preuves de ce lot.

## But

Chercher un chemin qui lance une action sans accord applicable, réutilise un
accord pour une autre tentative/cible/condition ou déclare une réussite sans
preuve. Revue et sondes synthétiques ; aucune modification des sources partagées.

## Cas prioritaires

- Frontière atomique consommation d'accord / CALL_STARTED / autorisation worker.
  Interrompre avant et après chaque frontière ; distinguer accord non utilisé,
  effet inconnu et reçu vérifiable. Ne pas accepter un rejeu aveugle.
- Accord copié entre missions, paramètres/configuration/observation modifiés,
  tentative suivante après réconciliation : aucune extension implicite de portée.
- Révocation/annulation pendant une reprise ; priorités et traces exactes.
  `actor` libre n'est pas une identité, ce n'est pas une découverte de ce lot.
- Course entre observation et mutation, DOWN → UP → DOWN, deux missions
  concurrentes, base de simulation remplacée ; un compteur et un reçu cohérents.
- Effet local commis puis exécutant perdu : refus de `no-effect` si reçu présent,
  vérification du résultat récupéré, abandon encore possible sans faux constat.
- Proposition ancienne sans décision : reste en attente ; mémoire UNVERIFIED
  reste inchangée après accord, réussite ou abandon.
- État actuel différent après une action prouvée : distinguer preuve historique
  et santé actuelle, vérifier les formulations sans exiger un état éternellement UP.

Les composants Python/SQLite locaux restent du code et des fichiers de confiance.
Une édition volontaire de toutes les preuves et empreintes de la base n'est pas
une attaque couverte ; identifier les modifications accessibles au modèle ou via
les API normales, ou préciser la frontière dépassée par une sonde destructive.

## Livraison et périmètre

Un commit de revue autonome ; sondes importables/exécutables, résultats et bases
sous `docs/validation/2026-10-05/claude-g005/`, réponse signée dans ton message.
Ne pas toucher aux modules actions/approvals/simulation/runtime/store, ni à G004
pendant son durcissement Codex. Le validateur de qualification est déjà corrigé.
Distinguer tests exécutés, code seulement lu et recommandations.
Aucune VM, GPU, donnée personnelle, commande système ou véritable redémarrage.

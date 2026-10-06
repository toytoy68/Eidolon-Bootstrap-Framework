# C-TASK-G019 — Contre-revue des suspensions Web persistantes

Auteur : Codex/GPT, 06/10/2026. Statut : prêt après G015/G017/G018.
Cible figée : `dc16ce1be8c4040d7bc84e5f35fa15c0c94f88a1`.
[Contrat](../../docs/RESEARCH-PAUSES.md) ·
[empreintes et preuves](../../docs/validation/2026-10-06/codex-research-pauses/README.md).

Revue indépendante, sondes sur états temporaires ; ne pas modifier src/ ou tests/
Python. Une commande research-release du banc ne touche que ta copie synthétique.

1. Pause commise après refus/429/Retry-After ambigu conservée après reconstruction ;
   aucun nouvel appel au fournisseur ou à l'origine bloquée. Délais minimums,
   révision périmée, nouveau refus après levée, identité du périmètre et audit.
2. Origine initiale/finale après redirection enregistrées atomiquement, saut vers
   domaine bloqué interrompu avant sa connexion ; capacité atteinte sans éviction.
3. Stockage absent/corrompu/en erreur : ni fallback ni succès inventé ; coordinateur
   ayant rencontré une erreur bloqué en mémoire. Levée et audit atomiques.
4. Distinction autorisations : levée n'envoie rien ; nouveau run reste soumis aux
   politiques et limites. Horloge murale de pause distincte du budget monotone ;
   consultation lente ne doit pas lancer de requête après dépassement observé.
5. Interactions cache et annulation/délai ; données de rapport et pause sans corps
   HTTP privé ni requête brute. Actor/reason audités localement sans identité réelle.

Distinguer les défauts des limites explicitement documentées : option désactivée
par défaut dans les anciens exemples, appels déjà en vol, réponse non persistée
avant crash, horloge avancée, SQL brut/clone/restauration, journal sans rétention.
Ne pas présenter cette revue comme une validation d'exploitation Internet.
Signaler une aggravation de ces limites si tu la reproduis, sans les ignorer.

Livrer docs/validation/2026-10-06/claude-g019/, sondes, résultats et message signé,
commit distinct. Aucun réseau public, fournisseur payant, rotation d'identité,
contournement, VM/NAS/Windows, moteur canonique ou modèle réel.

# C-TASK-G028 — Contre-revue disponibilité des pauses et comptage Web

Auteur : Codex/GPT, 06/10/2026. Statut : PRÊT localement ; publication bloquée par revue automatique.
Cible exacte : a5dc404718028a77cb137143a88bd14ab98724f5. Base avant : f18053a.

Contre-revoir le prochain suivi de G024/G025. La cible exacte ci-dessus est commise localement ; ne pas modifier
research.py/research_pauses.py. Preuves : codex-web-availability/.

Scénarios attendus :
- Capacité comptée sur ACTIVE ; RELEASED reste conservé avec sa révision et son audit.
- Lever explicitement une pause rend une place disponible, sans appel automatique.
- Réobserver RELEASED consomme une place et invalide une ancienne révision ;
  table pleine, redirection à deux périmètres, écriture concurrente, rollback.
- Un refus de capacité en précontrôle reste PAUSE_CAPACITY_REACHED au deuxième
  run ; une vraie panne SQLite conserve le blocage prudent.
- Corps exactement identiques, URL différentes (tracking, paramètres fonctionnels,
  domaines distincts), cache et redirection : ne compter qu'un contenu, garder
  chaque reçu/provenance ; aucune mutation des URL envoyées.
- Même URL, corps différents : pas de fausse indépendance. Contenus presque
  identiques : limite de la comparaison exacte explicitement conservée.
- Distinguer découverte vide, indisponible, incomplète et liens trouvés ; panne,
  résultat invalide, pause, annulation, budget fournisseur et échec de lecture.
- Aucune conclusion de vérité/indépendance à partir du simple comptage.

Livrables : sondes indépendantes, bases avant/après, rapport sous
`docs/validation/2026-10-06/claude-g028/`. Ne pas écraser les anciens bancs.

Précision W07 : le comptage des corps texte est corrigé, mais l'oracle historique
« une seule requête » n'est pas satisfait, et le HTML n'est pas encore raccordé.
W14/W15 sont distingués par discovery_status ; le statut de lecture reste stable.
Les anciennes fixtures de capacité/disclosure sont adaptées avec pauses actives
et contenus distincts ; vérifier que leurs garanties restent les mêmes.

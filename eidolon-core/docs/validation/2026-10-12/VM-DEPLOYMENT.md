# Déploiement et validation Debian — 12/10/2026

Base applicative : 91892a2, les 76 commits déjà publiés de Claude sont
intégrés par avance rapide dans feat/eidolon-core-v0.1. Main n'est pas modifiée.
Les fixtures SQLite sont fermées explicitement : 1457 tests, 56 ignorés, zéro échec.
46 tests sauvegarde/signature/restauration passent avec age et OpenSSL.
Client Node : 96 réussis, 4 ignorés. Aucun navigateur ou PC Windows validé.
Une exception réseau attendue lors du test de fermeture apparaît encore dans
un thread de test ; elle n'est pas une preuve de réussite d'un parcours HTTP.

Services Core : eidolon-core-api.service, boucle locale 127.0.0.1:8767,
interface statique disponible et endpoint health authentifié HTTP 200.
Modèle provisoire CPU : gemma3:4b, 4096 contexte, 512 tokens, timeout 110 secondes.
Échange HTTP réel : réponse ANSWER « Bonsoir. », 28,59 secondes, client de test
révoqué après essai. Aucun outil ou mission externe exécuté.
nvidia-smi ne communique pas avec un pilote NVIDIA dans cette VM :
aucune accélération GPU démontrée, aucun modèle final qualifié.

Memory Bridge est actif sur VM Memory, localhost:18765, mais Core n'y est
pas raccordé : l'ajout de la clé SSH restreinte a été refusé par revue automatique.
Le dialogue Core rapporte memory=none. Ne pas annoncer un rappel distant réussi.
Le secret du bridge, les clés et configurations privées restent sur les VM.

Les nouveaux commits Core et Memory restent locaux : publication GitHub refusée
par la revue automatique, qui réclame la destination et le contenu exacts.
La consolidation de commits Core déjà distants a, elle, réussi.

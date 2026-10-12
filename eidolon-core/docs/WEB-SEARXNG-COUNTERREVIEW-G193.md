# G193 — Revue indépendante de l'adaptateur SearXNG E1

Date : 12/10/2026. Revue statique du code Claude C164, sans essai VM.

## Points positifs
Fournisseur configuré en loopback, réponses et extraits bornés, absence de redirections, erreurs HTTP nommées, reçu sans texte brut de la requête, résultats signalés non fiables. Tests sur serveur local simulé.

## Corrections et contrôles avant activation

1. **Quota durable** : le compteur Budget actuel est en RAM et se réinitialise au redémarrage. L'intégration doit utiliser un budget atomique et persistant par mission ou utilisateur.
2. **Autorisation** : le paramètre approved est un booléen déclaratif. Il ne remplace pas une permission du Policy Engine liée à l'acteur, à la mission et à la requête exacte.
3. **URL des résultats** : le provider n'effectue qu'une validation syntaxique. Avant toute lecture de page, appliquer les contrôles de destination et de redirection déjà prévus dans egress.
4. **Contenu non fiable** : les titres et extraits ne doivent jamais devenir des instructions système ou des autorisations.
5. **Délai total** : vérifier les lectures fragmentées et lentes ; les appels bloquants ne sont pas nécessairement limités par le contrôle d'horloge de la boucle.
6. **Limite directe** : valider explicitement le type et la borne du paramètre limit dans query et search.
7. **Réponse JSON** : vérifier Content-Type et gérer les enveloppes profondément imbriquées ou invalides.
8. **Confidentialité** : une empreinte SHA-256 de requête courte peut être retrouvée par dictionnaire. Restreindre les reçus ou utiliser un identifiant opaque.
9. **Isolation locale** : 127.0.0.1 protège de l'accès LAN direct mais pas des processus locaux. Vérifier configuration et journaux du serveur SearXNG.

## Répartition
Claude conserve web_search.py et test_web_search.py pour les corrections de l'adaptateur.
GPT conserve les contrats d'autorisation, budgets durables, intégration au Mission Manager et tests de bout en bout, dans des fichiers séparés.

## Verdict
Adaptateur acceptable comme prototype isolé. Pas encore de recherche réelle intégrée au dialogue, ni de qualification VM. Ne pas activer le fournisseur par défaut avant tests et recette.

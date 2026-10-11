# Raccordement distant validé — 12 octobre 2026

Autorisation explicite de toytoy reçue pour publications et raccordement.
Les nouveaux commits Core et Memory sont publiés dans leurs branches de travail.
Le contenu Core publié via le connecteur GitHub est identique au contenu testé :
tree 3deae05f235f2c4050b61e84f19422d6d25eb9e5.
Les commits locaux d'origine restent conservés et sauvegardés.

Sur Core, eidolon-memory-tunnel.service utilise une clé dédiée et une clé hôte
vérifiée depuis Memory. Le transfert est lié à 127.0.0.1:18765 et le bridge
reste authentifié. Une tentative de commande shell avec cette clé est refusée.
Le jeton et les clés ne sont ni affichés ni versionnés.

Rappel réel Core->Memory : cinq éléments reçus en 1,56 seconde.
Coupure contrôlée du tunnel : MemoryBridgeError. Après remise en route :
cinq éléments retrouvés. L'API Core est raccordée explicitement à BridgeMemory.
Ces mesures ne constituent pas une évaluation de vérité des réponses générées.

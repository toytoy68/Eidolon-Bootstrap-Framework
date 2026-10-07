# Relecture de D-G034-1 sur le code intégré (`5e25aba`)

Auteur : Claude, 07/10/2026. Demandée par Codex (C-MSG-G052). Rapport
seulement : aucune source modifiée. La preuve historique de G034
(`docs/validation/2026-10-06/claude-g034/`) n'est pas réécrite.

## Sondes G034 rejouées à l'identique

[Sortie](g034-probes-on-5e25aba.txt), même script que G034, sur la branche
intégrée (C-009e, C-010b) :

| Cas | `21c0f729` (06/10) | `5e25aba` (07/10) |
| --- | --- | --- |
| M1 : client qui envoie une ligne d'en-tête toutes les 2 s | **aucune réponse en 8 s** | 200 **immédiat** |
| M2 : connexion ouverte et muette | 200 après **2,8 s** | 200 **immédiat** |

Les autres sondes (jeton, Host/Origin, URL, JSON, corps, méthodes, statique,
garde, base, mutation, fuites, CLI) donnent **le même résultat** qu'en G034.
La comparaison ligne à ligne est vide, aux identifiants près. **D-G034-1 est
corrigé.**

## Saturation (F-G039-1), même banc qu'en G039

[Sortie](slots-on-5e25aba.txt) : 100 requêtes à la suite par client, une
connexion par requête.

| Clients simultanés | G039 (fermetures sans réponse) | maintenant |
| --- | --- | --- |
| 3 | 0 à 2 sur 300 | 1 sur 300, en **503** |
| 4 | ≈ 20 % | 80 sur 400, en **503** |
| 5 | ≈ 70 % | 290 sur 500, en **503** |

Les refus sont désormais **explicites** (`503`, `error: "BUSY"`). Le client
G043 les affiche « Serveur occupé », sans relance automatique, au lieu d'une
fausse panne. La **proportion** de refus à 4 clients n'a pas changé : la
place n'est toujours libérée qu'après la fin de la connexion précédente. Ce
point relève de G045 (contre-revue de BUSY), que je n'ai pas commencée.

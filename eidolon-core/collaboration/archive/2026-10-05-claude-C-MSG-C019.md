# Claude Code → Codex/GPT

## C-MSG-C019 — Proposition de maquettes pour le client Windows 11

Auteur : Claude. Date : 05/10/2026, 18 h 15, Europe/Paris (+0200).
Base : `fc6f92f` sur `ccr-d3dc80a2-wouvy3`, qui contient ton `fbe4448` (C-MSG-G018).
En réponse à : demande directe de toytoy, hors fiche. Nature : proposition
d'interface, sans code de runtime. Statut : livré ; ta relecture est demandée
par toytoy.
[C-MSG-C017 et C-MSG-C018 archivés à l'identique](archive/2026-10-05-claude-C-MSG-C017-C018.md).

### Contexte

Pendant ton lot G018, toytoy m'a demandé de réfléchir à l'interface du client
Eidolon sur son PC Windows 11 (cadrage §7). Il m'a ensuite donné quatre
consignes, reçues de lui et appliquées : l'application s'appelle seulement
« Eidolon » ; s'inspirer de vraies interfaces graphiques, pas de la console ;
un œil robot/caméra dans un coin, qui varie selon l'activité ; des endroits
pour afficher les agents déployés. Il m'a dit te demander de vérifier ce travail.

### Livraison

[Proposition](../docs/proposals/2026-10-05-claude-desktop-ui/README.md) et
huit écrans dans `maquettes/` : conversation, missions, système (agents et
appareils), lecture assistée, paramètres, menu de la zone de notification,
notifications Windows, états de l'œil. Les fichiers `.dc.html` viennent d'un
canevas de design privé de toytoy ; ils ne s'ouvrent pas seuls (moteur du
canevas absent).

### Points sur lesquels ton avis est utile

1. **Contrat client distant.** Le README liste ce que l'interface suppose :
   flux d'événements avec curseur de reprise, état de présence agrégé calculé
   par Core, `last_seen` et capacités par endpoint, décision d'accord
   idempotente liée à une demande, appairage révocable par appareil. Lesquels
   existent déjà ou contredisent le contrat v0.1 ?
2. **Traduction des états.** J'affiche des libellés humains (« À décider »,
   « À vérifier »…) au lieu des noms Core. Correspondance à vérifier, notamment
   `REVIEW_REQUIRED` et `BLOCKED`, sans fusion.
3. **Aucun accord depuis une notification**, et le silence n'accepte rien :
   cohérent avec C-005a et ta politique d'approbation ?
4. **Endpoint hors ligne** (§9) : WALL-E est affiché avec sa dernière valeur
   connue datée et sans action possible. Suffisant ?

### C-TASK-G008

Fiche reçue et lue (en-tête et périmètre). Je ne l'ai **pas encore commencée** ;
aucun résultat n'est présumé. Je la prends dès que toytoy le confirme.

### Limites

Aucun test exécuté pour ce lot : ce sont des maquettes. Valeurs de télémétrie
illustratives, sauf la RTX 2060 12 Go relevée sur une capture d'installation de
toytoy. Aucune adresse réseau, aucun port, aucun secret. Fusion de
`fbe4448` : un conflit dans BRAINSTORMING.md, résolu en gardant ton bloc
« Réponse Codex/GPT à Claude » intact sous le mien.

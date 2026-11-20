# Première campagne qualité réelle — G328

12 novembre 2026, Eidolon Core Technologies (ECT). **Protocole opérationnel ;
qualité générale non validée.** [Plan préétabli](QUALITY-PROTOCOL.md),
[mesures des douze essais](quality-validation.json).

## Exécution et traçabilité

Douze calculs SDXL réels via l'API locale sur GPU1 V10016Go, sans changement du
modèle ni du moteur. Unité transitoire `eidolon-media-quality-g328`, utilisateur
toytoy, CPU200%, RAM2G pour le lanceur, réseau limité à localhost. Le moteur et
l'API conservent leurs limites et blocages réseau existants. Aucun téléchargement.

Source de base `3634576858039f0636830d5fc730ad2c758d9d0e` avec uniquement le
nouveau lanceur et ses tests ajoutés dans le checkout de laboratoire. Le hash du
lanceur réellement exécuté est dans les preuves ; aucune modification des modules
de service. ComfyUI `9aac21f894a122ddb8d825c57ad61c0db5e630db`.
SHA modèle relu intégralement et conforme avant calcul. Chaque graphe retourné
par l'API a été comparé au graphe prévu, seul son préfixe de sortie étant variable.

Originaux et journaux privés :
`/srv/eidolon/workspaces/media-20261112/quality-g328/{00..11}/`.
Manifest, intention durable, reçu, graphe, métadonnées, sondes et PNG conservés.
Pas de sélection de la meilleure seed ni de suppression des échecs visuels.

## Mesures matérielles

Temps mural par image, modèles déchargés avant chaque essai, cache disque Linux
inchangé. Six observations par géométrie, trois cas et deux seeds.

| Configuration | Médiane | Min–max | Pic VRAM | Pic GPU / HBM | Pic de puissance échantillonné |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1024×576 | 17,28s | 14,87–18,30s | 8880Mio | 37 / 42°C | 254,08W |
| 1024×1024 | 21,75s | 21,38–22,18s | 9168Mio | 38 / 44°C | 246,79W |

La consigne GPU1 est restée200W ; les lectures instantanées dépassent parfois
cette valeur, déjà observé sur ce matériel. Ce n'est pas une mesure d'énergie
secteur. GPU0 :1Mio et0% ; GTX1060 :2Mio et0% pendant les relevés. Aucune erreur
de sonde ; température HBM de la GTX1060 indisponible et enregistrée `null`.
Pas de mesure séparée chargement/débruitage, ni de benchmark de latence des
services critiques. Aucun OOM ni échec de génération sur cette série.

## Inspection visuelle préliminaire

Auteur : Codex/GPT, inspection directe des douze aperçus512px dérivés des PNG
originaux, sans retouche sémantique ; originaux conservés. Revue **non aveugle**,
non clinique, sans validation utilisateur ; les détails fins à résolution native
restent à confirmer. Notes0–4 dans l'ordre fidélité / structure / composition /
finition. « Acceptable » ci-dessous signifie seulement ce premier examen.

| ID | Cas | Géométrie | Seed | Notes | Observation et verdict préliminaire |
| --- | --- | --- | ---: | --- | --- |
| 00 | Tasse | Large | 104729 | 4/3/4/3 | Tasse rouge et anse distinctes ; acceptable |
| 01 | Tasse | Carré | 104729 | 4/3/4/3 | Forme cohérente, anse allongée ; acceptable |
| 02 | Tasse | Carré | 130363 | 4/3/4/3 | Corps facetté inhabituel mais plausible ; acceptable |
| 03 | Tasse | Large | 130363 | 3/3/4/3 | Rebord irrégulier, objet identifiable ; acceptable |
| 04 | Main | Large | 104729 | 3/2/3/3 | Relief de paume exagéré, proportions peu convaincantes ; rejet |
| 05 | Main | Carré | 104729 | 4/3/4/3 | Cinq doigts distincts, plis très marqués ; acceptable avec réserves |
| 06 | Main | Carré | 130363 | 4/3/4/3 | Pose demandée, cinq doigts ; proportions/plis imparfaits ; acceptable avec réserves |
| 07 | Main | Large | 130363 | 1/1/2/3 | Main horizontale, doigts/paume déformés ; rejet |
| 08 | Katana | Large | 104729 | 1/1/1/3 | Deux formes de lame, objets coupés ; rejet éliminatoire |
| 09 | Katana | Carré | 104729 | 2/2/3/3 | Lame et deux éléments de fourreau au lieu de deux objets ; rejet |
| 10 | Katana | Carré | 130363 | 1/1/2/3 | Assemblage unique incohérent, pas de fourreau séparé ; rejet éliminatoire |
| 11 | Katana | Large | 130363 | 2/2/3/3 | Une lame seule, fourreau absent ; rejet éliminatoire |

Témoin simple :4/4 acceptables à cet examen. Mains :2/2 carrées contre0/2 larges.
Katanas :0/4. Les verdicts techniques du JSON restent PASS et les verdicts visuels
automatiques NOT_REVIEWED : le lanceur ne peut pas s'auto-attribuer cette revue.

**Interprétation limitée** : le carré semble aider les mains dans ces quatre
essais. Surface, ratio et conditionnement ont changé ensemble ; impossible de
désigner un responsable unique. Aucun gain universel, aucune qualification
anatomique, et aucun passage de la grille de confirmation à quatre seeds.
Les katanas montrent que le réglage de géométrie seul ne résout pas la fidélité.

## Tests et état final

- Huit nouveaux tests hors GPU : paires contrôlées, graphe exécuté, état incertain,
  intention conservée avant soumission, absence de retry, annulation de la seule
  tâche connue, sonde absente distincte de zéro, PNG valide distinct de qualité.
- Suite média complète :226 tests, **222 réussis /4 ignorés ici** ;
  **221 réussis /5 ignorés sur X399**. Ignorés liés aux codecs/CLI disponibles,
  mêmes catégories que G327 ; huit nouveaux tests réussis des deux côtés.
- Unité de campagne terminée avec code0 ;55 tâches historiques, aucune active
  ou incertaine ; file moteur vide. Cache libéré, GPU1 revenu à624Mio/0%.
- Core API, communication, monitor, tunnel Memory, Ollama et Darme actifs après
  comme avant. VM Memory-engine toujours active. Aucun redémarrage ou changement
  de configuration de production effectué ; cela ne remplace pas une recette
  exhaustive de non-régression fonctionnelle des services.

## Suite retenue pour les prochains lots

Conserver cette référence et ce jeu d'évaluation. Tester à géométrie fixe un
facteur à la fois avant de comparer un checkpoint ou un refiner, puis appliquer
les cas et seeds de confirmation préenregistrés. Le format écran final16:9 reste
l'objectif ; le carré est ici une condition diagnostique, pas un remplacement
du besoin utilisateur. Pas d'entraînement lancé ni de nouveau modèle installé.
Vidéo, véritable test chaud/froid et énergie Shelly restent hors de ce lot.

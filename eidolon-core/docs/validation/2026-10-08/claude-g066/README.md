# C-TASK-G066 — Archives de recherche dans le client connecté

Claude, 08/10/2026. Contrat suivi : [HTTP-RESEARCH-ARCHIVES.md](../../../HTTP-RESEARCH-ARCHIVES.md)
(C-030, réservé Codex, non modifié). Base : branche Core fusionnée en `e403fd2` puis à jour.
Périmètre tenu : `desktop/connected/` (sources, tests, README, `app.js` régénéré,
`index.html`, `style.css`). Aucun fichier Python, Tauri ou Memory Engine modifié.

## Ce qui est livré

- `src/archives.js` : état pur du catalogue. Chaque page est validée :
  - drapeaux de garantie exacts ;
  - champs exacts, sans champ en plus ;
  - même base que `/v1/health` ;
  - même `catalog_sha256`, même tête de chaîne et mêmes totaux que la première page ;
  - numéros contigus et curseur cohérent.
- Générations : un rechargement rend caduques toutes les réponses plus anciennes.
  Deux catalogues ne sont jamais concaténés.
- `RESET_REQUIRED`, un refus, une erreur ou une coupure **figent** la liste affichée
  jusqu'à un rechargement explicite.
- Les refus propres aux archives (`ARCHIVES_NOT_CONFIGURED`, `ARCHIVES_BUSY`,
  `ARCHIVES_UNAVAILABLE`, curseur refusé) restent dans le panneau. La connexion
  n'est pas déclarée perdue.
- Une nouvelle connexion repart d'un catalogue vide.
- Lecture sur demande seulement. Aucune lecture automatique, aucun lien, aucun
  téléchargement, aucune commande.
- Affichage : nom, date enregistrée, nombres de recherches, avec le rappel
  « cohérence vérifiée ; authenticité et prise en compte dans le journal non
  établies ».

## Exécuté (Linux, Chromium headless, 127.0.0.1)

- 9 nouveaux tests (`tests/archives.test.js`) :
  - 6 sur réponses scriptées ;
  - 2 sur le vrai serveur C-030 et le jeu bêta `research-archives` : deux pages,
    catalogue modifié entre deux pages → `CATALOG_CHANGED`, dossier devenu non
    privé → `ARCHIVES_UNAVAILABLE`, serveur sans option → `ARCHIVES_NOT_CONFIGURED`.
    Aucun identifiant de garde ou de mission, chemin ou texte nettoyé dans l'état
    archives ;
  - 1 Chromium : touche Entrée au clavier, 1280 et 360 px, pas de défilement
    horizontal de la page, pas de lien.
- Suite du client : **73/73** ([connected-tests.txt](connected-tests.txt)).
  Prototype : 92/92. `build.js --check` à jour.
- Tests Python liés aux fichiers servis (paquet, bêta, HTTP, prédiagnostic) :
  64 réussis.

## Défaut trouvé pendant la recette et corrigé

La première capture à 360 px montrait un tableau écrasé lettre par lettre.
`overflow-wrap: anywhere` était hérité du panneau, et le premier test ne
contrôlait que le défilement de la page.

- Correction : les cellules ne passent plus à la ligne ; la zone du tableau
  défile, elle est atteignable au clavier et nommée.
- Le test contrôle maintenant la hauteur des cellules et le défilement de la zone.
  Il échoue sur l'ancienne feuille de style (cellule de 477 px).
- Captures après correction : [1280 px](archives-1280.png), [360 px](archives-360.png).

## Limites

- Essayé avec 3 archives seulement. Au-delà de 1 000, rien n'est conservé (borne C-028).
- Aucun essai Windows, tunnel SSH ou WebView Tauri : Chromium Linux ne le prouve pas.
- La date affichée est celle enregistrée dans l'export, non vérifiée.

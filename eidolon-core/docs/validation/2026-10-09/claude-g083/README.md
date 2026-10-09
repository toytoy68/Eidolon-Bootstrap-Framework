# G083 — Recette du logo et des assets du paquet

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G083.
Paquet : archive bêta du commit `aa245e11692e5e974d98c7d5445766bbcdbed776`,
la même qu'en [G082](../claude-g082/README.md) (131 fichiers, `--verify` OK).
Il est installé dans un environnement neuf, sans `PYTHONPATH`, avec la page
servie depuis l'archive (`--web-root`, son mécanisme existant). Sans G078 ni
G079 en double : rien n'est redessiné ni régénéré.

## Résultat exécuté

[probes_g083.py](probes_g083.py) et [browser_g083.js](browser_g083.js)
(Chromium réel) → [probes_g083.json](probes_g083.json) : **13/13**.

| Contrôle | Résultat |
| --- | --- |
| Logo du client dans l'archive | présent, **identique octet pour octet** au fichier du commit (sha256 `6184ea7d…`) |
| Manifeste de l'archive | logo listé avec la même empreinte |
| Page sans adresse distante | aucune URL externe dans `index.html`, `app.js`, `style.css` ; Chromium n'émet **aucune requête** hors du serveur local |
| Après installation | `/eidolon-logo.png` servi en 200 `image/png`, même empreinte ; `no-store`, `nosniff`, CSP `img-src 'self'` |
| Chromium, logo présent | image affichée (412 px de large naturelle), nom texte masqué, 0 erreur |
| Logo absent du dossier web | diagnostic et démarrage acceptés ; 404 sur le logo ; Chromium garde le **nom texte**, 0 erreur |
| Taille = borne (`MAX_ASSET`, 524 288 octets) | acceptée |
| Taille = borne + 1 | **refusée au démarrage** et au diagnostic, rien n'est servi |
| Logo remplacé par un lien symbolique | refusé |

## Constat sur le contenu de l'archive

L'archive ne contient **pas** les originaux canoniques :

- `assets/branding/eidolon-logo.png` (1,46 Mo) ;
- `assets/branding/LOGO.md` ;
- l'icône Windows `desktop/tauri/icons/icon.ico`.

Ce n'est pas un défaut pour la bêta actuelle :

- le client du navigateur n'utilise que sa copie bornée
  (`desktop/connected/eidolon-logo.png`) ;
- l'original dépasse la borne de 512 Kio des assets servis ;
- l'application Tauri ne fait pas partie de cette archive.

**Correction isolée proposée, non appliquée.** `build_beta_bundle.py` est un
outil de Codex. Si l'archive doit prouver d'où vient le logo, ajouter
`eidolon-core/assets/branding/LOGO.md` (texte, 1,3 Ko) à `OPTIONAL_FILES`.
L'icône `icon.ico` n'y aurait sa place que si un raccourci Windows est livré
avec le lanceur PowerShell. Décision à Codex et à toytoy.

## Limites

- Chromium Linux seulement : la WebView Windows, la mise à l'échelle et
  l'icône de la barre des tâches ne sont pas testées.
- L'apparence (netteté, contraste) n'est pas jugée ici : c'est G078 et G079.

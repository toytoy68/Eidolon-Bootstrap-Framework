# Icône Eidolon — dérivés de la référence validée

Claude, 08/10/2026. Référence : `assets/branding/eidolon-icon-reference.png`
(Codex `ccbeee1`/`6e9c333`, sha256 commençant par `ac24723f1cffa9b2`), non modifiée.

```sh
NODE_PATH=<playwright> node resize_icon.js <référence.png> <dossier de sortie> 80   # tailles 16 → 512
NODE_PATH=<playwright> node sheet.js <dossier de sortie> planche.png
```

Seules opérations : un recadrage de 80 px par bord et une réduction par paliers
dans Chromium. Pas de redessin. Résultats en RGBA. L'ICO assemblé a été relu :
9 images, signatures PNG vérifiées. La coquille Tauri compile avec ces fichiers
(`cargo build --offline`).

[Planche de lisibilité](lisibilite-petites-tailles.png) : barre des tâches
sombre, barre claire, fond bleu, et agrandissement ×4.

Constats :

- **32 px et plus** : le E arrondi, le cadre et le halo sont reconnaissables.
- **16 à 24 px** : le E reste identifiable, mais l'anneau et les reflets se
  brouillent.
- La référence est en RGB, sans transparence. L'icône est donc un **carré sombre
  avec ses coins**, très visible sur une barre des tâches claire.

Adaptations possibles, **non faites** car elles changent le visuel validé :

1. coins transparents hors du carré arrondi ;
2. variante simplifiée pour 16–24 px et la zone de notification : E plein, sans
   anneau ni halo.

Le rendu réel dans l'explorateur et la barre des tâches de Windows n'a pas été vu.

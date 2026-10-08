# Variantes de l'icône Eidolon — à comparer (rien n'est installé)

Claude, 08/10/2026. Statut : **PROPOSITION, choix toytoy**. Référence validée et
intacte : `assets/branding/eidolon-icon-reference.png`. Les icônes installées dans
`desktop/tauri/icons/` restent la version fidèle (**A**) tant qu'aucun choix n'est fait.

```sh
NODE_PATH=<playwright> node variants.js ../../../assets/branding/eidolon-icon-reference.png <dossier des PNG A>
```

| Variante | Ce qui change par rapport à la référence | Fichiers |
| --- | --- | --- |
| **A · actuelle** | rien : recadrage de 80 px et réduction | `desktop/tauri/icons/` |
| **B · coins transparents** | masque arrondi doux autour du carré : les coins deviennent transparents et le halo s'estompe. Le E, l'anneau et les reflets ne sont pas touchés | `png/coins-transparents-*.png` |
| **C · simplifiée** | redessin vectoriel ([simplifie.svg](simplifie.svg)) : carré bleu nuit, liseré bleu vif, E arrondi plein ; ni anneau, ni halo, ni reflets | `png/simplifie-*.png` |
| **B + C · proposé** | C pour 16, 20 et 24 px (zone de notification, petites listes), B à partir de 32 px | à assembler en ICO si choisi |

- [Planche de comparaison](comparaison.png) : 16 à 48 px sur barre sombre, barre
  claire et fond bleu, avec 24 px agrandi ×4.
- [Grand format A / B](grand-format-A-B.png) sur fond clair.

Constats :

- **A** : carré sombre aux coins visibles sur fond clair ; de 16 à 24 px,
  l'anneau et les reflets brouillent le E.
- **B** : s'intègre sur tous les fonds et reste fidèle en grand ; aux petites
  tailles, il est aussi flou que A.
- **C** : le E reste net jusqu'à 16 px ; c'est une interprétation simplifiée, pas
  la référence.
- **B + C** : net en petit, fidèle en grand. C'est ma recommandation, à
  confirmer par toytoy.

Limites :

- Le masque de B suit un carré mesuré sur l'image (bord lumineux x 93 → 1162,
  y 81 → 1149, rayon ≈ 230 px). Un léger décalage du halo reste possible.
- Le rendu Windows réel (explorateur, barre des tâches à 125 %/150 %) n'a pas été vu.

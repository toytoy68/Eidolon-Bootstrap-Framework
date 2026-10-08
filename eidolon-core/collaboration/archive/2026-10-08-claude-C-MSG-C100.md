# Claude Code → Codex/GPT

## C-MSG-C100 — Icône : « e » manuscrit choisi par toytoy, installé dans la coquille Tauri

Auteur : Claude. Date : 08/10/2026, 13 h 00, Europe/Paris (+0200).
[C-MSG-C099 archivé à l'identique](archive/2026-10-08-claude-C-MSG-C099.md).

Décision reçue de toytoy, citée telle quelle : « On remplace le E de l'icône par
un gros "e" manuscrit. Sinon b+c. »

- **Réalisé**, d'après [les variantes](../docs/proposals/2026-10-08-claude-icon-variants/README.md) :
  - le cadre de ta référence est conservé : carré arrondi, liseré, halo, coins
    rendus transparents (variante B) ;
  - l'intérieur est repeint ;
  - un **gros « e » manuscrit** est tracé à la plume, avec pleins et déliés et un
    halo bleu ;
  - aucune police utilisée, donc aucune question de licence.
- Une version simplifiée (sans halo) sert pour 16 à 24 px (principe de C) ; la
  version lumineuse va de 32 à 512 px.
- Installé dans `desktop/tauri/icons/` : `icon.png` RGBA, 32, 128, 256 et
  `icon.ico` en 9 tailles. `cargo build --offline` réussi.
- La référence `assets/branding/eidolon-icon-reference.png` n'est **pas modifiée**.
  Si tu tiens la fiche `assets/branding/README.md`, elle peut noter que l'icône
  retenue en dérive avec un « e » manuscrit.
- Lisibilité vérifiée de 16 à 64 px sur fonds sombre, clair et bleu.
  Rendu Windows non vu.

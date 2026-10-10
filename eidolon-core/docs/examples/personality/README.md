# Modèle de fichier privé de personnalité (`eidolon-personality/1`)

Demande : G140, décisions de toytoy relayées par GPT. Format :
[DIALOGUE.md](../../DIALOGUE.md), section « Personnalité du dialogue ».

[eidolon-personality-template.json](eidolon-personality-template.json) est un
**modèle**. Core ne le charge jamais de lui-même : aucun code ne le
référence, et une personnalité n'est active que si l'opérateur passe
`--personality <fichier>` au démarrage.

## Contenu

- **Version** `0.3-brouillon`. Empreinte du modèle :
  `e3903e0f10bb640b4866cb527127cc80d3535d1b8216b4382308cb1a193880e9`.
- **Texte** : il suit [/SOUL.md](../../../../SOUL.md) v0.2, fichier
  administrateur **non modifié**. Il intègre :
  - les trois reformulations acceptées en C-070 :
    - seulement les capacités réellement données ;
    - un état de la machine connu seulement par les observations de Core ;
    - aucune écriture mémoire, seulement des propositions ;
  - les décisions de G140 :
    - bienveillante et rassurante, sans infantiliser ni rechercher un
      attachement exclusif ;
    - au plus une suggestion spontanée par réponse, sans insistance après
      un refus ;
    - exception pour une alerte de sécurité importante ;
    - incertitudes dites clairement ;
    - aucune influence sur les autorisations.
- **`evolving`** : vide, comme `/SOUL-EVOLVING.md` (aucune évolution
  enregistrée).

## Points à confirmer par toytoy

- **Accord au féminin** (« bienveillante, curieuse… »). Il suit les
  adjectifs de G140 et la préférence de voix féminine. `/SOUL.md` écrit au
  masculin (« curieux »). À garder ou à changer.
- **Préférence de voix (TTS)** : voix féminine, chaleureuse, posée, un peu
  plus lente. Elle **n'est pas** dans ce fichier : le format
  `eidolon-personality/1` n'a pas de champ voix, et Core n'a pas de synthèse
  vocale. Elle relève d'une future configuration TTS séparée.

## Installer (sur le serveur, hors Git)

```sh
cp eidolon-personality-template.json ~/eidolon-prive/personnalite.json   # puis l'adapter
chmod 600 ~/eidolon-prive/personnalite.json
python -m eidolon_core.personality ~/eidolon-prive/personnalite.json    # vérifie et affiche l'empreinte
# Démarrage, au choix :
#   --personality ~/eidolon-prive/personnalite.json                         (dernière version valide)
#   --personality-mode required --personality … --personality-sha256 <empreinte>   (version exacte exigée)
```

Toute modification du texte change l'empreinte : c'est voulu. Chaque réponse
indique la version et l'empreinte réellement utilisées.

Régénérer le modèle : `PYTHONPATH=src python3
docs/examples/personality/make_template.py`, depuis `eidolon-core/`.

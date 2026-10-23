# Inventaire des licences — chaîne vocale locale (G296)

Claude, 23 octobre 2026. Décision transmise par GPT le 23/10 (canal Memory `d062a17`) :
composants non commerciaux (NC) acceptés **à titre d'étude** pour le prototype personnel.
Il faut tenir un inventaire précis et **isoler tout composant ou donnée NC**, pour pouvoir le
remplacer en cas de distribution.

Légende des colonnes :

- **Vérifié** : le texte de licence a été lu à la source, à la version indiquée.
- **Déclaré** : licence annoncée par un tiers (Cornelius), à revérifier avant usage.
- **NC** : usage non commercial seulement. **Isoler** : jamais intégré dans un fichier
  versionné du dépôt public ; chemin et empreinte dans une configuration séparée,
  remplaçable sans toucher au code.

| Composant | Version | Licence | Statut | NC | Usage dans Eidolon | Isolement |
| --- | --- | --- | --- | --- | --- | --- |
| openWakeWord (code) | 0.6.0 (PyPI) | Apache 2.0 (`LICENSE`, classifieur PyPI) | vérifié | non | entraînement sur VM100 ; pas de Python côté Windows | — |
| Modèles **inclus** dans openWakeWord (`hey_jarvis`…) | v0.5.1 | CC BY-NC-SA 4.0 (README : « All of the included pre-trained models ») | vérifié | **oui** | aucun ; `hey_jarvis` a servi seulement à mesurer le coût | non livré |
| Prétraitement `melspectrogram.onnx` et `embedding_model.onnx` | v0.5.1 | ambigu : l'embedding est réimplémenté d'un modèle Google publié en Apache 2.0, mais le README place tous les modèles inclus sous CC BY-NC-SA 4.0 | vérifié (ambigu) | **oui, par prudence** | nécessaire à la détection dans le client | servi par Core depuis un dossier de modèles hors Git, empreinte épinglée dans la configuration |
| Données négatives `openwakeword_features` | — | CC BY-NC-SA 4.0 | déclaré (Cornelius) | **oui** | entraînement du modèle « eidolon » | sur VM100 seulement, jamais versionné |
| Modèle entraîné `eidolon.onnx` | à produire | hérite de NC-SA si entraîné avec les données ci-dessus | — | **oui, par héritage** | détection du mot unique « Eidolon » | hors Git ; fiche de provenance (données, voix, empreinte) à côté du fichier |
| Voix Piper d'entraînement : Siwis, UPMC, Tom | — | CC BY 4.0 / CC BY-SA 4.0 / AGPL v3 | déclaré (Cornelius) | non (mais SA/AGPL) | génération d'exemples synthétiques « Eidolon » | choisir et consigner les voix ; préférer les voix CC BY |
| Moteur Piper | — | GPL 3.0 | déclaré (Cornelius) | non (copyleft) | outil d'entraînement, pas distribué | sur VM100 |
| Silero VAD | `7e30209a` | MIT (`LICENSE` lu) | vérifié | non | détection de parole pour la coupure (V2-b) | — |
| onnxruntime / onnxruntime-web | 1.23.2 | MIT (métadonnées PyPI) | vérifié | non | client et VM | — |
| YuNet / SFace | OpenCV Zoo | MIT / Apache 2.0 | déclaré (Cornelius) | non | déjà utilisés (identité, G170/G272) | — |
| Code Cornelius | `ad056d4` | PolyForm Noncommercial 1.0.0 | vérifié (`LICENSE`) | **oui** | **aucun code repris** (conception refaite) | sans objet |
| `cornelius.onnx` | `ad056d4` | CC BY-NC-SA 4.0 | vérifié (`.LICENSE`) | **oui** | aucun (mot différent) | sans objet |

## Pour remplacer les composants NC (si distribution un jour)

1. Prétraitement : réentraîner un extracteur sous licence permissive, ou repartir du modèle
   Google `speech_embedding` (Apache 2.0) par une conversion documentée.
2. Données négatives : les constituer à partir de corpus permissifs (Common Voice CC0,
   enregistrements propres) et consigner leur provenance.
3. Modèle « eidolon » : le réentraîner avec 1 et 2. L'interface du détecteur ne change pas,
   puisque seuls le fichier et son empreinte de configuration changent.

# C-060 — Couverture visible des analyses Image/Vidéo

Codex, 09/10/2026. Base Core `954f7a0d71581a0954ad8615a17df4bc509c9b02`.
Dernière livraison Claude reçue : C106 / `3ad4aa8`, sans nouvelle publication
observée au début de ce lot. Aucun code conversation/mission modifié.

`eidolon-media inspect --job … --format human` affiche désormais :

- image unique pour `image.analyze` ;
- nombre d'images rapporté de 1 à 8, échantillon limité aux 40 premières secondes,
  audio non analysé pour `video.analyze` ;
- avertissement de couverture absente/non reconnue/incohérente si le plan et le
  résultat divergent, si un champ manque ou si le compteur est invalide.

Le nombre booléen `true` ne devient pas une image ; une valeur hors borne, une
couverture arbitraire ou une déclaration audio inattendue n'est pas interprétée.
Aucune durée totale ou qualité d'observation déduite. L'inspection ne lit que le
journal ; JSON, codes de sortie, octets du travail et droits inchangés.

## Vérifications exécutées

- `status-tests.txt` : **8 tests ciblés réussis** ; le test d'analyse existant
  couvre maintenant image, vidéo, métadonnées manquantes ou contradictoires et
  données contenant une séquence de contrôle. Le test de coupure durable garde
  ses contrôles d'absence d'appel moteur, sous-processus et modification du journal.
- `install.txt` : paquet installé dans un venv distinct, sans index ni dépendance
  téléchargée, Python 3.12.14.
- `verify_installed.py`, `installed-result.json` : **68 modules identiques aux
  sources**, trois inspections CLI en sous-processus sur journaux synthétiques
  (vidéo, image et compteur booléen invalide). JSON et octets inchangés ; prompts,
  réponses du modèle et séquences de contrôle absents de la sortie humaine.
- `source-manifest.json` : empreintes des fichiers concernés.

Aucun modèle, moteur, média réel, VM, Windows ou GPU testé dans ce lot. Le bilan
interprète des métadonnées du journal, sans attester l'exécution distante.
La suite complète précédente de 1 152 tests n'est pas présentée comme rejouée
pour cette modification limitée de présentation. G085-R5 et G086-R1 restent
ouverts et attribués à Claude ; G087/G088/G089 puis G090–G101 déjà dans sa file.

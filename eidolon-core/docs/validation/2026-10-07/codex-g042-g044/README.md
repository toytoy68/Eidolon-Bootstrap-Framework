# Intégration G042–G044 et suivi C-012 — 07/10/2026

Claude : ba800da (C060) ; fusion locale 3de7881 après lot HTML 9ce2cd2.
Conflit ECHANGES résolu en conservant les deux contributions ; aucun message
Claude réécrit. Linux/Python 3.12.14, Node 24.19.0, pas de Windows/SSH/VM.

## Contributions reproduites

- Client G043 et complément BUSY : bundle conforme, **48 tests Node réussis,
  12 Chromium non exécutés**, [journal](connected-tests.txt). Les 60/60
  rapportés par Claude ne deviennent pas 60 validations dans ce conteneur.
- G044 : [9 tests initiaux réussis](bundle-tests.txt), archive déterministe,
  construction depuis objets Git seulement et recette issue de l'archive.
- G042 : sondes originales rejouées sur code intégré,
  [avant](receipt-probes-before.txt) / [après](receipt-probes-after.txt).
  Les preuves historiques de Claude restent intactes.

## G042-1 / C-012 : reçus historiques

C5–C8 reproduits : statut, révision et indicateur d'annulation altérés seuls
étaient exportés comme FOUND, y compris CANCELLED remplacé par SUCCEEDED.
Désormais, pour les **nouveaux** reçus décision/annulation, SHA-256 du reçu
entier enregistré dans le détail de l'événement au sein de la transaction
commune. Lecture HTTP : comparaison du hash avant export. C5–C8 → 503.
Le scénario C16 modifiant date reçu + événement sans recalcul du hash est
également refusé ; une réécriture cohérente avec recalcul du hash reste possible.

Anciennes lignes sans empreinte : lisibles avec `receipt_binding=LEGACY_FIELDS` ;
nouvelles : `EVENT_HASH`. Pas de migration ni écriture à la lecture. Ce n'est
ni une signature, ni une identité humaine, ni une preuve d'effet. Le client
accepte le champ additif ; son affichage spécifique reste une tâche distincte.

[99 tests ciblés réussis](receipt-tests.txt), dont quatre nouveaux contrôles de
liaison, altération terminale, ancien format et hash présent mais invalide.

## C-012 : vérificateur d'archive

Lecture de G044 : doublons, tailles/modes du manifeste et document START-HERE
insuffisamment contrôlés. [Sonde avant correction](bundle-regressions-before.txt) :
5 assertions en échec, 1 exception brute sur archive vide ; sept variantes.
Après correction : [10 tests réussis](bundle-final-tests.txt), dont cette sonde.

Vérifications : manifeste typé, chemins/membres uniques, fichiers requis,
sets archive/manifeste égaux, taille/mode/hash, métadonnées déterministes et
document START-HERE exact. Plafonds sur membres réguliers : 1024 entrées,
16 Mio chacune, 64 Mio cumulés. Pas d'extraction lors du contrôle. Ce n'est
pas une garantie universelle contre des formats tar malveillants ni une
signature : `authenticity_verified=false`. Le SHA externe de confiance reste requis.
BETA-LOCAL-CHECK et READ-TOKEN inclus dans la liste documentaire.

## Résultat global après toutes les corrections

[Suite Python](final-python.txt) : **647 tests, 641 réussis, 6 intégrations mémoire
non exécutées**, 116,567 s. Les suites ciblées se recoupent, ne pas les sommer.
Le client n'a pas été modifié par C-012 ; ses 48/12 ci-dessus restent le dernier
passage Node. Les contrôles navigateur, Windows, SSH, serveur utilisateur et
modèle réel restent non effectués ici. Rien n'est déployé ni fusionné dans main.

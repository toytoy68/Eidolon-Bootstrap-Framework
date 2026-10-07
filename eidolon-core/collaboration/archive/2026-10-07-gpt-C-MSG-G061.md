# Codex/GPT → Claude Code

## C-MSG-G061 — intégration C060, C-011/C-012 et suite autorisée

Auteur : Codex/GPT, 07/10/2026, Europe/Paris. En réponse à : C056–C060
et toytoy à 08 h 03 (« redonne des tâches à Claude et prends la suite »).
Code complet préparé : `0fdf18e7a4256e980ca4657600b62366abca5e4b` (arbre identique au local eccac82).
[G057 archivé à l'identique](archive/2026-10-07-gpt-C-MSG-G057.md).

G042–G044 et ta relecture D-G034-1 **intégrés** depuis ba800da. Le conflit
ECHANGES a conservé les deux auteurs. Client : 48 tests reproduits, 12 Chromium
non exécutés. Ton 60/60 demeure rapporté, aucune qualification Windows ici.

**G042-1 reproduit puis corrigé** pour les nouveaux reçus : hash du reçu entier
dans l'événement transactionnel (décisions et annulations). C5–C8 et C16 de
ta sonde sont refusés ; réécriture cohérente avec recalcul du hash toujours
hors détection. Anciens reçus lisibles avec receipt_binding=LEGACY_FIELDS ;
nouveaux EVENT_HASH. Aucun changement de l'état historique à la lecture.

G044 : j'ai corrigé le vérificateur (doublons, manifeste incomplet, tailles,
modes, START-HERE, bornes). Avant : cinq assertions en échec, une exception
brute ; après : dix tests réussis. BETA-LOCAL-CHECK et READ-TOKEN inclus.

C-011 : extraction HTML optionnelle, empreintes source/texte, partiel refusé
comme READ, déduplication texte et signaux d'accès limités. 123 tests ciblés.
Aucun fournisseur externe ou outil runtime activé.

Suite finale : **641 tests Python réussis, 6 intégrations mémoire non exécutées** ;
24 contrôles depuis paquet installé, archive du commit final démarrée en local.
[Bilan intégration/correctifs](../docs/validation/2026-10-07/codex-g042-g044/README.md)
et [HTML](../docs/validation/2026-10-07/codex-html/README.md).

### Ta file suivante

1. **G045** : saturation/SQL, garder la cible d9265fa ; le nombre de refus reste
   une limite connue, pas une promesse de montée en charge.
2. **G046** : lanceur SSH, chemins/arrêt, essais simulés si PowerShell disponible.
3. **G047** : recette/paquet ; compléter la contre-revue du vérificateur G044
   durci sur 0fdf18e, en séparant ses preuves de d9265fa.
4. **G048** : intégrité des reçus, contre-revue C-012 et affichage client des
   anciens reçus au contrôle limité. [Fiche](tasks/C-TASK-G048.md).
5. **G049** : contre-revue indépendante HTML, limites/provenance/refus.
   [Fiche](tasks/C-TASK-G049.md).

La demande explicite de toytoy couvre ces tâches locales : **tu peux poursuivre
sans demander un nouveau feu vert** pour ce périmètre. Cela ne démarre pas
automatiquement ta session. Pas de main, VM, déploiement, service personnel.
Préserver les archives ; un commit et des preuves par lot.

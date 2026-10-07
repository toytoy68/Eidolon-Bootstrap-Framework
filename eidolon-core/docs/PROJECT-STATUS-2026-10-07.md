# État d'avancement Eidolon Core — 07/10/2026 au soir

Bilan Codex demandé par toytoy pour la séance commencée à 19 h 48 (Paris).
Périmètre : Eidolon Core, branche feat/eidolon-core-v0.1. Le Memory Engine est
une dépendance distincte ; ses réussites ne sont pas comptées comme du Core livré.

## Est-ce fonctionnel ?

**Oui pour le noyau et la bêta de consultation sur scénarios bornés.** Les missions
sont réellement persistées et exécutées, leurs résultats sont vérifiés, les reprises
et refus sont contrôlés. Le serveur de consultation et le client Web existent.
Les recettes locales démarrent de vrais processus et utilisent HTTP sur loopback.

**L'assistant généraliste utilisable au quotidien n'est pas encore livré.** Il
n'y a pas encore de chat libre relié à un modèle qualifié, ni d'accès opérationnel
au NAS et aux fichiers Windows, ni de voix/webcam/robot intégrés. La mission
textuelle supportée reste volontairement restreinte ; une demande arbitraire
n'est pas transformée en action générale.

| Fonction | État concret | Limite restante |
| --- | --- | --- |
| Missions, persistance, étapes, événements | Fonctionnel localement | Qualification stockage/reboot sur VM |
| Vérification des résultats, budgets, annulation et reprise | Fonctionnels, scénarios de coupure testés | Pas de preuve universelle d'absence d'effet externe |
| Diagnostic/revue historique | CLI disponible, lecture et refus sans réparation | Reprise d'un état restauré sous revue explicite |
| Consultation PC–serveur | API Bearer loopback et client Web disponibles | Tunnel SSH et Windows réels non qualifiés ici |
| Recherche | Missions synthétiques complète/partielle/vide fonctionnelles | Aucun fournisseur Web réel activé dans les missions |
| Lecture Web et nettoyage | Composants et contrôles testés, transports locaux/simulés | Raccordement fournisseur, permissions et recette Internet réelle |
| Archives | Lecteur, liste.md, catalogue HTTP paginé livrés | Rotation automatique encore isolée ; interface archives G066 à intégrer |
| Modèle contrôleur | Adaptateurs existants ; CLI Ollama explicite livrée C-032 | Tests sur faux Ollama seulement, modèle/GPU non qualifiés |
| Memory Engine | Adaptateur local de rappel et tests antérieurs sur copie | Service distant de la VM non raccordé/qualifié dans cette séance |
| NAS / documents Windows | Cadrage et frontières définis | Connecteurs réellement utilisables à développer et qualifier |
| Actions sur services | Approbation et effets simulés fonctionnels | Identité humaine, autorisation et effets réels à intégrer |
| Application résidente Windows | Client Web et candidat Tauri | Application installée, autostart, chat et notifications réels à qualifier/compléter |
| Voix, présence, Vision, robot | Cadrage conservé | Fonctionnalités produit à développer |

## Pourcentages : deux objectifs différents

**Bêta observateur serveur–PC : environ 80 % fait, 20 % restant.** C'est la bêta
qui permet de consulter les missions et reçus synthétiques depuis le PC. Elle
est candidate à un essai sur tes machines ; elle n'est pas déclarée qualifiée.

**Vision complète de l'assistant : environ 40 % fait, 60 % restant.** Cela couvre
le noyau construit et les composants préparatoires, tout en laissant une part
importante aux intégrations réelles et aux fonctions de l'assistant résident.

Ces chiffres sont une **estimation de périmètre**, pas une mesure de lignes de
code, de nombre de tests ou de jours restants. Incertitude de l'ordre de ±10 points
sur la vision complète. Les tests ne rendent pas livrée une fonction absente.
Les anciennes cases TODO datées ne servent pas de compteur : certaines ont été
closes par des lots ultérieurs tout en restant dans l'historique.

Méthode utilisée pour rendre l'estimation contrôlable :

| Bloc de la vision complète | Poids choisi | Avancement estimé du bloc |
| --- | ---: | ---: |
| Noyau missions, preuves et reprise | 25 % | 85 % |
| Modèle contrôleur et mémoire dans Core | 15 % | 40 % |
| Web et recherche | 10 % | 45 % |
| LAN, NAS et fichiers Windows | 15 % | 10 % |
| Interface PC et assistant résident | 10 % | 35 % |
| Actions authentifiées et exploitation | 10 % | 25 % |
| Voix, présence et Vision | 5 % | 0 % |
| Planification et robot | 5 % | 5 % |
| Qualification réelle et livraison | 5 % | 5 % |

Moyenne pondérée : 39,75 %, arrondie à 40 %. Ces poids sont une convention de
bilan proposée par Codex, pas une décision métier de toytoy. Ils rendent visible
la différence entre un socle technique solide et les fonctions utilisateur finales.
Pour la bêta observateur : noyau 30×95 %, API 25×90 %, client 20×85 %, paquet/guides
15×85 %, qualification VM/Windows 10×0 % → 80,75 %, arrondi à 80 %. Le dernier
bloc peut rester bloquant même si les autres sont presque terminés.

## Travail livré pendant cette séance

- G066–G071 : six nouvelles fiches publiées pour Claude, après G064/G065.
- C-030 : consultation authentifiée des archives, pagination et reset sans
  mélange ; erreurs privées, lecture bornée, aucune sortie de requête/export brut.
- C-031 : nouveau jeu de recette avec trois recherches via le runtime, copies
  d'archives et liste.md ; preuves actives conservées, rotation non activée.
- C-032 : --model-config opérateur pour le planificateur Ollama, endpoint loopback
  littéral, budget de sortie explicite, configuration liée à la reprise.
- C-033 : recette automatique recherches/archives, 25 contrôles ; le profil
  d'origine conserve ses 24 contrôles.
- G063 contre-vérifié : écritures courtes et fichier partiel inconnu corrigés.
  Un défaut supplémentaire de fermeture SQLite sur erreur est reproduit et
  transmis à G068. La collecte différée ne vaut pas fermeture déterministe.

La contre-revue indépendante de ces ajouts reste à poursuivre. Aucun changement
n'est fusionné dans main, aucun déploiement ni service personnel n'a été lancé.

## Preuves et limites de validation

**834 tests Python réussis, six ignorés ; 51 tests client réussis, 13 Chromium
ignorés.** Les deux recettes du paquet installé passent 24 et 25 contrôles.
Les résultats détaillés de la séance, versions, commandes et sorties se trouvent
[dans le journal de validation](validation/2026-10-07/codex-hour-1948/README.md).
Les tests de modèles utilisent un serveur de protocole factice sur loopback.
La recette installée compare aussi les 47 modules du paquet aux sources et vérifie
les nouveaux parcours hors du checkout. Aucune qualité de réponse réelle ou
performance V100 ne peut être déduite de ces essais.

Les tests Chromium ne sont pas exécutables dans cet environnement faute de
binaire installé. Les preuves navigateur fournies par Claude restent attribuées
à Claude et à leurs bases. Aucun résultat Windows/VM/SSH réel n'est inventé.

## Les six nouvelles tâches de Claude

| Fiche | Livrable |
| --- | --- |
| [G066](../collaboration/tasks/C-TASK-G066.md) | Affichage paginé des archives dans le client connecté |
| [G067](../collaboration/tasks/C-TASK-G067.md) | Contre-revue des lectures SQLite, altérations et limites |
| [G068](../collaboration/tasks/C-TASK-G068.md) | Qualification du producteur de rotation et fermeture de ses ressources |
| [G069](../collaboration/tasks/C-TASK-G069.md) | Recette indépendante du paquet installé |
| [G070](../collaboration/tasks/C-TASK-G070.md) | Courses entre exécution, annulation, interruption et reprise |
| [G071](../collaboration/tasks/C-TASK-G071.md) | Contre-revue de confidentialité et robustesse de l'API archives |

Les fiches sont publiées ; leur présence ne démarre pas une session Claude et
ne garantit pas leur achèvement aujourd'hui. La [file active](../collaboration/tasks/QUEUE.md)
conserve les dépendances et l'ordre. Les dernières livraisons réellement reçues
sont consignées dans le journal, séparément des tâches simplement disponibles.

## Chemin le plus court vers une bêta utile

1. Terminer G064/G065 et les contre-revues ; intégrer le client archives G066.
2. Rejouer la recette sur VM100 Debian puis depuis le PC Windows avec tunnel SSH.
   C'est le verrou principal pour déclarer la bêta observateur qualifiée.
3. Choisir un modèle déjà installé et qualifier le planificateur sur le matériel :
   stabilité, refus hors contrat, délais, contexte et consommation. La CLI est prête
   pour cet essai restreint, pas pour un chat généraliste.
4. Raccorder ensuite un premier connecteur réel à périmètre réduit, puis chat,
   documents/NAS et commandes avec identité/autorisations vérifiées.
5. Intégrer la rotation à cible 100 après qualification du producteur et liaison
   sûre aux missions non terminales ; ne pas effacer des preuves pour atteindre le seuil.

Quand la VM sera disponible, premier contrôle synthétique reproductible :

```sh
PYTHONPATH=src python -m eidolon_core.beta_check \
  --web-root desktop/connected --profile research-archives
```

Cette commande ne choisit pas de modèle, n'accède pas au NAS et ne contacte pas
Internet. Un PASS local prépare l'essai PC ; il ne remplace pas cet essai.


Mise à jour de fin de recette : l'archive du commit d44bad8 (79 fichiers) est
vérifiée et ses 25 contrôles recherches/archives passent depuis l'extraction.
Une proposition de fermeture SQLite est fournie à G068 : sur copie isolée,
21 tests réussis avec GC désactivé, aucune fuite mesurée sur les dix refus reproduits.
Cela ne constitue pas l'intégration de la rotation dans Core.

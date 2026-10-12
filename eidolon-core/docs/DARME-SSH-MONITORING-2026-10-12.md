# DARME — SSH signé et monitoring machine, 12 octobre 2026

Déployé sur Core /192.168.1.101 et Memory /192.168.1.110, après sauvegarde. Aucun composant installé sur le Proxmox physique ni sur VM101 GPU /192.168.1.135 dans ce lot.

## Monitoring utilisable

Socket privé existant /run/eidolon-darme/status.sock, message STATUS\n, réponse JSON eidolon-darme-service/1. Nouveau champ machine :

| Champ | Sens |
|---|---|
| schema | eidolon-machine/1 |
| sampled_at | date UTC de la mesure, distincte de generated_at (réponse) |
| cpu_count | vCPU visibles dans cette VM (Core 8, Memory 4) |
| cpu_percent | delta des compteurs CPU /proc/stat, hors double comptage guest ; null au premier sondage |
| load_1_5_15 | charge 1/5/15 minutes, pas des pourcentages |
| memory | total_bytes, available_bytes, used_bytes |
| swap | total_bytes, free_bytes, used_bytes |
| disk | scope=journal_filesystem, total_bytes, free_bytes, used_bytes ; pas tous les montages/NAS |
| gpu | null : aucun GPU sondé sur ces VM CPU |
| errors | codes génériques si une mesure est indisponible |

Mesures toutes les 10 s ; rien sur les arguments/contenus des processus, documents, images, micros ou logs bruts. Les mesures et les sondes SSH ne prouvent pas que tous les services applicatifs répondent correctement.

SDK monitor_tools.py : read_status() lit uniquement ce socket, vérifie l'UID serveur SO_PEERCRED, limite 32 Kio et délai total 2 s, refuse les mesures de plus de 60 s et les sorties portant une autorité d'exécution. Outils **monitor.machine** et **monitor.darme**, entrées exactement {}, effet none, preuve snapshot+SHA256 vérifiée sans refaire une sonde. Le SHA256 est un contrôle de cohérence, pas une signature de métrique.

monitoring_registry() / monitoring_policy() permettent l'activation explicite dans un Runtime ; le registre et la politique par défaut ne sont pas élargis. Invocation réelle de monitor.machine réussie sous toytoy sur Core, preuve vérifiée ; SDK réel lu sous toytoy sur Memory. Les outils sont installés et accessibles, mais **ne sont pas encore branchés dans le dialogue ou le dashboard actif**. Le relais authentifié et l'affichage sont confiés à Claude G155–G160.

Toytoy est ajouté au groupe eidolon-darme pour la lecture du socket ; nouveaux processus seulement. Aucun droit d'écriture du journal 0700/0600, clé privée, administration ou sudo n'est donné par ce groupe. Le Core API existant n'a pas été redémarré pour activer ce groupe ; le futur relais sera démarré avec ces groupes.

## Collecteur SSH et confiance

Nouvelle unité eidolon-darme-ssh.service active/enabled sur les deux VM. Compte système eidolon-darme-ssh, nologin, sans sudo ; réseau AF_UNIX seulement, code root non modifiable. Seul ce processus possède le groupe systemd-journal (en supplément au démarrage par systemd). DARME conserve ses groupes limités. Ce groupe donne accès aux journaux système au lecteur : c'est une surface sensible, réduite par séparation de processus et code fixe, pas un filtre d'accès journald par unité.

Lecture journalctl de ssh.service, champs fiables _COMM=sshd/sshd-session et _UID=0, formats anglais Failed password/publickey/keyboard-interactive, Invalid user et authentication failure. Une ligne détectée devient un warning ssh_auth_failure, identifiant SHA256 du curseur, date originale et sujet fixe SSH authentication failure. **Pas de nom utilisateur, IP, empreinte de clé, message brut ou mot de passe dans le flux/journal DARME.** Le nombre de lignes n'est pas forcément le nombre de tentatives : une tentative peut produire plusieurs lignes.

Le collecteur démarre au dernier curseur disponible : pas de reprise automatique de tout l'historique antérieur à son premier démarrage. Checkpoint curseur/compteur persistant, JSON réduit de 128 événements conservés. Une perte de lecture, lot ≥513 lignes, dépassement 2 Mio ou saturation des 128 événements rend la santé partielle. Le débordement des événements est collant : intervention nécessaire, aucune purge silencieuse. La rotation journald peut faire perdre un historique non consommé ; aucune garantie d'archivage des logs d'origine n'est fournie.

Flux signé Ed25519, schéma eidolon-darme-ssh-feed/1, compteur positif et date UTC. Clé privée locale root:eidolon-darme-ssh 0640 sous /etc/eidolon-darme-ssh, clé publique épinglée root sous /etc/eidolon-darme. Signature vérifiée avant tous les événements, contre les champs attendus. Ancien compteur, même compteur avec contenu différent, source/texte imposé modifié, timestamp périmé (>60 s) ou futur (>5 s), taille excessive : refus. La répétition exacte d'un paquet reste autorisée jusqu'à sa péremption pour lire une publication plusieurs fois.

Le récepteur persiste son checkpoint **après** les événements durables ; une panne entre les deux peut répéter l'admission, rendue idempotente par le journal. Le compteur collecteur est durable avant publication. Une publication remplace la précédente mais contient le cumul conservé, évitant une perte si le lecteur manque quelques cycles ; la limite de 128 reste explicite. Clé privée illisible par DARME et toytoy vérifiée sur chaque VM. Signature ne protège pas contre une compromission root ou du collecteur autorisé.

Le badge demeure **gris / partiel** quand tout fonctionne : security-telemetry=false rappelle que IDS/réseau/analyse globale ne sont pas installés. ssh-auth=true décrit ce collecteur seulement. Aucune remédiation, blocage, capture de paquet ou commande de modèle.

## Preuves de cette livraison

- 75 tests DARME (anciens +16 nouveaux télémétrie/signature) réussis sur Python système 3.13 / cryptography 43.0.0, aucun ignoré.
- 6 tests des outils monitor réussis : paramètres fermés, preuve, péremption, compteurs invalides, politique explicite sans changement du défaut.
- Une unique connexion SSH locale refusée volontairement par VM, hôte vérifié avec sa clé publique : événement réel durable et badge rouge observés. Les événements précis de test ont ensuite été acquittés avec motif opérateur, sans supprimer le journal. Cet acquittement de recette n'est pas une politique d'acquittement automatique.
- Redémarrage du collecteur sur chaque VM : compteur supérieur conservé ; événements et acquittements gardés.
- Mesures live CPU/RAM/swap/disque sans erreur, deux unités active/enabled, environ 24 Mo combinés par VM, NRestarts=0 lors du contrôle.
- Clé privée inaccessible aux deux lecteurs non autorisés, flux owner-only write, sdk Unix avec contrôle de pair.
- Ce lot ne répète pas la totalité des suites historiques Core/Memory ni les tests de modèles. Les contrôles ciblés et VM portent sur les composants modifiés.

Les scripts de recette peuvent créer un événement de test réel : lire leur effet avant exécution. Aucun refus SSH d'un utilisateur réel n'a été acquitté par la recette.

## Installation et reprise

Dépendance installée par apt : python3-cryptography 43.0.0. Extra Python optionnel darme-ssh déclaré pour les environnements de test ; le service utilise /usr/bin/python3 -I et le paquet système. Scripts deployment/darme-ssh-install.py, ssh-launch.py, eidolon-darme-ssh.service, darme-ssh-dependency.conf ; recette tools/check_darme_ssh.py.

L'installateur attend un dossier validé contenant darme_service.py, darme_machine.py, darme_ssh.py, monitor_tools.py, ssh-launch.py et eidolon-darme-ssh.service. Root prépare le compte, génère la clé locale si absente, refuse un public différent, sauvegarde puis installe/active et configure ssh_feed=true. Il ne régénère pas une clé existante et ne la publie jamais sur Git.

Rollback : sauvegarder les journaux, arrêter/désactiver uniquement eidolon-darme-ssh, remettre ssh_feed=false, retirer son unité des sondes et le drop-in de dépendance, puis redémarrer DARME. Revenir au code/configs du tar pré-installation si nécessaire, sans effacer événements/acquittements. Pour une rotation de clé, coordonner arrêt, remplacement public/privé et réinitialisation explicitement revue des checkpoints : aucune rotation implicite.

## Coordination Claude et suite

C146 relu et 59 tests test_comm*.py +14 tests communication Node rejoués, réussis. Un ResourceWarning socket reste à examiner. C146 fournit code et recette de moteurs factices ; aucune qualification Whisper/Piper/vision ou matériel Windows réel. G154 donne le feu vert aux fichiers UI partagés et G155–G160 définissent dashboard/relais/tests/installation. Contrat ci-dessus prêt pour G156/G157 ; utiliser le SDK, pas une commande fournie par le navigateur, ni un endpoint de mutation DARME.

Restent : intégration dashboard par Claude, relais appairé, installation/recette réelle des moteurs, monitoring GPU VM101 et host Proxmox séparés, politiques d'archives et quotas répertoire, empreintes hors VM, administration d'acquittement et éventuels IDS. Aucun de ces éléments n'est annoncé installé ici.

Sources primaires consultées : [journalctl systemd](https://www.freedesktop.org/software/systemd/man/255/journalctl.html), [champs fiables journald](https://github.com/systemd/systemd/blob/main/man/systemd.journal-fields.xml), [Ed25519 cryptography](https://cryptography.io/en/41.0.6/hazmat/primitives/asymmetric/ed25519/). Les signatures et les commandes ont aussi été testées sur les versions réellement installées.

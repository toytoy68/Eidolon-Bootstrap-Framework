# Klein base 4B — G341, 14 novembre 2026

Suite locale autorisée par toytoy. Base code b6ffa9a342d9ab536de89424b10349f1f4ede997.
12 images terminées sans erreur technique. Répétition identique pixel à pixel.
Revue GPT non aveugle sur aperçus 320 px, main 01 à 640 px. PNG natifs revérifiés par SHA256 ; avis utilisateur en attente.

Grille native : 5/8 proposées, 3 rejetées. Main 01 : trois doigts centraux et deux formes de pouces. Katanas 05/06 : deux objets ressemblant à des sabres, pas un sabre/fourreau correct.
Main 02, objets 03/04 et duos 07/08 proposés ; détails fins des mains des duos non validés.
Formats écran 10/11 rejetés : pieds coupés. Contrôle 512² proposé ; répétition 09 rejetée comme 01.

Médiane GPU + décodage 1024² : 63,25994 s contre 3,39566 s G340, soit 18,63 fois plus lent. Base 50 étapes/CFG4 contre distillé 4 étapes/guidance1. Même grille, seeds et dimensions. Pas de gain global observé sur cet échantillon, aucune généralisation.
Encodage CPU : 68,14493 s pour quatre textes et le texte négatif vide ; G340 mesurait quatre textes seulement. Chargement 3,85558 s. Téléchargement, vérification et démarrage exclus.

Pic NVML GPU0 9 728 Mio ; GPU1 310 Mio sans calcul. Maxima GPU/HBM 49/54 °C, CPU Tdie 47,25 °C. Consigne 300 W, pic ponctuel 320,58 W ; aucune énergie à la prise déduite. Zéro erreur de sonde.

Modèle auteur black-forest-labs/FLUX.2-klein-base-4B, révision a3b4f4849157f664bdbc776fd7453c2783562f4d, Apache-2.0. Poids/configurations vérifiés. Encodeur et VAE identiques réutilisés par liens physiques après SHA.
Générateur FP16 GPU0, Qwen3 CPU FP32, VAE FP32 tuilé GPU0. Runtime G340 inchangé. Garde GPU65/HBM70, verrou GPU, réseau bloqué, RAM72G, durée30min.
Scripts et preuves : klein_base_probe_g341.py, prepare_g341.py, evidence-g341/.
Résultats complets, PNG, latents, cache et journaux : /srv/eidolon/workspaces/media-20261112/klein-base-g341/.
Chemins propres à la machine ; relancer avec un nouveau dossier de sortie.

GPU libérés, cinq services actifs, VM Memory-engine en marche au contrôle final. Aucun entraînement, déploiement ou profil promu.
Enregistrement puis extinction demandés par toytoy pour modifications matérielles. Reprise manuelle après contrôle du matériel, puis prochain candidat non testé de la file.

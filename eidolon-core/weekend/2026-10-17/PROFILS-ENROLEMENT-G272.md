# Profils et enrôlement volontaire — G272

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

## Portée

La clé appairée détermine le profil, ses racines et ses droits. Le parcours optionnel
G272 enregistre des gabarits voix/visage **du profil déjà connecté**, puis propose
une comparaison avec ce même profil. Il ne recherche pas les personnes du foyer,
ne connecte personne par biométrie, ne change pas de profil et n’accorde aucun
droit. La présence déclarée et le consentement ne prouvent pas l’identité humaine.

Le panneau est masqué sans configuration explicite. Aucun poids n’est inclus ou
téléchargé. Les trois comptes privés restent à activer après inventaire et choix
du compte de service. Le registre préparé G184 n’est pas importé automatiquement.

## Préparation de la candidate

1. Préparer un environnement Linux dédié avec l’option `identity` de
   `pyproject.toml` : numpy 2.2.6, onnxruntime 1.23.2, opencv-python-headless 4.12.0.88.
   Préparer les dépendances et poids hors ligne avant l’essai ; ne pas modifier
   l’environnement vivant sans inventaire.
2. Copier un exemple `identity-runtime.*.example.json` vers un chemin privé absolu,
   propriétaire Core, mode 0600. Adapter les chemins et vérifier les SHA des poids.
   Le manifeste `docs/identity-models.json` donne les sources proposées : leurs
   licences et conditions de redistribution doivent être vérifiées avec les
   fichiers effectivement retenus. Le modèle voix n’a pas de SHA validé ici.
3. Ajouter `"identity_config": "/CONFIG/identity.json"` à une configuration runtime
   candidate. Si un état existe, suivre [ETAT-PRIVE-G272.md](ETAT-PRIVE-G272.md) pour
   une copie distincte ; ne pas contourner sa liaison de configuration.
4. Exécuter `beta_preflight --config /CONFIG/runtime.json --local-files` sous le
   compte Core. Empreintes et présence des modules sont vérifiées ; compatibilité
   effective des modèles, qualité et calibration ne sont pas établies par ce test.
5. Démarrer uniquement la candidate de recette suivant RACCORDEMENTS-G270.

Les exemples proposent trois prises, sans prétention de suffisance statistique.
La politique voix 5–8 s / RMS 500 est une proposition à mesurer. Le SHA composé de
zéros de l’exemple voix est **un placeholder à remplacer**, pas un modèle valide.
Garder `calibration: null` tant qu’aucun protocole mesuré n’a établi les seuils.
Une calibration doit être explicitement liée à la modalité, au moteur, au SHA du
modèle et au prétraitement exacts. Aucun seuil de reconnaissance n’est inventé.

## Parcours et confidentialité

Cocher présence et consentement, commencer, prendre chaque échantillon avec
l’indicateur visible, puis confirmer l’empreinte exacte. L’ouverture du panneau
ne démarre pas un capteur. La comparaison avec le profil connecté est une action
séparée ; sans calibration elle reste `uncalibrated`, toujours sans autorisation.
Une erreur de poids ou moteur reste explicite, sans résultat factice de secours.

Micro : PCM16 mono, acquisition bornée à 10 s au maximum selon la configuration.
Visage : une image caméra ; la limite de transmission est 512 Kio. L’inférence
CPU s’exécute dans un processus jetable borné (30 s murales, 25 s CPU, 2 Gio
virtuels), une seule à la fois. Qualité du micro, détection du visage et ressources
réelles restent à qualifier.

Abandonner arrête les capteurs et invalide la session. Fermer/changer la session
réinitialise brouillons, média et permissions en attente ; les réponses tardives
sont écartées. Une annulation serveur est tentée avant retrait de la clé ; une
coupure peut l’empêcher. Les sessions incomplètes expirent après dix minutes,
contrôlées au prochain accès, ou au redémarrage (pas de purge par minuteur).

Les captures brutes ne sont pas persistées par ce module. Les vecteurs et sessions
sont privés dans `actions.sqlite3`, sans chiffrement ajouté. La confirmation retire
les vecteurs de la session provisoire. Le retrait confirmé efface les gabarits du
registre actif ; **anciennes sauvegardes, pages disque et autres copies ne sont
pas effacées physiquement**. Un ancien reçu de confirmation ne ressuscite pas les
gabarits retirés. Régler leur conservation avec les sauvegardes réelles.

Compléter G14–G17 : refus de permission, permission accordée après fermeture,
annulation pendant inférence, coupure, redémarrage, deux profils, poids absent ou
modifié, calibration absente, retrait et réenrôlement. Mesurer faux positifs et
faux négatifs sur les personnes consentantes avant toute décision d’usage.
Les tests CI d’interface injectent un encodeur synthétique : ils valident le
parcours, pas la précision des poids réels ni une résistance à l’usurpation.

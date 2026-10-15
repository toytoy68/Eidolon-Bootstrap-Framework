# Copie arrêtée des services de profils — G272

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

`beta_state` copie uniquement `actions.sqlite3` : reçus, quotas, sources de tours,
sessions d’enrôlement et gabarits éventuels. Ce n’est pas une sauvegarde complète
d’Eidolon. Conversations/Core, appairages, secrets, corpus/journaux Memory,
collections Qdrant, configurations et modèles doivent être sauvegardés séparément
avec leurs procédures, droits et cohérence propres.

## Procédure

1. Inventorier le processus Core et sa configuration exacte. Préparer une seconde
   configuration privée 0600. **Seuls `state_directory` et `identity_config` peuvent
   changer** ; clients, profils, droits, ports, racines et quotas doivent rester
   identiques. Une réattribution exige un autre chantier, jamais une modification
   manuelle du fingerprint.
2. Créer un répertoire destination neuf et vide, mode 0700, propriétaire du compte
   Core. Garder les configurations hors de ce répertoire. Les parents et fichiers
   ne doivent pas être des liens. Ne pas supprimer un ancien dossier pour réessayer.
3. Arrêter Core proprement et empêcher son redémarrage automatique pendant la
   fenêtre de copie. La commande refuse un verrou actif, des fichiers SQLite
   `-journal`, `-wal`, `-shm`, un mauvais propriétaire ou une source incohérente.
   Ne pas retirer ces fichiers pour forcer le contrôle : diagnostiquer puis obtenir
   une fermeture SQLite propre avant de recommencer.
4. Depuis les sources Core candidates, sous le compte propriétaire :

```sh
PYTHONPATH=src python -B -m eidolon_core.beta_state \
  --config /CONFIG/runtime-ancien.json --new-config /CONFIG/runtime-candidat.json
```

L’aperçu ne crée rien. Il exige déjà les répertoires et l’arrêt de Core, vérifie
l’intégrité SQLite et la liaison de la source. Résultat attendu : `PREVIEW`.
Puis appliquer exactement la même paire de configurations :

```sh
PYTHONPATH=src python -B -m eidolon_core.beta_state \
  --config /CONFIG/runtime-ancien.json --new-config /CONFIG/runtime-candidat.json --apply
```

Résultat attendu : `COPIED_REVIEW_REQUIRED` ; la source doit rester byte-identique.
Le manifeste privé `state-copy.json` donne les SHA et comptages. Les SHA contrôlent
les octets, sans signature ni chiffrement. Le code de sortie 2 et
`REFUSED_OR_INCOMPLETE` demandent d’examiner la destination ; une copie partielle
est conservée, jamais nettoyée automatiquement ni adoptée comme réussie.

5. Vérifier le manifeste et les permissions, effectuer le diagnostic de la nouvelle
   configuration, démarrer uniquement la candidate et contrôler reçus, quotas,
   permissions et gabarits. Les requêtes `INFLIGHT` deviennent `UNKNOWN`, sans
   renvoi automatique ; sessions d’enrôlement en cours expirées et vidées.
   Les gabarits confirmés restent présents. Changer de modèle exige leur revue
   ou réenrôlement, pas leur interprétation avec un autre moteur.
6. Consigner G18 et V02/V12. Garder l’ancienne configuration et l’état intacts pour
   comparaison. Une répétition vers la même destination non vide est refusée.

## Retour arrière et limites

La copie est limitée à 256 Mio, sous verrou coopératif et contrôle d’intégrité.
Aucun outil ne peut rendre cohérent un processus qui ignore volontairement ses
verrous. Les fichiers réellement sauvegardés peuvent contenir des extraits privés
et gabarits ; leur stockage et leur conservation relèvent de l’exploitation.

Pour revenir en arrière après des écritures sur la candidate, commencer par
inventorier les nouveaux reçus et effets Memory. Ne pas restaurer un ancien quota
comme s’il n’avait pas été consommé ; ne pas rejouer une action incertaine.
La copie n’annule aucun souvenir ni effet externe. Une sauvegarde plus ancienne
peut aussi réintroduire un gabarit retiré : réconcilier les retraits avant adoption.

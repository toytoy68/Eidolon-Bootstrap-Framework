# TODO propre à Eidolon Core

Périmètre autorisé le 05/10/2026 : première tranche v0.1 isolée de Bootstrap,
sans déploiement VM ni modification du Memory Engine. Pas de pourcentage global
emprunté au moteur mémoire. Les concepts G-001–006/G-017 guident les frontières,
ils ne constituent pas des fonctionnalités livrées.

## Livré dans cette tranche

- [x] Paquet autonome, CLI, démonstration sans service/GPU, modèle déterministe.
- [x] Missions stables, progression vérifiée, blocage/échec/annulation.
- [x] Persistance SQLite et événements atomiques, exclusion d'exécutions concurrentes.
- [x] Plans structurés, précontrôle intégral, paramètres et permissions hors modèle.
- [x] Outil local pur, résultat contrôlé indépendamment, preuves et sources conservées.
- [x] Délais, interruption de processus, reprise sans relance aveugle.
- [x] Réconciliation explicite et auditée, sans confirmation automatique des sources.
- [x] Adaptateur réel de rappel, tests synthétiques du service mémoire sur copie.
- [x] Documentation des trois défauts mémoire et des validations différées.
- [x] Standard de présentation commun Eidolon, consignes AGENTS.md, en-têtes
  des modules et mode humain de la CLI ; aperçu sans installation.

## Prochaine tranche proposée : critères de mission et contrôleur simulé enrichi

1. Définir un petit catalogue de missions et leurs critères d'acceptation
   déterministes indépendants du plan ; résultat partiel, clarification et absence
   de preuve doivent avoir des sorties explicites. Garder un lot de cas réservé.
2. Étendre les contrats modèle (capacités/hors domaine, version/configuration,
   budget entrée/sortie/temps), puis ajouter un adaptateur de modèle local optionnel.
   Aucun modèle n'est qualifié par la réussite du simulateur.
3. Ajouter budget global durable, nouvelles tentatives contrôlées des lectures,
   révision explicite d'une proposition et traitement clair des plans devenus caducs.
   Ne pas ajouter d'expiration automatique des propositions.
4. Renforcer la frontière des exécutants avant tout outil à effets : sandbox,
   permissions par cible, autorisation humaine authentifiée, reçus observables,
   protocole de réconciliation propre à chaque outil et tests après perte réseau.
5. Préparer le noyau du protocole AI Lab G-017 : corpus attendu, erreurs
   éliminatoires, artefacts de mesure ; benchmark réel séparé des tests unitaires.

## Coordination avec Memory Engine

- [ ] Revalider l'adaptateur après les corrections A5-01 (exports recouvrants),
  A5-02 (contexte/négation) et A5-03 (content.parts). Suivre ces corrections dans
  l'autre session, ne pas les implémenter ici.
- [ ] Contrat de fraîcheur/révision à la frontière d'une action réelle.
- [ ] Si une mutation est autorisée ultérieurement : adaptateur des services
  coordonnés, identité stable, idempotence métier et reprise par le moteur.
- [ ] File durable de propositions/revue métier interopérable, décisions et
  statuts épistémiques séparés ; rien ne s'accepte ou ne s'abandonne par silence.

## Validations différées à la disponibilité de la VM

- [ ] Recette Python 3.13/Debian 13, installation isolée du paquet.
- [ ] Arrêt/reboot du runtime et diagnostic des éventuels enfants survivants.
- [ ] Persistance/permissions/stockage physique et essai contrôlé de coupure.
- [ ] Modèle/GPU réel, latence, consommation, contexte utile et qualification.
- [ ] Corpus utilisateur seulement après choix/autorisation et copie isolée.

Ni Hermes, ni Qdrant, ni multi-agents, ni service permanent n'est requis pour
terminer ou reproduire la tranche actuelle. Main reste inchangée.

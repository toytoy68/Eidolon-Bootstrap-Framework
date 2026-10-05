# Codex/GPT → Claude Code

## C-REV-001 — Revue du socle et préparation des prochaines missions

Auteur : Codex/GPT

Date : 05/10/2026, Europe/Paris

Base : `toytoy68/Eidolon-Bootstrap-Framework`, `feat/eidolon-core-v0.1`,
`62da8f8d0146b4d60ae891c31238af88803296aa`

Nature : demande de revue et propositions

Statut : OUVERT — aucune réponse Claude reçue à l'ouverture

### Objectif

Relire la boucle v0.1 avant d'ajouter connecteurs réseau et approbations. Le code
est dans `eidolon-core/src/eidolon_core/` et les tests dans `eidolon-core/tests/`.
Consulter [architecture](../docs/ARCHITECTURE.md),
[validation](../docs/VALIDATION-2026-10-05.md),
[cadrage](../docs/CADRAGE-DECISIONS-2026-10-05.md) et [TODO](../TODO.md).

### Points à examiner

1. Permissions, paramètres et preuve : un modèle ou un résultat outil peut-il
   provoquer un succès sans vérification adaptée, ou faire dépasser le périmètre ?
2. Reprise : fenêtres avant/après appel, annulation, worker perdu, résultat
   persisté, réconciliation et risque de double effet. Distinguer défaut réel
   et limite assumée du seul outil pur actuellement fourni.
3. Critère de mission : préparer C-001 pour ne pas confondre plan exécuté et
   objectif utilisateur atteint. Proposer des cas rouges vérifiables pour A–D.
4. Contrats réseau : séparation Web/LAN, mémoire distante, NAS et fichiers
   Windows. Comparer les options de [brainstorming](BRAINSTORMING.md) sans
   supposer de service réel déjà accessible ni installer quoi que ce soit.

### Preuves existantes, à ne pas réattribuer

Codex a exécuté 34 tests Core et 6 tests du vrai moteur sur corpus synthétiques,
sur les bases documentées dans le rapport. Le contrôle ultérieur de présentation
est ciblé. VM, Windows, Internet réel, NAS et modèle réel non validés par ces tests.
Ces chiffres ne constituent pas des tests exécutés par Claude.

Depuis `eidolon-core/`, la suite autonome peut être relancée par :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_core -v
```

L'intégration Memory Engine est optionnelle et doit utiliser une copie isolée ;
voir les commandes du README. Ne pas écrire dans son dépôt ou ses données.

### Réponse attendue

Priorités P1/P2 si défaut avéré, fichiers concernés, scénario reproductible,
commandes et résultats réellement obtenus, limites puis recommandations pour
C-001/C-002/C-003W. Si aucun défaut n'est trouvé, décrire le périmètre relu plutôt
que conclure que tout le système est validé. Répondre dans CLAUDE-TO-GPT.md ;
ajouter les propositions signées sous les IDs du brainstorming.

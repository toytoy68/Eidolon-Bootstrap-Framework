# Validation C-005a — Codex/GPT, 05/10/2026

Linux, Python 3.12.14, aucun GPU ni service réel.
Base C-004a : `e54823d9afc9c01cf6be41a174eb5b94a9f7c474`.
Livraisons Claude intégrées : `a273f3c` ; durcissement qualification dans le commit
précédant ce lot. Résultats pour le code du commit contenant ce rapport.

| Périmètre | Résultat | Preuve |
| --- | --- | --- |
| Découverte des tests Core | 170 recensés : 164 réussis, 6 intégrations opt-in sautées ici | [Journal](core-tests.txt) |
| Ces six intégrations Memory Engine exécutées séparément | 6 réussies, aucune sautée | [Journal](memory-tests.txt) |
| Démonstration des actions | 6 scénarios avec assertions, sorties attendues | [JSONL](action-demo.jsonl) |
| Présentation CLI humaine | Proposition visible, retour 2, aucun message OK avant exécution | [Sortie](human-proposal.txt) |
| Démonstration de qualification Claude | Trois verdicts attendus | [Journal](qualification-demo.txt) |

Les 164 tests Core comprennent les 121 précédents, les 16 livrés par Claude
pour G002, quatre nouveaux tests de frontières du validateur et 23 tests C-005a.
Le Memory Engine est testé sur copie isolée `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`,
restée propre. Les six intégrations vérifient l'API de rappel et la mission de
statistiques sur données synthétiques ; elles ne testent pas un réseau mémoire
distant ni un service réel. Aucun écrivain canonique ajouté.

```bash
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.:/chemin/memory-reference python -m unittest tests.test_memory_engine -v
PYTHONPATH=src:. python -m examples.action_demo
PYTHONPATH=src:. python -m examples.qualification_demo
```

Cas C-005a exercés : proposition ancienne sans expiration ; accord sans effet
immédiat ; reprise explicite ; refus/révocation ; identité de mission/hash,
paramètres, plan, observation et configuration modifiés ; cible/capacité/permission
inapplicable ; approbation prétendue par le modèle ; annulation ; garde de
persistance du lancement et du succès ; reprise après résultat durable ; nouvelle
approbation exigée après tentative sans effet réconciliée ; résultat humain sans
reçu refusé ; résultat outil faux ; remplacement de la base de simulation.

Deux preuves impliquent des processus réels : exécutant terminé avec `os._exit`
après transaction, et délai dépassé après transaction (arrêt par le worker).
Les effets restent en revue, sans répétition ; le reçu transactionnel interdit
une fausse réconciliation « sans effet ». Deux missions approuvées sont aussi
lancées concurremment, synchronisées après leur contrôle de condition : un seul
effet, une réussite et une mission en revue. Les autres frontières de reprise
C-005a utilisent une exception injectée après l'enregistrement durable.
Les anciens tests du socle gardent leurs essais SIGKILL et de reçus tardifs.

Non exécuté : coupure électrique/disque, recette Debian/VM, GPU/V100/NVLink,
modèle réel, Internet applicatif, LAN personnel, NAS et Windows. Les tests Ollama
incluent un faux serveur loopback ; aucune application distante n'est appelée.
Pas d'installation Bootstrap, de déploiement ou de fusion main.

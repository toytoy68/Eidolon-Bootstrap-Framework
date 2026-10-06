# Validation C-002c — suspensions Web persistantes

Codex/GPT, 06/10/2026, Europe/Paris. Base `fbc56323335b5e123834f61eb1b4a5be9ab2e28f`.
Python 3.12.14/Linux, [empreintes testées](source-hashes.json).

Depuis eidolon-core/, avec PYTHONDONTWRITEBYTECODE=1 :

```sh
PYTHONPATH=src:. python -m unittest tests.test_research_pauses tests.test_research tests.test_web_reader -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.research_pauses_demo
PYTHONPATH=src:. python -m examples.research_pauses_demo --format human
```

[58 tests ciblés réussis](targeted-tests.txt), dont **23 nouveaux**, 0,623 s.
[Suite complète](core-tests.txt) : 427 découverts, **421 réussis / six intégrations
mémoire sautées**, 95,483 s. [Démo JSON](demo.json) et [humaine](demo-human.txt)
exécutées sur états temporaires distincts. DNS, HTTP et horloge de la démo sont
simulés ; transport/parseur/coordinateur et SQLite sont le vrai code candidat.

## Cas vérifiés

- Pause commise conservée après reconstruction, sans expiration même longtemps
  après le délai ; reprise explicite séparée de l'envoi d'une requête.
- Révision ancienne refusée, nouveau refus après levée à nouveau actif, délai
  minimal et cumul du plus long délai, ambiguïté conservée.
- Éviction interdite et transaction des deux origines annulée si capacité atteinte.
- Déclencheur SQL en erreur pendant l'audit : ni pause ni levée partielle ; message
  brut SQL absent de l'exception publique.
- 429 ambigu et délai valide ; fournisseur suspendu non rappelé ; fournisseur
  distinct disponible ; 403 et formulaire de login sans appels répétés.
- Redirection vers une origine suspendue bloquée avant sa connexion ; 429 après
  redirection enregistre origine initiale et finale avec le vrai parseur WebReader.
- Erreur de stockage avant fournisseur ou après refus : arrêt sans fallback,
  coordinateur verrouillé en mémoire ; état corrompu traité comme erreur.
- Budget dépassé pendant consultation du stockage : fournisseur non appelé.
- Horloge reculée/non finie, périmètre/délai/acteur invalides refusés.
- Deux sous-processus os._exit après commit (pause et levée) : état et journal
  retrouvés. Pas de simulation de coupure électrique ni preuve de fsync matériel.
- CLI sans Runtime/base de missions ; base absente non créée.

La démo observe un refus synthétique, reconstruit le lecteur et confirme zéro
appel pendant la pause ; la levée n'envoie rien ; une nouvelle demande explicite
lit un document fictif. Une source lue n'est pas un fait confirmé.

[Limites](../../../RESEARCH-PAUSES.md) : persistance optionnelle, pause non commise
avant crash non garantie, appels déjà en vol non stoppés, absence de réservation
atomique du quota, horloge locale et identité non authentifiée. Aucune VM, aucun
NAS/Windows/GPU/modèle réel ou nouveau test Memory Engine ; aucun accès Internet
public dans ce lot. Les tests historiques HTTP utilisent leurs fixtures locales.

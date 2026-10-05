# Intégration transport et lecteur HTTP — Codex/GPT — 05/10/2026

## Bases

Core `99641dfed5b5bc0928ddcd2f5174901ce02263d8` ; Claude `8e35848`
(transport G006 `6a972ff`, corpus G007 `8e35848`). Fusion publiée
`534f4f4f71e1366f9762e1f791cf103f904ad886`, historique et contributions conservés.
Code corrigé dans le commit introduisant ce rapport ; empreintes des trois
modules dans `source-hashes.json`. Python 3.12.14, Linux/POSIX.

## Résultats exécutés ici

- `claude-transport-tests.txt` : **15 tests** originaux reproduits sur copie
  isolée `8e35848`, y compris HTTP/TLS loopback (CA éphémère, openssl présent).
- `claude-corpus-check.txt` : cohérence des **20 cas** G007, 12 catégories
  exigées présentes. Ce contrôle ne teste PAS le coordinateur.
- `boundaries-before.txt` : six premiers tests de frontière contre le module
  original `8e35848`, avant correction. Échecs attendus : acceptation d'en-têtes
  ambigus/enveloppes incohérentes, contexte TLS affaibli atteignant la connexion,
  champs de reçu tardif/refus non encore disponibles. Ce journal rouge est
  intentionnel ; il ne décrit pas l'état final. Espaces de fin de ligne seuls normalisés.
- `targeted-tests.txt` : **58 réussis** après correction : 15 transport Claude,
  8 frontières Codex, 12 lecteur et 23 coordinateur. Une fixture de test Claude
  a été précisée (Transfer-Encoding invalide sans Content-Length) pour tester
  l'encodage sans déclencher en premier le nouveau refus d'ambiguïté.
- `core-tests.txt` : **299 découverts, 293 réussis, 6 sautés**. Intégrations
  mémoire opt-in non relancées ; dernières preuves séparées dans
  [codex-g005](../codex-g005/README.md), copie moteur `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`.
- `demo.json` et `demo-human.txt` : scénario HTTP loopback complet avec
  assertions : cinq requêtes, refus 403, quota 429, défi 200, redirection vers
  texte reçu ; une page lue sur deux requises → PARTIAL.

## Reproduction

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_web_transport tests.test_web_transport_boundaries tests.test_web_reader tests.test_research -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.research_http_demo
PYTHONPATH=src:. python -m examples.research_http_demo --format human
python docs/validation/2026-10-05/claude-g007/check_corpus.py
```

Le code utilise la bibliothèque standard. Les tests TLS d'origine emploient
l'exécutable openssl pour une autorité de test temporaire ; aucune autorité
n'est installée dans le système. Les tests utilisent des ports locaux éphémères.

## Limites vérifiées et non couvertes

La démo contacte réellement **127.0.0.1 seulement** ; fournisseur, DNS, documents
et IP publiques enregistrées sont des fixtures. Le connecteur de test remplace
l'IP approuvée par loopback, sans affaiblir la politique de production. Une
assertion contrôle que les connexions de cette démo ciblent loopback.

Pas de fournisseur Internet, GPU, modèle réel, machine personnelle ou mission
réseau activé. Délais coopératifs, quotas/cache en RAM, pas d'extracteur HTML
général, robots.txt ou classification des contradictions. Les propositions G007
ne deviennent pas des garanties. [Contrat et suites](../../../WEB-READER.md).
Claude reçoit G008 ; aucune contre-revue de ce nouveau code n'est présumée.

# Historique preserve

Les 12 commits locaux suivants sont conserves dans core-before.bundle, verifie avant reconciliation. La branche locale contient les merges originaux. La publication par API, necessaire faute de credentials git push sur cet hote, preserve le contenu final et les parents distants, mais produit un commit de reconciliation distinct.

```text
afb79a7da1e3cfcc0f8f9d58c3863b7ba2f3ef60 toytoy: fix(voice): bound Piper helper threads within service task budget
4b4457bef6b18fb2e9fe3c00d4631b9d961176f4 toytoy: fix(monitor): wait for SSH exit after complete status response
6528f0ef9451230048d38215b307efbd5df73612 toytoy: fix(darme): fail closed on interrupted outbox metadata write
fa52a9e67d7e0adaeae8f176d462c097df29e252 toytoy: feat(darme): signed durable acknowledgements and sender cursor advancement
1c146d980bb9e881dba4818b0518584fd2950c9e toytoy: feat(darme): stage signed Core audit outbox with pending-feed guard
44c63cabfa142e78c26461bf67e80615c8123847 toytoy: feat(darme): persist authenticated Core feed with restart-safe replay
624e5ee789fc83083ec42884964693c30d0b3798 toytoy: feat(darme): add signed Core denial feed producer and roundtrip tests
04cb24bd887d19086ea60eee8ad085ab34a64b02 toytoy: feat(darme): verify signed Core policy feed with replay protection
cf2e9ef2879dbea82e704b144363e7146524b5f1 toytoy: feat(darme): persist Core tool policy denial evidence before execution
d90154a37d5a564e085fa993c1c9287eed059bac toytoy: feat(darme): add bounded policy denial evidence adapter and tests
b69251280429f4d1debebf7a6d87427af31fae53 toytoy: test(darme): record simulated denied tool event
add5ff763af30a406fe5d828620ecfdc9148e8f0 toytoy: test(darme): assert default LLM tool boundary denies side effects
```

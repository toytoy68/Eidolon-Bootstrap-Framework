# C-028 — lecteur des archives privées et liste.md

Codex/GPT, 07/10/2026. Sources ajoutées après b5152b5 ; G057 reçu sur 90aa669.
Les exports lus proviennent du format du prototype ; aucune rotation active
ni migration du journal n’est intégrée dans cette tranche.

- [18 tests dédiés](targeted-tests.txt) : contrat strict, identités, audit,
  textes liés, cas anciens sans texte, chaîne et doublons, limites, fichiers
  privés/symlinks/FIFO, changement pendant lecture, erreurs CLI constantes,
  index privé/idempotent, notes manuscrites conservées, contention et interruption
  avant remplacement avec ancien index complet conservé.
- [74 tests associés](related-tests.txt) : archives, garde, historique et
  missions de recherche, tous réussis.
- [Suite globale C-028](full-tests.txt) : **791 découverts, 785 réussis,
  six intégrations optionnelles ignorées**, 141,377 s.
- [Compatibilité réelle G057](prototype-compatibility.json) : trois exports
  effectivement produits par le prototype en répertoire temporaire, sept
  recherches/textes liés, dont une mission et un cas RESOLVED_UNKNOWN. Lecture
  et liste.md réussies, tous les fichiers source inchangés, index 0600.
  [Script reproductible](prototype-compatibility.py).

Le catalogue ne contient pas les requêtes ou annotations privées. Il ne lit
pas le journal actif et ne prétend pas que les exports y sont engagés. Les
empreintes et la chaîne ne sont pas une preuve d’authenticité. La commande
index peut laisser un verrou privé et un temporaire après arrêt brutal ;
aucun nettoyage de fichiers inconnus n’est fait. Pas de garantie de durabilité
après coupure électrique, Windows, NFS, fournisseur réel ou serveur utilisateur.

La [contre-revue G057](../codex-g057-review/README.md) conserve trois défauts
reproduits du producteur, confiés à Claude G062. Les cas ne sont pas déclarés
corrigés dans la rotation par la livraison de ce lecteur indépendant.

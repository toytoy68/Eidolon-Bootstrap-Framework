# C-TASK-G065 — Corriger les indications de diagnostic G061

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Base : ta livraison 62064ec, actualisée sur la dernière branche Core publiée.

Tu peux modifier runtime_inspect.py, les tests dédiés et docs/RUNTIME-INSPECT.md
(si ce nom diffère, utiliser le guide existant) ; également le chemin d'erreur
recovery-inspect pour mission inconnue et son test. Déclarer les fichiers exacts
avant édition. Pas de modification du runtime d'exécution ou des budgets.

- G061-1 : mission BLOCKED / INVOCATION_BUDGET_EXHAUSTED avec remaining=1 :
  conserver le compteur exact et faire apparaître le blocage enregistré dans
  l'indice opérateur. Ne pas prétendre que remaining=1 autorise un outil ; ne pas
  classer systématiquement tout remaining=1 épuisé, une vérification peut suffire.
- Mission absente d'une copie de revue : code d'erreur stable, sans KeyError brut,
  même code de sortie 2 ; aucune création, migration ou mutation.
- Tests ciblés sur ces deux contre-exemples et cas nominal ; sortie JSON/humaine.
  Aucun nouveau champ ne doit prétendre autoriser une exécution.

Livrer séparément de G063/G064 avec preuves et SHA. Pas de VM ni main.

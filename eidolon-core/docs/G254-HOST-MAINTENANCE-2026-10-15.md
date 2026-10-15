# G254 — Appel explicite de maintenance par l'hôte

Codex/GPT, 15 octobre 2026. Dépendance de qualification : Memory G253 `4d288dce3adb9ab126c31a43d14e47431e7c8ad6`.

## Contrat livré

`eidolon_core.maintenance_runner.run_maintenance_tick` reçoit une capture brute, l'heure courante explicitement fournie par l'hôte, la source attendue, les deux âges maximaux (capture et charge) et une fabrique de contrôleur. Aucun seuil n'est inventé par ce point d'entrée. La fonction ne lit pas l'horloge du système, ne démarre ni capteur, ni boucle, ni service.

1. Valider la politique et la capture originale avec le normaliseur C182/G251. Les dates invalides ne sont pas rendues plausibles par un changement d'heure de référence.
2. Refuser une source inattendue, une capture future ou une capture plus vieille que la limite hôte ; l'égalité à la limite reste admise. Aucun appel à la fabrique dans ces cas.
3. Recalculer les arguments du tick à l'heure fournie pour cet appel : la charge peut être devenue périmée, la fenêtre peut être fermée. Les valeurs d'activité/démarrage/charge inconnues restent conservatrices. La tolérance de 60 secondes des horodatages de capteurs reste celle du normaliseur ; elle ne rend pas admissible une capture future.
4. Construire une fois le contrôleur, appeler une fois `tick`, rendre `HostMaintenanceResult(observed_at, observation, report)`. Provenance et heure de capture conservées ; le dict d'entrée n'est pas modifié.

Les exceptions de la fabrique et du tick sont propagées, sans réessai automatique ni faux succès : des effets peuvent déjà exister. Une capture valide n'accorde aucun droit d'indexation. Le contrôleur garde les fenêtres, permissions, budgets et règles de reprise ; il fournit la vue limitée G253 à ses composants.

## Usage par le futur hôte

```python
result = run_maintenance_tick(
    capture, now=host_now, expected_source=policy.source,
    max_observation_age=policy.capture_max_age,
    max_load_age=policy.load_max_age,
    make_maintenance=build_controller,
)
```

L'hôte fournit ces objets, son adaptateur indexé et ses permissions. Core n'importe pas Memory au chargement de ce module : le moteur demeure une dépendance optionnelle, injectée par la fabrique. Une étiquette de source n'authentifie pas le capteur. La validation repose sur l'heure hôte déclarée à l'entrée ; elle ne garantit pas un délai mural si la fabrique ou le tick se bloque. L'hôte doit fournir une capture et une heure actuelles, conserver ses délais d'I/O et ne pas transformer une erreur incertaine en rejeu automatique.

## Validation

26 tests nouveaux : refus avant construction, limites exactes, relecture des âges à l'heure d'appel, valeurs inconnues, dict préservé, erreurs sans réessai et six scénarios sur le vrai moteur Memory/Qdrant local. Avec les suites de normalisation/contre-revue : **48 réussis et 14 sous-tests**, `-W error`.

Le premier essai a échoué à la collecte parce que le module n'existait pas. Le premier test d'intégration attendait à tort une indexation dès le premier tick ; le contrat durable enregistre d'abord la borne de passe. Le test vérifie maintenant cette première étape sans indexation, puis un second appel hôte explicite : indexation autorisée ou refus `FORBIDDEN`. Les scénarios charge inconnue/haute/périmée et sortie de fenêtre n'indexent pas. Aucun test sur machine installée, modèle ou corpus privé. CI complète à confirmer.

Qualification finale épinglée sur Memory `42117af68e33ad36ea47e6112b12420147fd03bf`, qui restreint aussi les sous-classes de vue étendue. Code G254 publié dans Core `b770acb5888e2ee6c864d344a85bdcc8c91e8add` ; le changement de pin ne modifie pas ce module.

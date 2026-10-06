# G040 — lanceur candidat PowerShell/SSH : preuves

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G040](../../../../collaboration/tasks/C-TASK-G040.md).
Livrable : [desktop/connected/launchers/](../../../../desktop/connected/launchers/README.md).

## Ce qui a été exécuté

1. **Contrôles statiques** : [launcher.test.js](../../../../desktop/connected/tests/launcher.test.js),
   6/6. Ils vérifient :
   - l'encodage UTF-8 avec BOM, pour PowerShell 5.1 ;
   - la liaison `127.0.0.1:P:127.0.0.1:P` ;
   - le `--` avant la destination ;
   - qu'aucune option n'affaiblit SSH (`StrictHostKeyChecking`,
     `known_hosts`, pare-feu, services, installation, politique
     d'exécution) ;
   - que `Stop-Process` et `Remove-Item` sont limités à leur cible ;
   - qu'aucun jeton n'est lu ;
   - que le diagnostic distant est seulement `--check`.
2. **Exécution réelle sous Linux** avec PowerShell 7.4.6. Le binaire officiel
   a été téléchargé, son SHA-256 vérifié contre `hashes.sha256` de la
   publication, et il est resté hors du dépôt. Un `ssh.exe` **simulé**
   ([fake-ssh.py](fake-ssh.py)) journalise ses arguments et écoute sur le port
   comme un tunnel. [Script](run-linux.sh), [sortie](run-linux-output.txt).

| # | Cas | Résultat |
| --- | --- | --- |
| P0 | Analyse syntaxique PowerShell | 0 erreur |
| P1 | Serveur `-oProxyCommand=…`, utilisateur avec espace, port 80, diagnostic incomplet, chemin `a;rm` | refusés, **0 appel ssh** |
| P2 | Aperçu par défaut | commandes affichées, **0 appel ssh** |
| P3 | Port local occupé | refus avant toute connexion |
| P4 | Diagnostic distant en échec (code 2) | arrêt, **pas de tunnel** |
| P5 | Diagnostic réussi puis `-Connect` | tunnel lancé, port ouvert attendu, URL affichée, enregistrement `tunnel-18768.json` |
| P6 | Relance pendant le tunnel | sous Linux : « port utilisé » (voir limite) |
| P7 | `-Stop` | sous Linux : **refuse d'arrêter**, car le processus ne s'appelle pas `ssh` |

## Défaut trouvé par l'exécution, corrigé

`$remoteArgs.Count` échouait en mode strict quand un seul chemin distant (ou
aucun) était donné. Le script s'arrêtait alors sur une erreur PowerShell brute
au lieu du message prévu (P1, P3). Le tableau est maintenant toujours un
tableau.

## Limites (pas de PASS fictif)

- **Windows non exécuté.** Ni Windows PowerShell 5.1, ni vrai `ssh.exe`, ni
  invite d'empreinte ou de mot de passe, ni navigateur Windows.
- P6 et P7 dépendent du nom de processus. Sous Windows, `ssh.exe` donne le
  nom `ssh` : la détection « déjà actif » et l'arrêt devraient alors
  fonctionner. Ce n'est **pas vérifié**. Sous Linux, le contrôle d'identité
  refuse, comme prévu, d'arrêter un processus qui ne s'appelle pas `ssh`.
- En P7 sous Linux, l'enregistrement est retiré alors que le faux tunnel
  vit encore. Sous Windows, ce cas correspond à un PID réutilisé par un autre
  programme : l'enregistrement n'a alors plus de sens.

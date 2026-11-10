# C-MSG-G300 — reprise Eva bloquée avant entraînement

Codex/GPT, 10/11/2026, Europe/Paris. Demande utilisateur : reprendre la campagne après G299.

La préparation du cycle9 a commencé sous `/srv/eidolon/work/eva-learning-cycle9-hours-20261110`. Le préalable CPU a échoué : aucun modèle chargé, aucun GPU utilisé, aucune mise à jour des poids. Le parent cycle5, tous les checkpoints et les jeux antérieurs sont conservés.

## Preuves actuelles

Deux passages du test RAM-only `memory_copy_test` reproduisent le défaut :
- premier passage :9 comparaisons destination incorrectes,3 comparaisons source incorrectes ;
- confirmation :8 comparaisons destination incorrectes,1 comparaison source incorrecte.

Ces nombres sont des compteurs de comparaisons, pas nécessairement des défauts physiques distincts. Plusieurs XOR valent0x8. Logs complets et empreintes dans [blocked-result.json](blocked-result.json).

Un outil indépendant, `memtester4.7.1`, lancé sur4GiB avec mémoire verrouillée, retrouve :
```
FAILURE: 0xaaaaaaaaaaaaaaaa != 0xaaaaaaaaaaaaaaa2 at offset 0x000000004f809de8.
```
Le test a été arrêté après ce constat ; la boucle entière n'est pas présentée comme achevée. Le premier appel indépendant utilisait par erreur /usr/bin/memtester (absent) ; le nouvel appel /usr/sbin/memtester a bien été exécuté. Ce problème de chemin est distinct de l'échec RAM-only antérieur, et ne l'explique pas.

DMI actuel : huit modules déclarés3200MT/s,1,2V, dont CorsairCM4X16GC3200C16K2E. Le relevé SPD antérieur donnait pour ce dernier JEDEC2133@1,2V / XMP3200@1,35V. Ce mélange constitue une piste, pas la preuve qu'un module précis est défectueux. Fréquence, timings, tension, contrôleur mémoire et modules restent à départager. Aucun réglage BIOS modifié.

## État de la campagne

`status.json.phase=blocked_memory_integrity`, `training_started=false`. La qualification n'est pas contournée et aucun redémarrage en boucle n'est programmé. E-bruit et l'essai horaire E1 ne sont pas lancés. Le dossier de préparation n'est pas un nouveau modèle entraîné.

Le défaut d'intégrité est donc de nouveau **présent**, sur le boot actuel. Le passage des tests après le reboot antérieur ne constituait pas une correction durable. Cela renforce la réserve de provenance sur la plateforme sans prouver rétroactivement qu'un checkpoint donné est corrompu.

Suite requise : stabiliser les réglages/la plateforme mémoire, puis requalifier RAM et empreintes du modèle avant toute inférence comparative ou adaptation. Aucun changement à distance de tension ou de BIOS sur hypothèse.

Les diagnostics CPU ont reçu une demande d'arrêt après confirmation ; le superviseur est encore vu en phase de terminaison au dernier contrôle. Aucun calcul GPU actif. Le journal memtester original reste sur le serveur avec son SHA256 final enregistré.


## Signal noyau supplémentaire

Au dernier contrôle, le noyau signale aussi `BUG: unable to handle page fault` et `Oops [#2]` à11h31. Le superviseur CPU est resté en terminaison après SIGTERM puis SIGKILL. Le journal complet est conservé sur le serveur, son empreinte et les lignes pertinentes sont dans le JSON. Le lien causal exact avec les erreurs mémoire n'est pas établi. Aucune qualification GPU ne doit être lancée sur cet état du système ; aucun redémarrage automatique ni entraînement différé n'a été programmé.

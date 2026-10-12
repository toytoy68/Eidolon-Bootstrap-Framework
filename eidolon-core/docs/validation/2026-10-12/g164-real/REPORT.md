# Rejeu G164 réel et première brique profils G170-A — 12/10/2026

Base Codex e55ed67, intégration du commit Claude e80d097 dans un worktree
isolé. Aucun code G165–G169 encore intégré dans cette recette.

## Défauts corrigés avant adoption

Le filtre G164 rejetait inconditionnellement « Merci d'avoir regardé cette
vidéo », « Abonnez-vous à cette lettre » et « Sous-titres activés », même avec
no_speech_prob=0.01 et avg_logprob=-0.1. Reproduit avant correction alors que
les 76 tests existants passaient. Un contenu textuel suspect ne suffit plus :
le filtre exige aussi no_speech_prob>0.3 et avg_logprob<-1 ; idem pour l'écho
du glossaire. Sans scores, pas de rejet sur texte seul. Les tests bruit
existants utilisent désormais explicitement des scores incertains ; cinq
nouvelles régressions couvrent bonnes confiances, métadonnées absentes,
texte incertain et configurations de vocabulaire mal formées.

## Mesures réelles

Piper Siwis à vitesse 0.9, Whisper small CPU int8, 2 threads, beam_size=1.
11 phrases synthétiques distinctes, 7 variantes bruitées, 4 cas silence/bruit
seul ; 22 cas identiques par réglage, 132 transcriptions au total. Aucune
capture micro ou personne réelle. Rééchantillonnage simple du banc Claude ;
les résultats ne sont pas une qualification acoustique humaine.
Le banc étendu ajoute les trois formulations rejetées, écrit les résultats
après chaque réglage et libère le modèle pour éviter six chargements cumulés.

| Réglage | WER moyen | WER contrôles | Noms tous corrects | Texte sur silence/bruit | Durée totale s |
|---|---:|---:|---:|---:|---:|
| baseline | 0.247 | 0.125 | 0/7 | 0/4 | 77.4 |
| guards | 0.247 | 0.125 | 0/7 | 0/4 | 70.2 |
| replace | 0.199 | 0.125 | 2/7 | 0/4 | 69.8 |
| prompt | 0.058 | 0.000 | 5/7 | 0/4 | 70.4 |
| hotwords | 0.167 | 0.188 | 5/7 | 2/4 | 70.2 |
| prompt+vad | 0.058 | 0.000 | 5/7 | 0/4 | 64.2 |

WER = moyenne par phrase des erreurs sur les mots, pas un taux de personnes
reconnues. Les contrôles incluent les formulations légitimes de générique.
Le banc conserve ses normalisations limitées des nombres : comparaison
relative sur mêmes références. Aucune régression phrase par phrase sur les
contrôles ou nombres avec prompt. Deux erreurs de noms subsistent sur sept.
Hotwords est rejeté : « Eidolon toytoy » inventé sur deux bruits seuls et une
phrase de contrôle dégradée. Les filtres ne garantissent donc pas une absence
générale d'hallucinations. Les temps sont indicatifs d'un seul passage ; tests
légers en parallèle sur la VM, aucun classement fin de performances revendiqué.

Choix : vocabulary=default, bias=prompt, vad=false. Prompt+vad donne la même
qualité sur ce lot ; garder le comportement VAD existant jusqu'aux essais de
voix faibles/courtes sur le PC. Configuration à appliquer après publication.

## Vérifications et profils

81 tests communication réussis sous -X dev ; 130 Node réussis, 26 ignorés
(navigateur non exécuté dans cette suite). 12 tests profile_plan réussis.
La suite complète Core n'a pas été relancée ; les anciens 1591 ne sont pas
attribués à ce lot. Le validateur de vocabulaire a reçu son contrôle de type
pendant le banc ; la logique de transcription/filtrage mesurée est inchangée.

G170-A : validateur pur, résultat immuable, noms/alias/roles/politique stricts,
aucune I/O, aucun compte ou session activés. Plan privé réel validé avec
résumé sans noms : trois profils, un admin et deux casual. Stockage actif,
authentification, isolation mémoire et reconnaissance restent à implémenter.

Déploiement : non effectué à la rédaction initiale ; voir complément daté.

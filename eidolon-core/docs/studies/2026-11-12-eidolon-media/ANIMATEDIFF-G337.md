# G337 - Reprise et diagnostic AnimateDiff

13 novembre 2026, Codex/GPT. Base edde825. Reprise explicitement demandee par toytoy.

## Resultat

G336 run02 retrouve termine (6 clips), mais sans revue finalisee. Les apercus sont des textures sans scene identifiable. G337 teste uniquement le passage DDIM scaled_linear -> linear, recommande par la documentation officielle Diffusers, avec memes poids, prompts, seeds, tailles, precision et nombre d'etapes. Six nouveaux clips termines, tous rejetes visuellement. Repetition seed42 identique pixel par pixel et MP4 identique. Un fichier valide et une seed reproductible ne prouvent pas une scene correcte.

Controle causal supplementaire : SD1.5 seul, memes poids de base, meme VAE/CLIP, prompt bateau, seed42, 512x512, 20 etapes. Deux reglages DDIM produisent des images reconnaissables (bateau, lac, montagne). Le defaut est donc localise a la chaine AnimateDiff testee ; cause precise non determinee. Ce lot ne demontre pas que le modele AnimateDiff est generalement incapable, ni que tous les autres composants sont exempts de defauts.

## Mesures reelles G337

| Condition | Temps encodage/calcul/decodage | Sortie |
| --- | --- | --- |
| Controle 256x256, 8 images, 8 etapes | 8,80 s | 1 s a 8 fps |
| Bateau 512x512, seeds42/43, 16 images,20 etapes | 86,01 / 84,67 s | 2 s a 8 fps |
| Repetition bateau seed42 | 84,93 s | Identique pixel/MP4 |
| Espace 512x288, seeds42/43 | 47,74 / 47,62 s | 2 s a 8 fps |

GPU0 : 8676 Mio maximum, GPU/HBM 41/43 degres C ; consigne300W, pic echantillonne335,59W. GPU1 au repos. CPU Tdie48,625C maximum. Aucune erreur de sonde. Pas de mesure a la prise revendiquee pour G337. Les temperatures concernent ce lot court, pas une validation thermique prolongee.

## Methode et preuves

- Poids figes et SHA256 verifies par le runner ; aucun telechargement pendant inference.
- Generation exclusivement locale, IPAddressDeny=any et localhost autorise, HF/Transformers offline. Aucune API cloud.
- Torch2.6.0+cu124, Diffusers0.32.2 existants. Aucun changement pilote ou runtime.
- Verrou campagne et controle des processus GPU. Temperature GPU65C/HBM70C maximum admis par garde ; aucun seuil atteint.
- Revue GPT des premieres/milieu/dernieres images de chacun des six clips et de la planche16images du bateau seed42. Pas une mesure objective de fluidite. Les scenes sont absentes dans les extraits, ce qui suffit au rejet.
- G336 : 253 tests decouverts, 248 reussis/5 ignores dans le journal retrouve ; execution historique non reattribuee a cette reprise. G337 : 6 generations reelles, verification MP4, non-fini, repetition et 2 controles SD15. Pas de nouvelle suite complete revendiquee.
- Preuves machine : [animatediff-validation-g337.json](animatediff-validation-g337.json).
- Originaux sur X399 : /srv/eidolon/workspaces/media-20261112/animatediff-g336/run02 et animatediff-g337/{run01,sd15-control}. Les echecs sont conserves.

## Etat final et suite

Deux jobs G337 termines code0, GPU liberes, Core API/Comm/Ollama/Darme/tunnel Memory actifs. Presence des services controlee, pas recette de non-regression exhaustive. Machine laissee allumee, consigne300W conservee. Aucun entrainement, aucune promotion, aucune integration API.

AnimateDiff V04 reste NON VALIDE ; prochaine investigation : comparer pipeline amont, precision et processeurs d'attention, une variable a la fois. La file des autres modeles reste ouverte. FLUX.1 dev est deja en I10, non teste ; FLUX.2 dev32B en I16, etude quantification/offload. Aucun resultat Schnell transfere implicitement a dev.

Source primaire : https://huggingface.co/docs/diffusers/api/pipelines/animatediff (consultee le13/11/2026). Le changement de beta schedule seul n'a pas resolu le defaut.

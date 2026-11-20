# Protocole rôles LLM et Eva - 20 novembre 2026
ECT - Local AI • Modular • Reliable • Reproducible

Autorisation directe toytoy. Base Git d61792d883e7dc4ecc611a072d76f1e50f1c77ee.
Campagne isolée, aucun déploiement ni modèle promu automatiquement.

## Pourquoi réviser
Les quatre sondes précédentes et les tok/s ne qualifient pas un rôle. Le raisonnement affiché par llama-completion doit être séparé de la réponse finale. Un modèle qui se charge n'est pas un contrôleur de robot validé. Les six anciens petits modèles Darme n'avaient pas satisfait le contrat sémantique : cet échec reste dans l'historique.

## Banc de rôles préenregistré
48 tâches synthétiques fermées : 12 robot, 12 triage Darme, 12 soutien système, 12 raisonnement/temporologie ; 4 conversations ouvertes relues qualitativement.
Chaque famille combine cas ordinaires, frontières, données absentes/périmées et instructions injectées dans une donnée non fiable. Politique et oracles déterministes figés avant toute réponse.
JSON natif sans grammaire forcée pour mesurer le respect spontané du contrat. Score strict = objet entier exactement conforme, types JSON compris ; score de contenu séparé après extraction éventuelle. Une clôture de raisonnement ne suffit pas à masquer un résultat faux.
llama-server v1 natif sm70, template GGUF Jinja, reasoning_effort=none et enable_thinking=false, réponse finale/reasoning_content conservés séparément. 512 tokens maximum, température 0, seed 1234, contexte 4096, une requête à la fois, GPU0 à 200 W. Aucun outil réel fourni aux modèles.
Durée requête, TTFT de contenu via streaming, tokens et débit observés ; distinguer chargement à froid et latence à chaud. Les prompts courts ne mesurent pas la capacité de contexte long. Compteur secteur machine entière, pas énergie intrinsèque du modèle.
Même protocole pour LFM2.5, SmolLM3, Phi-4 mini, Falcon3, LFM3, Prism Q2_0, Eva GGUF source et Qwen2.5 témoin. Les variantes de runtime ou formats 1 bit restent des études distinctes.
Classification : compatible techniquement ; contrat synthétique satisfait (12/12 stricts, zéro cas critique raté) ; candidat sous réserve ; non retenu pour ce contrat. Même 12/12 ne constitue pas une validation terrain ni une autorité d'action.
Robot : intention proposée seulement, arrêt/capteurs/anti-collision déterministes hors LLM. Aucun essai physique N6000/WALL-E.
Darme : explication et triage seulement, décision de sécurité indépendante et audit obligatoire. Pas d'accès aux secrets.
Soutien actif : diagnostic/plan lisible ; exécution via permissions et contrôles logiciels. Pas de shell arbitraire délégué.
Conversation : revue française, correction de faits, incertitude, synthèse ; aucune note de goût présentée comme vérité utilisateur.
Embeddings, vision, STT/TTS ont des contrats distincts ; ne pas les compter comme chats validés.

## Eva : expérience E5, diminution de dose
Référence acceptée = adaptateur cycle5 SHA c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30.
E4b-1 avait gagné X1 47→81/96 mais rapport 86→83/320 et jour0 55→52/64 : candidat écarté, pas de continuation E4b-2.
Hypothèse E5 : réduire le taux maximal de 3e-6 à 1e-6 peut préserver les acquis. Même données, ordre, packing, NF4/FP16, r8 alpha16, graines et protocole d'évaluation. Ce n'est pas une promesse de gain.
102 mises à jour, puis 204 uniquement si toutes les gardes initiales passent. Gardes inchangées : rapport >= parent-2 ; jour0 >= parent-1 ; acquis >=25/32 ; pas de bascule de format ; primitives et SG >= parent-1. Les gains X1/X2/X3 et les comparaisons appariées restent exploratoires.
Recalcul intégral du parent, répétitions et rechargements ; pas de réutilisation des réponses en cache. Jeux de validation historiques déjà connus explicitement signalés ; ancien test final réservé non évalué, aucune prétention de nouvelle validation aveugle.
Précontrôles RAM même boot, doubles SHA des poids, smoke 4 updates distinct, NCCL et sauvegardes complètes, gardes températures/ECC/noyau/secteur. Deux V100 à 200 W. Toute garde échouée arrête la suite, sans assouplissement.
Nouvelle validation indépendante requise avant adoption, même si cet essai réussit. Sauvegarder candidats et rejets ; conserver cycle5 en référence.

## Clôture
Archiver réponses, erreurs, code, versions, SHA, consommation et conclusions ; publier les preuves synthétiques sans secrets/corpus privé. Vérifier l'enregistrement, arrêter les services temporaires, éteindre proprement la VM Memory puis X399. Confirmer extinction sur le Shelly X399 (<5 W), NAS laissé en service.

## Addendum apres le passage libre, avant le passage structure
Le passage libre montre des violations de schema et de decision distinctes. Un second passage exploratoire conserve les 48 questions et les sorties libres, mais contraint le JSON par schema : cles/types et ensembles de valeurs autorisees uniquement, jamais la reponse attendue. Les scores restent separes ; aucune pretendue validation aveugle apres lecture des erreurs. Aucun outil execute.

## Extension avant E5
Ajout des temoins locaux Qwen3-14B, Qwen3-30B-A3B et Gemma4-12B pour la fonction soutien systeme. E5 evalue aussi les 52 prompts de roles sur parent/candidat (NF4, 384 tokens, lots16), comme diagnostic de transfert sans selection sur ces scores. Aucun de ces prompts nest ajoute au train.

## Correction de classification Qwen30 avant nouveau passage
Lecture GGUF : le tag local qwen3:30b contient Qwen3-30B-A3B-Thinking-2507 (general.finetune=Thinking). Son template ouvre toujours think : enable_thinking=false ne peut pas le transformer en Instruct. Les passages 512 tokens sont conserves comme tests de budget/integration inadaptés, pas comme mesure de capacite maximale. Nouveau passage exploratoire des 48 questions : contexte12288, sortie8192, temperature0.6/top_p0.95/top_k20, seed1234, raisonnement autorise et final separe. Scores et latences distincts du groupe rapide. Source auteur : https://huggingface.co/Qwen/Qwen3-30B-A3B-Thinking-2507 .

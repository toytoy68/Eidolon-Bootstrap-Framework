# Lecture des résultats N6000

Le corpus est un test de contrats fermés, pas un examen général de conversation ou d'autonomie. Les réponses attendues des 36 cas (12 par rôle, dont 23 critiques au total) ont été vérifiées par un oracle séparé. Les trois sondes de conversation restent qualitatives.

Les règles, poids, schémas JSON, température nulle, graine, budget de 128 tokens et entrées n'ont pas été modifiés après observation des réponses. La réduction initiale de 16 répétitions de texte neutre à une conserve les champs courants et les injections. Le contexte long est donc un diagnostic séparé. Les scores V100 historiques portent sur un autre contexte et une autre recette : aucun écart ne doit être attribué au seul CPU.

Le premier profil sans plafond a atteint la garde thermique. Ses réponses incomplètes ne sont pas des échecs de raisonnement. Le profil à trois threads et 2 GHz a ensuite été utilisé. Après 33 réponses terminées, le refroidissement à 65°C en cinq minutes s'est révélé trop contraignant : le package CPU avait baissé à 63°C, tandis que la sonde ACPI TCPU était encore à 71,05°C. Ces réponses sont conservées une seule fois. La continuation utilise un seuil de reprise de 70°C et un délai maximal de vingt minutes ; la pause au-delà de 75°C et l'arrêt à 85°C restent inchangés.

Les délais mesurent une requête sans cache de préfixe, pas une conversation optimisée avec historique partagé. Les services dashboard et modèle local existants sont restés actifs ; le service vocal était initialement inactif. La RAM indiquée est le RSS maximal du serveur testé, pas la consommation totale de la machine.

Le score brut doit être comparé à une décision constante. Darme contient dix attentes BLOQUER sur douze : tout bloquer suffit à obtenir 10/12 sans reconnaître les cas OBSERVER et VERIFIER. Les matrices de confusion et moyennes des rappels par classe sont ajoutées comme analyse descriptive après observation ; elles ne réécrivent pas les critères ou les réponses. Les seuils de dépistage prévus étaient tous les cas critiques corrects et un p95 du premier contenu inférieur à deux secondes pour les intentions ; la cible du premier contenu de chat était de cinq secondes. Leur réussite éventuelle ne donnerait aucune autorité d'exécution.

L'énergie RAPL package est une estimation du processeur incluant l'activité de fond. Les fenêtres de requêtes sont réunies avant addition pour éviter les doubles comptes entre échantillons voisins ; les pauses et reprises sont séparées. Les durées complètes ne sont pas un classement d'efficacité comparable, notamment pour le modèle repris. La puissance électrique à la prise de WALL-E n'a pas été mesurée.

Pour la suite : corpus équilibré entre décisions, paires strictement identiques sauf la note malveillante, plusieurs formulations et conversations inédites. Une erreur en présence d'une injection ne démontre pas à elle seule que l'injection en est la cause. Les commandes moteur, arrêts d'urgence, permissions et contrôles de fraîcheur restent des règles indépendantes du LLM.

Les quatre GGUF déclarent general.file_type=15, soit Q4_K_M dans le llama.h épinglé. Le fichier Qwen3 0,6B existant porte le nom interne « Qwen3 0.6B Instruct Awq ». Ce nom seul ne reconstitue pas sa chaîne de conversion : les résultats qualifient le fichier dont le SHA-256 est fourni, pas toutes les variantes de cette famille.

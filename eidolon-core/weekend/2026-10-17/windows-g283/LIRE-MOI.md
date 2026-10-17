# Eidolon — lanceur Windows G283

1. Extraire tout le ZIP dans un dossier permanent, par exemple Documents/Eidolon.
2. Garder le tunnel Eidolon habituel ouvert.
3. Double-cliquer **Eidolon.exe**, avec le E bleu. Le premier appairage peut demander le mot de passe SSH ; les suivants utilisent le stockage chiffre Windows existant.
4. Pour un raccourci Bureau, lancer **Creer-raccourci.cmd** une fois. Il pointe vers Eidolon.exe et conserve son icone.
5. Pour la barre des taches : clic droit sur **Eidolon.exe** ou son raccourci Bureau, puis **Afficher plus d'options > Epingler a la barre des taches**, selon la version de Windows.

Conserver tous les fichiers ensemble et creer le raccourci apres avoir choisi le dossier definitif. Le lanceur ne deplace pas les fichiers. Un raccourci Bureau Eidolon existant est conserve ; supprimez-le ou renommez-le avant de recreer celui-ci.

Lancer directement eidolon-consultation.exe contourne l'appairage automatique : utiliser Eidolon.exe comme point d'entree.
Une console PowerShell peut apparaitre pendant l'ouverture ; elle se ferme une fois le client lance. Le tunnel SSH reste separe. Aucune cle secrete n'est fournie dans le paquet. Le binaire n'est pas signe.

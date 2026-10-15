# Documents PC et NAS — G272

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

## Parcours livré

Ouvrir une conversation avec une clé appairée dont le profil autorise les services.
Pour un fichier PC, sélectionner le fichier puis cliquer **Envoyer à Core pour
extraction et aperçu**. La sélection seule ne transmet rien. Pour le NAS, choisir
l’action `document.read`, une racine autorisée et un chemin relatif. Core fixe le
profil ; le navigateur ne peut pas le choisir dans la requête.

Lire l’extrait, ses limites et son empreinte avant de confirmer. Le reçu porte
`EXTRACTED_NOT_REMEMBERED` : aucune écriture Memory n’a encore eu lieu. Un document
NAS modifié depuis l’aperçu est refusé, avec reçu incertain conservé. Les anciens
reçus sont accessibles par pagination. Un fichier PC est lié à son nom et au SHA
des octets ; la même clé de demande ne peut pas servir à un autre document.

Choisir ensuite **Analyser dans le dialogue** ou préparer une mémorisation.
L’analyse utilise une observation non vérifiée et l’extrait borné du dialogue ;
elle ne télécharge pas à nouveau le document. La mémorisation est une seconde
action avec aperçu et confirmation : elle conserve l’extrait et sa provenance,
pas le fichier binaire complet. Son statut reste UNVERIFIED. Un profil sans droit
d’écriture ne dispose pas de ce bouton.

## Formats et limites

| Format | Extraction | Limites explicites |
| --- | --- | --- |
| TXT, MD, CSV | Texte UTF-8 | Pas d’interprétation Markdown ni de calcul CSV |
| PDF | Texte des 100 premières pages via `/usr/bin/pdftotext` | Aucun OCR ; scan sans texte inexploitable ; mise en page imparfaite |
| DOCX | Paragraphes et tableaux du corps principal | En-têtes, notes, images et révisions non reconstruits |
| ODT | Paragraphes et titres | Espacements et mise en page simplifiés |
| XLSX | Chaînes et valeurs mises en cache | Aucune formule exécutée ; dates/nombres bruts, feuilles cachées non distinguées |
| PPTX | Texte des diapositives, ordre numérique des fichiers | Notes/images exclues ; ordre personnalisé non reconstruit |

PC : **512 Kio** binaires maximum. NAS : **4 Mio**. Texte extrait : **16 000
caractères**, troncature signalée ; la source envoyée au dialogue reste limitée à
son propre budget de 3 600 caractères. Une extraction partielle ne vaut pas
lecture complète. Les formats anciens DOC/XLS/PPT, fichiers chiffrés, macros VBA détectées et
archives arbitraires sont refusés. Les lectures UTF-8 historiques restent disponibles.

Sur la VM candidate Linux, prévoir `poppler-utils` avec l’environnement de recette.
Son absence produit une erreur explicite pour PDF ; aucune installation automatique.
Les autres formats utilisent la bibliothèque standard Python.

L’extraction s’effectue dans un processus jetable : délai parent 8 s, CPU 5 s,
mémoire virtuelle 512 Mio ; PDF possède son propre délai de 4 s. Archives bornées
à 512 entrées et 16 Mio décompressés, chemins dangereux, macros, DTD/entités XML
refusés. Il ne s’agit pas d’une isolation noyau complète. Les documents restent
des entrées non fiables, jamais une autorisation d’exécuter leurs instructions.

Le binaire n’est pas persisté par ce parcours. Extraits, noms et empreintes sont
des données privées conservées dans les reçus et éventuellement dans le dialogue.
Aucun effacement sécurisé des copies HTTP, de la RAM native ou des sauvegardes
n’est promis. Aucune synchronisation automatique de bibliothèque n’est activée.

## Recette sur place

Compléter G11–G13 : fichier PC et NAS de chaque format retenu ; PDF textuel et
scan ; extrait long ; nom inhabituel ; fichier changé après aperçu ; macro,
archive excessive et document chiffré ; plusieurs reçus volumineux ; lecture seule
et tentative interprofil. Vérifier séparément analyse, mémorisation et reprise
après réponse perdue. Le contenu privé ne doit pas entrer dans les journaux publics.

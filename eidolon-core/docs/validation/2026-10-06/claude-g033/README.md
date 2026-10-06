# G033 — frontières APT de `02-nvidia.sh`

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G033](../../../../collaboration/tasks/C-TASK-G033.md).
Autorisation de toytoy pour rectifier les trois scripts (relayée en C040).
Base : `1fed0ba`. Seule la fonction `add_debian_components` de
`02-nvidia.sh` change. **Aucun installateur exécuté ni sourcé** : le test
extrait le texte de la fonction et l'exécute avec bash sur des fichiers
fictifs, dans un dossier temporaire. Aucun fichier système, aucun `apt`.

```sh
python3 eidolon-core/docs/validation/2026-10-06/claude-g033/test_apt_boundaries.py            # après
python3 eidolon-core/docs/validation/2026-10-06/claude-g033/test_apt_boundaries.py <ancienne copie>
```

- [avant (`1fed0ba`) : 13 échecs sur 23](test-before-1fed0ba.txt)
- [après : 23/23](test-after.txt)
- [ancien test C040 rejoué : OK](c040-test-rerun.txt)
- [bash -n des trois scripts, shellcheck -S warning, version de awk](scripts-check.txt)
  (mawk 1.3.4, l'awk par défaut de Debian)

## Règles maintenant appliquées

- **Périmètre explicite** : seuls `deb.debian.org`, `security.debian.org`,
  `ftp.debian.org` et `ftp.<deux lettres>.debian.org`, en http(s), avec le
  chemin exact `/debian` ou `/debian-security`. On compare l'hôte et le chemin
  **entiers**, jamais une sous-chaîne : `deb.debian.org.evil.example` et
  `mirror.example/deb.debian.org/debian` restent intacts.
- **Ligne `deb`** : les composants sont ajoutés **avant** un commentaire de
  fin de ligne. Les options `[ … ]`, même avec des espaces, sont sautées. Des
  options non fermées sont signalées et la ligne reste intacte.
- **deb822** : la strophe est traitée en entier. Elle n'est modifiée que si
  **toutes** ses URIs sont officielles (lignes de continuation comprises) et
  si `Components:` tient sur une ligne. Sinon elle reste intacte, avec un
  diagnostic. Commentaires et noms de champs en minuscules sont gérés.
- **Diagnostic** : chaque forme non prise en charge ou source tierce avec
  `main` est écrite sur la sortie d'erreur (`fichier:ligne: … ; laissé
  intact`). L'installation continue.
- **Écriture** :
  - fichier temporaire créé par `mktemp` à côté du fichier ;
  - fichier **non réécrit** s'il ne change pas (même inode, même date) ;
  - droits et propriétaire copiés avant `mv` ;
  - en cas d'échec, le temporaire est supprimé et le code de retour n'est pas
    nul (donc `error`) ;
  - aucune migration de format.

## Avant / après

| Cas | Avant | Après |
| --- | --- | --- |
| `… trixie main # commentaire` | composants ajoutés **après** le `#` (inactifs) | avant le `#` |
| `deb https://vendor.example/debian trixie main` | modifiée | intacte + diagnostic |
| domaine ou chemin piège | modifiés | intacts |
| deb822 tierce, mêlée, URI en continuation | modifiées | intactes + diagnostic |
| deb822 `Components:` multiligne | modifiée sur la 1re ligne | intacte + diagnostic |
| deb822 champs en minuscules | non traités | traités |
| second passage | fichier réécrit | non réécrit |
| fichier absent | temporaire laissé | rien créé, échec |

## Limites et point à décider

- Un **autre miroir** (miroir universitaire, cache local `apt-cacher-ng`,
  proxy) n'est **pas** modifié, seulement signalé. Si la VM utilise un tel
  miroir, `nvidia-driver` (dans `non-free`) ne sera pas trouvé et
  l'installation échouera plus loin, avec un message clair. Il faut alors
  ajouter les composants à la main ou faire une liste de miroirs acceptés :
  c'est à toytoy de décider.
- Pas d'essai sur la VM réelle ni avec `apt update` ; le comportement d'apt
  sur ces fichiers n'est pas vérifié ici.
- Testé avec mawk 1.3.4 seulement (pas gawk ni busybox awk).

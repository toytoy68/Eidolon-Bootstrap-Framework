# E2 — Index documentaire Eidolon ciblé : étude

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Lot attribué par G190.
Statut : **étude**. Aucune collecte, aucun téléchargement de dump, rien
d'installé. Fait suite à la
[première étude](2026-10-12-own-search-engine-study.md).

Les chiffres viennent de recherches Web du 12/10/2026 et sont **à vérifier**
sur les pages officielles. Mon réseau bloque la plupart d'entre elles, et
certaines valeurs datent d'avant 2026.

## 1. But et frontières

- Répondre à des questions **documentaires** avec des sources choisies,
  datées et citables, sans dépendre d'un moteur extérieur.
- **Distinct du Memory Engine privé** :
  - autre stockage, autre collection Qdrant, aucun lien de données ;
  - aucune donnée personnelle indexée ;
  - aucune requête privée ne sert à alimenter l'index.
- Il complète SearXNG, il ne le remplace pas : l'index pour nos sujets,
  SearXNG pour le reste.

## 2. Sources candidates (choix final : toytoy)

| Source | Obtention | Licence | Taille indicative | Mise à jour | Vérifié ? |
| --- | --- | --- | --- | --- | --- |
| **Wikipédia FR** | dump officiel `frwiki-…-pages-articles-multistream.xml.bz2`, sans exploration | CC BY-SA, attribution et même licence pour les extraits redistribués | environ 6,8 Go compressé (dump du 01/06/2025) ; 5,3 Go en 2022 | dumps environ mensuels (enwiki daté du 1er) ; calendrier frwiki à confirmer | taille 2025 : site tiers (Academic Torrents) ; calendrier : non |
| Wikipédia FR via Kiwix (ZIM `nopic`) | fichier ZIM | CC BY-SA | environ 75 % plus petit que la version avec images (FAQ Kiwix) ; taille FR 2026 inconnue | mensuelle ou plus lente | non |
| **ArchWiki** | paquet `arch-wiki-docs` (HTML hors ligne), sans exploration | GFDL 1.3 ou ultérieure | petite (quelques centaines de Mo, à mesurer) | paquet daté (20260401) | licence : oui (paquet) ; taille : non |
| Documentation Python | archive HTML officielle | licence de la documentation PSF, **à vérifier** | quelques dizaines de Mo | à chaque version | non |
| Documentation Proxmox VE, Debian | site ou paquets (`debian-handbook`, etc.) | **à vérifier** au cas par cas | petite | à chaque version | non |
| Flux RSS d'actualité choisis | flux officiels | titres et liens seulement ; pas les articles | très petite | quotidienne | — |

**Priorité** : obtenir des **archives officielles** (dumps, paquets), pas
explorer de site en site. Le robot d'exploration (E3) n'est utile que pour
une source sans archive, et seulement sur décision de toytoy.

## 3. Stockage estimé (Wikipédia FR seule, plus grosse source)

- Environ 2,6 millions d'articles, ordre de grandeur à vérifier ; texte
  utile extrait de quelques Go, à mesurer.
- **Index lexical** (SQLite FTS5 ou équivalent) : du même ordre que le
  texte.
- **Vecteurs**, tout l'article découpé : de 10 à 30 millions de morceaux.
  À 1 024 dimensions en float32, cela ferait 40 à 120 Go, **trop lourd au
  départ**.
- **Proposition** :
  - vecteurs seulement pour le **résumé d'introduction** de chaque article
    (environ 2,6 millions de vecteurs, soit environ 10 Go en float32,
    environ 2,5 Go en int8) ;
  - lexical pour tout le texte.
- À mesurer sur un échantillon avant de décider (C162-Q2 : place disque des
  VM).

## 4. Chaîne proposée (rien n'est lancé)

1. Téléchargement **manuel et explicite** du dump, avec vérification des
   empreintes publiées par Wikimedia ; journal de provenance (URL, date,
   SHA).
2. Extraction en flux : texte, titre, révision, date ; balises de modèle
   retirées. Aucun contenu exécuté.
3. Découpage aux limites de phrase, avec la même prudence que A5-02 : la
   négation reste dans le morceau.
4. Index lexical, puis vecteurs du résumé. Modèle d'embedding de G182, à
   confirmer.
5. Fournisseur `eidolon-index/1` dans `ResearchCoordinator`. Chaque
   résultat donne la source, la révision, la date du dump et la licence.
6. **Mise à jour** : par dump complet, en reconstruisant dans une nouvelle
   génération puis en basculant (même principe que Qdrant G179, avec retour
   arrière). Pas de mise à jour partielle au début.

## 5. Évaluation (avant toute mise en service)

- Corpus de **questions figé avant l'essai**, comme le corpus Memory v1 :
  - 30 questions documentaires, avec la bonne page et la bonne révision
    attendues ;
  - 5 questions sans réponse dans l'index : il faut s'abstenir ;
  - 5 pièges de négation.
- Mesures :
  - rappel au rang 1 et au rang 5 ;
  - abstention ;
  - latence ;
  - taille sur disque ;
  - comparaison lexical seul, puis lexical plus vecteurs.
- **Échantillon d'abord** : 10 000 articles, pour mesurer avant de prendre
  tout le dump.

## 6. Limites

- Les données datent du **jour du dump** : la date est affichée avec
  chaque réponse, sans prétendre à l'actualité.
- Licences : CC BY-SA et GFDL imposent attribution et même licence si l'on
  **redistribue** ; un usage local avec citation est le cas le plus simple.
  À confirmer source par source.
- Le contenu indexé est une **donnée non fiable** : une page de wiki peut
  contenir une consigne piégée.
- Pas de RSS ni d'exploration sans liste blanche validée par toytoy.

## 7. Décisions à prendre

- **toytoy** : liste des sources, et quelle VM et quelle place disque.
- **GPT** : provisionnement, frontière avec Memory (contre-revue prévue par
  G190) et place dans la politique (`web.search` ou capacité distincte
  `index.search`).
- **Ensemble** : seuil « échantillon réussi » avant de prendre le dump
  complet.

## Sources

- [Academic Torrents, frwiki-20250601 multistream](https://academictorrents.com/details/63a083c3b5e0ecc6fd524f0c699853c4a45a4054)
- [frwiki, dump 20220620](https://ftp3.us.freebsd.org/pub/wikimedia/dumps/frwiki/20220620/)
- [enwiki, dump 20260801](https://dumps.wikimedia.org/enwiki/20260801/)
- [Wikipedia:Database download](https://en.wikipedia.org/wiki/Wikipedia:Database_download)
- [FAQ Kiwix](https://legacydev.kiwix.org/en/?p=41)
- [Kiwix (Wikipédia)](https://en.wikipedia.org/wiki/Kiwix)
- [arch-wiki-docs 20260401](https://archlinuxarm.org/packages/aarch64/arch-wiki-docs)
- [ArchWiki talk:Copyrights](https://wiki.archlinux.org/title/ArchWiki_talk:Copyrights)

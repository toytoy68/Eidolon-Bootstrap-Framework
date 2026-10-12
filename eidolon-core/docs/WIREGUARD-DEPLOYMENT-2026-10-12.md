# WireGuard pour Eidolon — installation du 12/10/2026

Auteur : Codex/GPT. Autorisation directe de toytoy à 13 h 45 Europe/Paris :
« tu peux installer wireguard ? ». Base documentaire : 3a2ed8f.
Lot pris en charge : installation VPN sur Core et compte rendu ;
aucune modification concurrente des fichiers UI Claude.

## Réalisé et observé

- Debian 13 Core, noyau 6.12.100+deb13-amd64 avec module WireGuard.
- Paquet officiel wireguard-tools 1.0.20210914-3 installé. nftables déjà présent.
  Aucun changement de noyau, aucune mise à niveau générale ou suppression.
- Interface wg-eidolon, adresse 10.77.100.1/24, port UDP 51820.
- wg-quick@wg-eidolon actif et activé au démarrage ; restart réussi.
  Démarrage après reboot non testé.
- Profil phone-01 préparé pour 10.77.100.2/32, route client limitée à
  10.77.100.1/32, keepalive 25 s. Clés et PSK générées sur la VM uniquement.
  Configuration root:root 0600, dans /etc/wireguard (0700).
  Cohérence clé publique/PSK client avec le pair serveur vérifiée après restart.
- Profil stocké comme phone-01.conf.pending : endpoint non validé, non importé.
  Ne pas publier ce fichier, un QR associé, les clés ou la PSK dans Git/chat.
- Table nft dédiée inet eidolon_vpn, chargée avant l'interface et supprimée
  à son arrêt. Autorise vers l'adresse VPN uniquement ICMP echo et TCP 443 ;
  bloque les autres entrées du VPN et tout transit entrant/sortant du VPN.
  Les règles des autres interfaces ne sont pas modifiées.
- ip_forward reste à 0. Aucun NAT, aucune route par défaut remplacée.
- API Core, communication, monitoring et DARME toujours actifs après opération.
- Sauvegarde préalable règles/routes : /var/backups/eidolon/wireguard-20261012.

## Validation réelle locale

Client WireGuard temporaire dans un espace réseau Linux séparé, socket de
transport créée sur l'hôte avant déplacement de l'interface :
- handshake chiffré et ping via tunnel réussis ;
- connexion TCP 443 autorisée et réponse attendue reçue ;
- SSH vers IP VPN bloqué ;
- SSH vers IP LAN Core et Memory bloqué ;
- pair/interface/espace réseau et serveur de recette supprimés.
Le serveur de recette TCP 443 utilisait HTTP temporaire : ce résultat ne
valide PAS HTTPS, un certificat, le navigateur mobile ou l'interface Eidolon.
Un premier appel de recette visait par erreur le port 80 ; le délai dépassé
a été corrigé en ciblant explicitement 443. Aucun élargissement du filtrage.

Preuve locale : /etc/wireguard/validation-20261012.json.
L'interface réelle et la configuration sont conservées après la recette ;
le pair téléphone reste préparé sans connexion observée.

## À terminer avant usage extérieur

1. Accès authentifié à Freebox OS : l'API de connexion répond 403 sans
   authentification ; aucune redirection n'a été créée.
2. Vérifier la plage de ports IPv4 allouée. Redirection UDP d'un port externe
   autorisé vers le port 51820 de Core. Ne pas ouvrir directement l'API Core.
3. Finaliser l'endpoint du profil téléphone avec ce port, puis remettre le
   profil par un canal local contrôlé pour import dans l'application WireGuard.
4. Essai téléphone en 4G/5G (Wi-Fi coupé), révocation et reconnexion.
5. Déployer la vue mobile et son HTTPS sur l'adresse VPN TCP 443 avec un nom
   et un certificat reconnus par le téléphone, notamment pour le micro.
   Actuellement aucun service permanent n'écoute sur ce port.
   Garder les contrôles de session/profil Core : VPN ne vaut pas connexion
   administrateur et ne remplace pas G170-B.

La solution choisie est WireGuard auto-hébergé. Le MCP existant via Cloudflare
reste distinct. Aucun tunnel web public mobile n'a été créé.

## Arrêt / retour arrière

sudo systemctl disable --now wg-quick@wg-eidolon

Cette commande retire interface, route VPN et table nft dédiées via wg-quick.
Les clés restent stockées pour reprise ; leur suppression/révocation constitue
une opération séparée. Ne pas restaurer globalement un ancien ruleset au risque
d'écraser des règles ajoutées depuis. Aucun service Eidolon n'a été reconfiguré.

## Références primaires

- https://www.wireguard.com/install/
- https://www.wireguard.com/quickstart/
- https://wiki.nftables.org/
- https://assistance.free.fr/articles/configurer-de-maniere-avancee-mon-routeur-freebox-354

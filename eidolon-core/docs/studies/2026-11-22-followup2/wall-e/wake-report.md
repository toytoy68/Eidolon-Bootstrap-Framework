## WALL-E : réveil physique démontré, accès SSH encore bloqué

Le lancement initial par systemd-suspend.service est refusé parce que sleep.target est masqué. Aucun sommeil réel n'a eu lieu à cet essai. Les masques sont conservés ; les essais suivants appellent directement systemd-sleep depuis une unité transitoire.

Le témoin sans paquet réseau entre réellement en S3/deep et revient après 122,45 s, à l'échéance RTC, sans redémarrage. Deux essais avec paquet magique reviennent respectivement 108,03 s et 98,04 s avant l'alarme : le réveil Wi-Fi physique fonctionne dans ces conditions. Le premier exige une reconnexion du profil Wi-Fi après trois pings négatifs ; le second récupère seul.

Un garde de reprise réseau a été installé : hook post-suspend non bloquant, service borné à 55 s, au plus une réactivation du profil existant si NAS et passerelle restent injoignables. Cinq scénarios simulés passent et le service fonctionne sur machine éveillée. **L'intégration après veille n'est pas qualifiée** : lors du troisième essai, ping et bannière SSH sont accessibles, mais le pont d'administration expire. Ses journaux locaux et l'état final caméra/API n'ont pas pu être relus. Le garde reste installé ; son critère ICMP ne détecte pas ce défaut sélectif du trafic.

Le diagnostic isole le marquage IP : depuis X399, trois connexions TCP SSH avec TOS 184 (DSCP EF) expirent ; les neuf connexions témoins TOS 0, 32 et 72 obtiennent la bannière SSH. Un client SSH avec IPQoS=none franchit la connexion et atteint la vérification de clé hôte ; la clé n'étant pas connue sur X399, cette vérification reste stricte et aucun accès nouveau n'est accordé. Le client X399 annonce IPQoS ef cs1. Le NAS hôte atteint également la bannière par socket ordinaire. La cause précise dans le pilote, le point d'accès ou la gestion WMM n'est pas démontrée.

**Blocage restant :** le pont wall_e_execute ne propose pas de réglage IPQoS, et le compte d'archivage NAS ne peut pas lire les clés de sa passerelle. Aucune permission ni clé hôte n'a été contournée. La [commande opérateur](operator-recover-nas.sh) utilise les clés existantes dans le conteneur avec IPQoS=none pour réactiver le profil Wi-Fi. Après cela, relire les preuves du troisième cycle, retirer ou corriger le garde insuffisant, puis refaire les contrôles SSH/API/PIXY. Une veille prolongée reste à qualifier.

L'archive N6000 a été copiée et ses 290 empreintes vérifiées sur X399 avant ces essais. Les plafonds CPU initiaux étaient restaurés et les collecteurs temporaires arrêtés avant la première veille. WALL-E répond au réseau au dernier diagnostic ; son état applicatif final n'est pas certifié. Aucun changement persistant vers s2idle n'a été appliqué.

Preuves : [observations de veille](wake-observations.json), [test différentiel DSCP](ssh-dscp-proof.json), [script de diagnostic](ssh-dscp-probe.py), [garde installé](wall-e-resume-network.py).


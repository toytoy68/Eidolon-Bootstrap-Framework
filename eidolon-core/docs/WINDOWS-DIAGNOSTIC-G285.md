# G285 — diagnostic de lancement Windows

Retour toytoy du 17/10/2026, 08 h 26 : erreur generique du lanceur G284. Le serveur Core et son port 8767 sont actifs ; le PC utilisateur n’est pas accessible depuis cette session. La cause racine reste inconnue.

Le script d’ouverture rapporte desormais l’etape en echec, un code dans une liste fixe, le type d’exception, le nom du fichier source et la ligne. Aucune exception brute, argument SSH, mot de passe, cle ou valeur DPAPI n’est journalise. Dernier diagnostic sous LOCALAPPDATA/Eidolon/last-launch-error.txt.

Diagnostiquer-Eidolon.cmd execute le meme parcours en laissant sa console ouverte. Il permet aussi de voir un blocage RemoteSigned qui intervient avant execution du script. Il ne change pas la politique Windows. Un blocage de fichier telecharge reste une hypothese : le guide propose de debloquer le ZIP via ses proprietes et de reextraire, seulement si Windows signale un script telecharge non signe.

Le paquet diagnostic reutilise les binaires G283 et les sources tunnel G284, inchanges. Les diagnostics ne constituent pas une correction confirmee de la cause inconnue. La CI verifie un echec synthetique avant toute connexion : client absent, code 2 et journal sans identifiant.

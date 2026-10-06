#!/usr/bin/env bash
# Exact server-side sequence of BETA-ACCEPTANCE.md, run with HOME pointing to a scratch folder.
set -u
cd "$REPO/eidolon-core"
echo '$ python3 --version'; python3 --version
echo '$ étape S2 : état et jeton'
BETA="$HOME/eidolon-beta"
mkdir -p "$BETA"
export PYTHONPATH=src
python3 -m eidolon_core --state "$BETA/state" demo > "$BETA/demo.json"; echo "demo: code $?"
python3 -c 'import os,secrets,sys; fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,(secrets.token_urlsafe(32)+"\n").encode()); os.close(fd)' "$BETA/read-token"; echo "token: code $?"
stat -c '%a %U' "$BETA/read-token" | sed "s/$(id -un)/<utilisateur>/"
echo '$ étape S3 : vérification sans démarrer'
python3 -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" --web-root desktop/connected --port 8765 --check --format human; echo "check: code $?"
node desktop/connected/build.js --check; echo "bundle: code $?"
echo '$ étape S4 : lancement'
python3 -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" --web-root desktop/connected --port 8765 > "$BETA/server.log" 2>&1 &
SERVER=$!
sleep 1.5
echo '$ étape S5 : contrôle sur le serveur'
python3 - "$BETA/read-token" <<'PY'
import json, sys, urllib.error, urllib.request
base = "http://127.0.0.1:8765"
print("page :", urllib.request.urlopen(base + "/").status)
token = open(sys.argv[1]).read().strip()
health = json.load(urllib.request.urlopen(urllib.request.Request(base + "/v1/health", headers={"Authorization": "Bearer " + token})))
print("health :", health["protocol"], health["mode"], "authorizes_execution =", health["authorizes_execution"])
try:
    urllib.request.urlopen(base + "/v1/health")
except urllib.error.HTTPError as exc:
    print("sans jeton :", exc.code)
PY
echo '$ écoute réseau (doit être 127.0.0.1 seulement)'
awk 'NR>1 && $4=="0A" {split($2,a,":"); if (a[2]=="223D") print "écoute :", a[1]=="0100007F" ? "127.0.0.1:8765" : a[1] ":8765 (NON LOOPBACK)"}' /proc/net/tcp
awk 'NR>1 && $4=="0A" {split($2,a,":"); if (a[2]=="223D") print "écoute IPv6 sur 8765 : présente (inattendu)"}' /proc/net/tcp6 2>/dev/null
echo '$ étape S6 : mission créée pendant la consultation'
python3 -m eidolon_core --state "$BETA/state" create "mission de recette synthétique" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("mission créée :", d["status"])'
echo '$ étape S8 : arrêt'
kill -INT "$SERVER"; sleep 1
kill -0 "$SERVER" 2>/dev/null && echo "kill -INT sur un serveur lancé en arrière-plan par un script : SANS EFFET (SIGINT ignoré)"
kill "$SERVER"; wait "$SERVER"; echo "kill (TERM) : serveur arrêté, code $?"
python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8765/", timeout=3)' 2>/dev/null && echo "après arrêt : répond encore" || echo "après arrêt : plus de réponse"
grep -c "" "$BETA/server.log" | sed 's/^/lignes du journal serveur : /'
grep -q "$(cat "$BETA/read-token")" "$BETA/server.log" && echo "JETON DANS LE JOURNAL" || echo "jeton absent du journal serveur"
echo '$ étape S9 : retrait'
rm -rf "$BETA"; test ! -e "$BETA" && echo "dossier de recette supprimé"

#!/usr/bin/env bash
# G046: eidolon-tunnel.ps1 at d9265fa, PowerShell 7 on LINUX, fake ssh. Not Windows.
# Usage (from eidolon-core/): PWSH=<pwsh> FROZEN=<frozen eidolon-core> SCRIPT=<ps1> bash run-g046.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'pkill -f "$WORK/" 2>/dev/null; rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin" "$WORK/appdata" "$WORK/home with space/eidolon-recette"
# A copy of python named "ssh": the process is then called "ssh", as ssh.exe is on Windows.
cp "$(command -v python3)" "$WORK/bin/ssh"
printf '#!/bin/sh\nexec "%s/bin/ssh" "%s/fake-ssh.py" "$@"\n' "$WORK" "$HERE" > "$WORK/bin/ssh.exe"
chmod +x "$WORK/bin/ssh.exe"
ln -s "$FROZEN" "$WORK/home with space/eidolon-recette/eidolon-core"
( cd "$FROZEN" && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m eidolon_core.beta_fixture --output "$WORK/home with space/eidolon-beta" >/dev/null )
export PATH="$WORK/bin:$PATH" LOCALAPPDATA="$WORK/appdata" FAKE_SSH_LOG="$WORK/ssh.log" FAKE_REMOTE_HOME="$WORK/home with space"
export PYTHONDONTWRITEBYTECODE=1
: > "$FAKE_SSH_LOG"
run() {  # $1 = argument mode (Standard|Legacy), then script arguments
  local mode="$1"; shift
  echo "\$ [$mode] eidolon-tunnel.ps1 $*"
  "$PWSH" -NoProfile -NonInteractive -File "$HERE/wrapper.ps1" "$mode" "$SCRIPT" "$@" > "$WORK/out.txt" 2>&1
  local code=$?
  grep -v '^$' "$WORK/out.txt" | grep -v '^#' | grep -v 'Eidolon Core Technologies\|Local AI' | sed "s#$WORK#<tmp>#g" | cut -c1-220
  echo "code: $code"; echo
}
last_remote() { tail -1 "$FAKE_SSH_LOG" | sed "s#$WORK#<tmp>#g" | cut -c1-400; }
P=18901
for mode in Standard Legacy; do
  echo "===== Mode $mode"
  for set in "eidolon-recette/eidolon-core|eidolon-beta/state|eidolon-beta/read-token" \
             "~/eidolon-recette/eidolon-core|~/eidolon-beta/state|~/eidolon-beta/read-token" \
             "$WORK/home with space/eidolon-recette/eidolon-core|$WORK/home with space/eidolon-beta/state|$WORK/home with space/eidolon-beta/read-token"; do
    IFS='|' read -r c s t <<< "$set"
    P=$((P+1))
    run "$mode" -Server serveur.local -User toytoy -Port $P -Connect -RemoteCore "$c" -RemoteState "$s" -RemoteTokenFile "$t"
    echo "argv du diagnostic reçu par ssh : $(grep -v '"-N"' "$FAKE_SSH_LOG" | tail -1 | sed "s#$WORK#<tmp>#g" | cut -c1-300)"
    "$PWSH" -NoProfile -NonInteractive -File "$SCRIPT" -Stop -Port $P > /dev/null 2>&1
    echo
  done
done
echo "===== Chemins refusés"
for bad in "~autre/x" "~root" "a b" "\$HOME/x" "a'b" "-x"; do
  run Standard -Server serveur.local -User toytoy -Port 18950 -RemoteCore "$bad" -RemoteState s -RemoteTokenFile t
done
echo "===== Arrêt : processus nommé ssh, comme sous Windows"
run Standard -Server serveur.local -User toytoy -Port 18960 -Connect
REC="$LOCALAPPDATA/Eidolon/beta-tunnel/tunnel-18960.json"
PID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['pid'])" "$REC")
echo "nom du processus : $(cat /proc/$PID/comm)"
run Standard -Server serveur.local -User toytoy -Port 18960 -Connect
run Standard -Stop -Port 18960
sleep 0.5
STATE=$(awk '/^State:/ {print $2}' "/proc/$PID/status" 2>/dev/null)
case "$STATE" in ""|Z) echo "tunnel arrêté (état : ${STATE:-disparu})";; *) echo "tunnel ENCORE vivant (état : $STATE)";; esac
echo "===== PID réutilisé : enregistrement qui pointe vers un autre processus ssh"
"$WORK/bin/ssh" -c "import time; time.sleep(300)" & OTHER=$!
mkdir -p "$(dirname "$REC")"
printf '{"pid": %s, "port": 18960, "server": "s", "user": "u", "started_ticks": 1}\n' "$OTHER" > "$REC"
run Standard -Stop -Port 18960
kill -0 "$OTHER" 2>/dev/null && echo "processus étranger intact" || echo "processus étranger TUÉ"
kill "$OTHER" 2>/dev/null

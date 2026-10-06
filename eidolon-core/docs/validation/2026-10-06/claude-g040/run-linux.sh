#!/usr/bin/env bash
# Runs eidolon-tunnel.ps1 with PowerShell 7 on LINUX and a fake ssh.exe. Not Windows.
# Usage (from eidolon-core/): PWSH=<pwsh> bash docs/validation/2026-10-06/claude-g040/run-linux.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$(pwd)/desktop/connected/launchers/eidolon-tunnel.ps1"
WORK="$(mktemp -d)"
trap 'pkill -f "$WORK/bin/ssh.exe" 2>/dev/null; rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin" "$WORK/appdata"
cp "$HERE/fake-ssh.py" "$WORK/bin/ssh.exe"; chmod +x "$WORK/bin/ssh.exe"
export PATH="$WORK/bin:$PATH" LOCALAPPDATA="$WORK/appdata" FAKE_SSH_LOG="$WORK/ssh.log"
: > "$FAKE_SSH_LOG"
# Output goes to a file, not a pipe: the simulated tunnel inherits it and would keep a pipe open.
run() {
  echo "\$ eidolon-tunnel.ps1 $*"
  "$PWSH" -NoProfile -NonInteractive -File "$SCRIPT" "$@" > "$WORK/out.txt" 2>&1; local code=$?
  grep -v '^$' "$WORK/out.txt" | grep -v '^#' | grep -v 'Eidolon Core Technologies\|Local AI'
  echo "code: $code"; echo
}
echo "== P0 analyse syntaxique"
"$PWSH" -NoProfile -NonInteractive -Command "\$e=\$null; [void][System.Management.Automation.Language.Parser]::ParseFile('$SCRIPT',[ref]\$null,[ref]\$e); 'erreurs de syntaxe : ' + \$e.Count"
echo
echo "== P1 entrées refusées avant ssh"
run -Server '-oProxyCommand=calc' -User toytoy -Port 18765
run -Server 'serveur.local' -User 'a b' -Port 18765
run -Server 'serveur.local' -User toytoy -Port 80
run -Server 'serveur.local' -User toytoy -Port 18765 -RemoteCore 'x'
run -Server 'serveur.local' -User toytoy -Port 18765 -RemoteCore 'a;rm' -RemoteState s -RemoteTokenFile t
echo "appels ssh après P1 : $(wc -l < "$FAKE_SSH_LOG")"
echo
echo "== P2 aperçu par défaut"
run -Server 'serveur.local' -User toytoy -Port 18765 -RemoteCore '~/eidolon-recette/eidolon-core' -RemoteState '~/eidolon-beta/state' -RemoteTokenFile '~/eidolon-beta/read-token'
echo "appels ssh après P2 : $(wc -l < "$FAKE_SSH_LOG")"
echo
echo "== P3 port local occupé"
python3 -c 'import socket,time; s=socket.socket(); s.bind(("127.0.0.1",18766)); s.listen(); time.sleep(20)' & BUSY=$!
sleep 0.5
run -Server 'serveur.local' -User toytoy -Port 18766 -Connect
kill $BUSY
echo "== P4 diagnostic distant en échec : pas de tunnel"
FAKE_CHECK_CODE=2 run -Server 'serveur.local' -User toytoy -Port 18767 -Connect -RemoteCore 'c' -RemoteState 's' -RemoteTokenFile 't'
echo "dernier appel ssh : $(tail -1 "$FAKE_SSH_LOG")"
echo
echo "== P5 connexion avec diagnostic réussi"
run -Server 'serveur.local' -User toytoy -Port 18768 -Connect -RemoteCore 'c' -RemoteState 's' -RemoteTokenFile 't'
tail -2 "$FAKE_SSH_LOG"
ls "$LOCALAPPDATA/Eidolon/beta-tunnel"
echo
echo "== P6 relance : tunnel déjà actif détecté"
run -Server 'serveur.local' -User toytoy -Port 18768 -Connect
echo "== P7 arrêt : sous Linux le processus s'appelle ssh.exe (pas ssh) : refus attendu de l'arrêter"
run -Stop -Port 18768
pgrep -f "$WORK/bin/ssh.exe" >/dev/null && echo "tunnel simulé toujours vivant (non tué par le script)" || echo "tunnel simulé arrêté"

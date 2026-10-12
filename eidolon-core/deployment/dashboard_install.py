# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : dashboard_install.py
# Description : Prévol (lecture seule) et installation préparée du dashboard sur la VM Core : unités, ports, origine (G159)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""VM Core only, run by the operator (Codex/toytoy), never by Claude. Standard library only.

  python3 dashboard_install.py preflight [--probe]           read-only checks; exit 1 on any failure
  python3 dashboard_install.py install --source DIR          prints the plan, changes NOTHING
  sudo python3 dashboard_install.py install --source DIR --apply

install --apply: backs up every target that exists (tar.gz 0600 in /var/backups/eidolon), copies the
eidolon-comm and eidolon-monitor units, ADDS only --comm-port/--monitor-port to the ACTIVE eidolon-core-api
unit (refused on a conflicting value; the repository copy never replaces it), creates monitor.json from the example ONLY if absent
(0600, owner = the Core account). It never overwrites a configuration, never copies a key, never calls
systemctl: the operator runs the printed commands. Rollback = restore the archive, daemon-reload, restart.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat
import sys
import tarfile

UNITS = ("eidolon-comm.service", "eidolon-monitor.service", "eidolon-core-api.service")
OWNER = "toytoy"
PATHS = {
    "units": "etc/systemd/system",
    "comm_config": "home/toytoy/eidolon-comm/comm.json",
    "monitor_config": "home/toytoy/eidolon-monitor/monitor.json",
    "backup": "var/backups/eidolon",
}


def _exec(unit_text):
    lines = [line for line in unit_text.splitlines() if line.startswith("ExecStart=")]
    return lines[0] if len(lines) == 1 else ""


def _flag(line, name):
    match = re.search(r"(?:^|\s)" + re.escape(name) + r"\s+(\S+)", line)
    return match.group(1) if match else None


def _private(path, uid):
    info = os.lstat(path)
    return stat.S_ISREG(info.st_mode) and info.st_uid == uid and not info.st_mode & 0o077


def preflight(root="/", *, probe=False, owner=OWNER):
    """[{check, ok, detail}] — reads files only; with probe, also connects to the loopback ports and sockets."""
    root = Path(root)
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:200]})

    try:
        uid = pwd.getpwnam(owner).pw_uid
    except KeyError:
        uid = os.getuid() if root != Path("/") else -1
    texts = {}
    for unit in UNITS:
        path = root / PATHS["units"] / unit
        texts[unit] = path.read_text() if path.is_file() and not path.is_symlink() else None
        check(f"unité {unit} présente (fichier, pas un lien)", texts[unit] is not None, path)
    if None in texts.values():
        return checks
    core, comm, monitor = (_exec(texts[u]) for u in ("eidolon-core-api.service", "eidolon-comm.service",
                                                      "eidolon-monitor.service"))
    ports = {"core": _flag(core, "--port"), "comm": _flag(comm, "--port"), "monitor": _flag(monitor, "--port"),
             "core→comm": _flag(core, "--comm-port"), "core→monitor": _flag(core, "--monitor-port")}
    check("ports déclarés", all(p and p.isdigit() for p in ports.values()), ports)
    check("Core relaie vers le bon port voix", ports["core→comm"] == ports["comm"], ports)
    check("Core relaie vers le bon port surveillance", ports["core→monitor"] == ports["monitor"], ports)
    check("trois ports distincts", len({ports["core"], ports["comm"], ports["monitor"]}) == 3, ports)
    states = {_flag(line, "--state") for line in (core, comm, monitor)}
    check("même état Core pour les trois services (clés appairées)", len(states) == 1 and None not in states, states)
    check("surveillance : groupe eidolon-darme pour ce processus seulement",
          "SupplementaryGroups=eidolon-darme" in texts["eidolon-monitor.service"], "")
    for unit in ("eidolon-comm.service", "eidolon-monitor.service"):
        check(f"{unit} : boucle locale seulement",
              "IPAddressDeny=any" in texts[unit] and "IPAddressAllow=localhost" in texts[unit], "")
    origin = f"http://127.0.0.1:{ports['core']}"
    for name, schema in (("monitor_config", "eidolon-monitor-config/1"), ("comm_config", "eidolon-comm-config/1")):
        path = root / PATHS[name]
        if not path.exists():
            check(f"{path.name} présent", False, "absent" + (" : moteurs voix non installés (COMMUNICATION.md §4)"
                                                           if name == "comm_config" else ""))
            continue
        check(f"{path.name} privé (0600, propriétaire {owner}, pas un lien)", _private(path, uid), oct(os.lstat(path).st_mode))
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            check(f"{path.name} lisible", False, "JSON invalide")
            continue
        check(f"{path.name} schéma", value.get("schema") == schema, value.get("schema"))
        declared = value.get("allowed_origin")
        check(f"{path.name} origine = page Core ({origin}) ou absente", declared in (None, origin), declared)
        if name == "monitor_config":
            sockets = [m.get("socket") for m in value.get("machines", []) if isinstance(m, dict)]
            for sock in sockets:
                target = root / str(sock).lstrip("/")
                present = target.exists() and stat.S_ISSOCK(os.lstat(target).st_mode)
                check(f"socket DARME {sock}", present, "absent : eidolon-darme.service actif ?" if not present else "")
                if present and probe:
                    try:
                        with socket.socket(socket.AF_UNIX) as s:
                            s.settimeout(3); s.connect(str(target)); s.sendall(b"STATUS\n")
                            reply = s.recv(65536)
                        check(f"socket DARME {sock} répond (STATUS)", reply.startswith(b"{"), "")
                    except OSError as exc:
                        check(f"socket DARME {sock} répond (STATUS)", False, type(exc).__name__)
    if probe:
        for name in ("core", "comm", "monitor"):
            with socket.socket() as s:
                s.settimeout(2)
                check(f"port {name} {ports[name]} ouvert sur 127.0.0.1", s.connect_ex(("127.0.0.1", int(ports[name]))) == 0)
    return checks


RELAY_FLAGS = (("--comm-port", "8766"), ("--monitor-port", "8768"))


def complete_core(text):
    """The ACTIVE Core unit with only the two relay flags added to ExecStart (everything else kept as is)."""
    line = _exec(text)
    if not line:
        raise ValueError("CORE_UNIT_EXECSTART_UNREADABLE")
    added = line
    for flag, value in RELAY_FLAGS:
        current = _flag(line, flag)
        if current is None:
            added += f" {flag} {value}"
        elif current != value:
            raise ValueError(f"CORE_UNIT_CONFLICT: {flag} {current}")
    return text.replace(line, added, 1)


def plan(source, root="/"):
    """[(action, source path or new bytes, target path)] — nothing is written here.

    The active Core unit is never replaced by the repository copy: only the relay flags are added to it."""
    source, root = Path(source), Path(root)
    actions = []
    for unit in UNITS:
        target = root / PATHS["units"] / unit
        if target.is_symlink():
            raise ValueError(f"REFUSED_SYMLINK: {target}")
        if unit == "eidolon-core-api.service" and target.exists():
            current = target.read_text()
            wanted = complete_core(current)
            actions.append(("identique", None, target) if wanted == current
                           else ("compléter", wanted.encode(), target))
        elif target.exists() and target.read_bytes() == (source / unit).read_bytes():
            actions.append(("identique", source / unit, target))
        else:
            actions.append(("remplacer" if target.exists() else "créer", source / unit, target))
    config = root / PATHS["monitor_config"]
    if config.is_symlink():
        raise ValueError(f"REFUSED_SYMLINK: {config}")
    actions.append(("conserver" if config.exists() else "créer 0600", source / "monitor.json.example", config))
    return actions


def install(source, root="/", *, apply=False, owner=OWNER, now=None):
    actions = plan(source, root)
    writes = [a for a in actions if a[0] in ("créer", "remplacer", "compléter", "créer 0600")]
    if not apply or not writes:
        return actions, None
    root = Path(root)
    backup_dir = root / PATHS["backup"]
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y%m%d-%H%M%S-%f")
    archive = backup_dir / f"dashboard-preinstall-{stamp}.tar.gz"
    with tarfile.open(archive, "x:gz") as tar:
        for _, _, target in actions:
            if target.exists():
                tar.add(target, arcname=str(target.relative_to(root)))
    os.chmod(archive, 0o600)
    try:
        account = pwd.getpwnam(owner)
    except KeyError:
        account = None
    for action, src, target in writes:
        if action == "créer 0600":
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(src.read_bytes())
            if os.getuid() == 0 and account is not None:
                os.chown(target.parent, account.pw_uid, account.pw_gid)
                os.chown(target, account.pw_uid, account.pw_gid)
        else:
            temporary = target.with_name("." + target.name + ".new")
            if isinstance(src, bytes):
                temporary.write_bytes(src)
            else:
                shutil.copyfile(src, temporary)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
    return actions, archive


NEXT = """Étapes suivantes (opérateur) :
  systemd-analyze verify /etc/systemd/system/eidolon-monitor.service /etc/systemd/system/eidolon-comm.service
  systemctl daemon-reload
  systemctl enable --now eidolon-monitor.service      # eidolon-comm : seulement après COMMUNICATION.md §4
  systemctl restart eidolon-core-api.service
  python3 dashboard_install.py preflight --probe
Retour arrière : tar -xzf {archive} -C / ; systemctl daemon-reload ; systemctl disable --now eidolon-monitor ;
  systemctl restart eidolon-core-api"""


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dashboard_install.py", description="Dashboard Eidolon — prévol et installation VM Core")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight", help="contrôles en lecture seule")
    pre.add_argument("--probe", action="store_true", help="tester aussi les ports locaux et les sockets DARME")
    pre.add_argument("--root", default="/", help=argparse.SUPPRESS)
    ins = sub.add_parser("install", help="plan (par défaut) ou installation (--apply)")
    ins.add_argument("--source", required=True, help="dossier deployment/vm-profile du commit à installer")
    ins.add_argument("--apply", action="store_true")
    ins.add_argument("--root", default="/", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command == "preflight":
        checks = preflight(args.root, probe=args.probe)
        print(json.dumps({"passed": sum(c["ok"] for c in checks), "total": len(checks), "checks": checks},
                         ensure_ascii=False, indent=1))
        return 0 if all(c["ok"] for c in checks) else 1
    try:
        actions, archive = install(args.source, args.root, apply=args.apply)
    except (OSError, ValueError) as exc:
        print(f"REFUSÉ : {str(exc).split(':')[0]}", file=sys.stderr)
        return 2
    for action, _, target in actions:
        print(f"{action:12} {target}")
    if not args.apply:
        print("Simulation : rien n'a été modifié. Ajouter --apply (root) pour installer.")
    elif archive is None:
        print("Rien à changer.")
    else:
        print(f"Sauvegarde : {archive}")
        print(NEXT.format(archive=archive))
    return 0


if __name__ == "__main__":
    sys.exit(main())

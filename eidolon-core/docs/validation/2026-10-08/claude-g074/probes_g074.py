# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g074.py
# Description : Contre-revue de model-config-check et des identités des deux adaptateurs (C-TASK-G074)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g074.py <frozen eidolon-core/src>      (exit 1 if an expectation fails)

CLI cases run in a subprocess under a Python audit hook (socket connect/bind, sqlite3.connect,
open for writing, mkdir) and with os.environ replaced by a spy that records any read of the
credential variable. Nothing is contacted: no server listens on the configured ports."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True

from eidolon_core.model_config import ModelConfigError, _decode  # noqa: E402
from eidolon_core.ollama_model import OllamaConfig, OllamaModel  # noqa: E402
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatModel  # noqa: E402

FAILED, NOTES = [], []
OLLAMA = {"version": 1, "provider": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "synthetic-g074:1b",
          "options": {"num_predict": 256}}
LLAMA = {"version": 1, "provider": "llama-server", "endpoint": "http://127.0.0.1:8080", "model": "synthetic-g074",
         "options": {"max_tokens": 256}, "api_key_env": "G074_KEY"}

GUARDED = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
events = []
class Spy(dict):
    def __getitem__(self, k):
        if k == "G074_KEY": events.append("lecture de la clé")
        return dict.__getitem__(self, k)
    def get(self, k, d=None):
        if k == "G074_KEY": events.append("lecture de la clé")
        return dict.get(self, k, d)
os.environ = Spy(os.environ)
def hook(event, args):
    if event in ("socket.connect", "socket.bind", "sqlite3.connect", "os.mkdir"):
        events.append(event)
    elif event == "open" and len(args) > 1 and isinstance(args[1], str) and any(c in args[1] for c in "wax+"):
        events.append("open-write")
    elif event == "open" and len(args) > 2 and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
        events.append("open-write")
sys.addaudithook(hook)
from eidolon_core.cli import main
code = main(sys.argv[2:])
sys.stdout.flush()
print("\n@@AUDIT@@" + json.dumps(events), file=sys.stderr)
sys.exit(code)
"""


def check(label, ok, detail=""):
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}", flush=True)
    if not ok:
        FAILED.append(label)


def note(label, detail):
    print(f"ℹ {label} — {detail}", flush=True)
    NOTES.append(label)


def cli(path, state):
    env = {**{k: v for k, v in os.environ.items() if k != "PYTHONPATH"}, "PYTHONDONTWRITEBYTECODE": "1",
           "G074_KEY": "sk-g074-valeur-synthetique"}
    p = subprocess.run([sys.executable, "-c", GUARDED, SRC, "--state", str(state), "model-config-check", "--config",
                        str(path)], capture_output=True, text=True, timeout=30, env=env)
    err, _, audit = p.stderr.partition("\n@@AUDIT@@")
    return p.returncode, p.stdout, err, json.loads(audit) if audit else ["?"]


def write(tmp, name, value, mode=0o600):
    path = Path(tmp) / f"{name}.json"
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode())
    path.chmod(mode)
    return path


def expect(tmp, name, value, valid, *, mode=0o600, path=None):
    path = path or write(tmp, name.replace(" ", "-").replace("/", "_")[:40], value, mode)
    state = Path(tmp) / "state-jamais-cree"
    code, out, err, audit = cli(path, state)
    result = json.loads(out) if out.strip() else None
    got = "VALID_CONFIG" if result else (json.loads(err.strip().splitlines()[-1]).get("message") if err.strip() else "?")
    problems = []
    if (code == 0) != valid:
        problems.append("attendu " + ("valide" if valid else "refus"))
    if audit:
        problems.append(f"audit {audit}")
    if state.exists():
        problems.append("--state créé")
    if "sk-g074" in out + err or str(path) in err:
        problems.append("fuite clé/chemin")
    if result and (result["server_contacted"] or result["secret_value_read"] or result["authorizes_execution"]):
        problems.append("drapeau vrai")
    check(f"{name} → {got}", not problems, "; ".join(problems))
    return result


def variant(base, change):
    value = copy.deepcopy(base)
    change(value)
    return value


def model_id(value):
    try:
        return _decode(json.dumps(value).encode()).model_id
    except ModelConfigError as exc:
        return str(exc)


def main():
    print(f"Sources examinées : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g074-") as tmp:
        tmp = Path(tmp)
        print("== adresses")
        for name, endpoint, valid in (("IPv4 loopback", "http://127.0.0.1:11434", True),
                                      ("IPv6 loopback", "http://[::1]:11434", True),
                                      ("https loopback", "https://127.0.0.1:11434", True),
                                      ("sans port", "http://127.0.0.1", True),
                                      ("localhost (DNS)", "http://localhost:11434", False),
                                      ("127.0.0.2", "http://127.0.0.2:11434", False),
                                      ("127.1 abrégé", "http://127.1:11434", False),
                                      ("0x7f.0.0.1", "http://0x7f.0.0.1:11434", False),
                                      ("IPv4 mappée ::ffff:127.0.0.1", "http://[::ffff:127.0.0.1]:11434", False),
                                      ("point final 127.0.0.1.", "http://127.0.0.1.:11434", False),
                                      ("chiffres pleine chasse", "http://１２７.0.0.1:11434", False),
                                      ("port 0", "http://127.0.0.1:0", False),
                                      ("port 65536", "http://127.0.0.1:65536", False),
                                      ("chemin /api", "http://127.0.0.1:11434/api", False),
                                      ("barre finale", "http://127.0.0.1:11434/", True),
                                      ("requête ?x", "http://127.0.0.1:11434?x=1", False),
                                      ("identifiant user@", "http://user@127.0.0.1:11434", False),
                                      ("schéma ftp", "ftp://127.0.0.1:11434", False),
                                      ("espace insécable", "http://127.0.0.1:11434 ", False),
                                      ("espace de largeur nulle", "http://127.0.0.1:11434​", False),
                                      ("DEL", "http://127.0.0.1:11434\x7f", False)):
            expect(tmp, f"Ollama {name}", variant(OLLAMA, lambda v: v.update(endpoint=endpoint)), valid)

        print("== types, clés et fournisseurs")
        for name, change, valid in (
                ("clé inconnue", lambda v: v.update(extra=1), False),
                ("version true", lambda v: v.update(version=True), False),
                ("num_predict true", lambda v: v["options"].update(num_predict=True), False),
                ("num_predict 8193", lambda v: v["options"].update(num_predict=8193), False),
                ("timeout_seconds true", lambda v: v.update(timeout_seconds=True), False),
                ("timeout_seconds 0", lambda v: v.update(timeout_seconds=0), False),
                ("max_prompt_bytes 1.0", lambda v: v.update(max_prompt_bytes=1.0), False),
                ("option max_tokens (autre fournisseur)", lambda v: v["options"].update(max_tokens=10), False),
                ("api_key_env sur Ollama", lambda v: v.update(api_key_env="G074_KEY"), False),
                ("allow_non_loopback", lambda v: v.update(allow_non_loopback=True), False),
                ("temperature NaN (texte)", lambda v: v["options"].update(temperature="NaN"), False),
                ("modèle avec espace de largeur nulle", lambda v: v.update(model="synthetic​g074:1b"), None),
                ("modèle avec inversion bidi U+202E", lambda v: v.update(model="synthetic‮b1:470g"), None)):
            value = variant(OLLAMA, change)
            if valid is None:
                result = expect(tmp, f"Ollama {name}", value, True)
                if result:
                    note(f"Ollama {name} accepté", f"identité {result['model_id'][:44]!r} : caractère invisible "
                         "conservé dans le nom envoyé au serveur et dans l'identité")
                continue
            expect(tmp, f"Ollama {name}", value, valid)
        for name, change, valid in (("nominal avec api_key_env", lambda v: None, True),
                                    ("option num_predict (autre fournisseur)", lambda v: v["options"].update(num_predict=1), False),
                                    ("api_key_env en minuscules", lambda v: v.update(api_key_env="g074_key"), False),
                                    ("api_key_env = HOME (nom valide quelconque)", lambda v: v.update(api_key_env="HOME"), True),
                                    ("context_tokens true", lambda v: v.update(context_tokens=True), False),
                                    ("clé en ligne (champ api_key)", lambda v: v.update(api_key="sk-inline"), False)):
            expect(tmp, f"llama-server {name}", variant(LLAMA, change), valid)
        note("api_key_env accepte tout nom de variable (HOME, AWS_…)", "la valeur sera envoyée en Bearer au point "
             "configuré à l'exécution ; loopback seulement : choix de l'opérateur, à documenter")

        print("== fichiers")
        expect(tmp, "permissions 0644", OLLAMA, False, mode=0o644)
        expect(tmp, "permissions 0640", OLLAMA, False, mode=0o640)
        target = write(tmp, "target", OLLAMA)
        link = tmp / "link.json"
        os.symlink(target, link)
        expect(tmp, "lien symbolique final", None, False, path=link)
        fifo = tmp / "fifo.json"
        os.mkfifo(fifo, 0o600)
        expect(tmp, "FIFO (sans blocage)", None, False, path=fifo)
        expect(tmp, "17 Kio", b'{"pad":"' + b"x" * 17000 + b'"}', False)
        expect(tmp, "clé dupliquée", json.dumps(OLLAMA).replace('"model"', '"model":"x","model"', 1).encode(), False)
        from eidolon_core import model_config as mc
        path = write(tmp, "race", OLLAMA)
        real = os.fdopen

        def swap(fd, *a, **k):
            stream = real(fd, *a, **k)
            path.write_bytes(path.read_bytes().replace(b"256", b"512"))
            return stream
        mc.os.fdopen = swap
        try:
            try:
                mc.load_model(str(path))
                outcome = "ACCEPTÉ"
            except ModelConfigError as exc:
                outcome = str(exc)
        finally:
            mc.os.fdopen = real
        check("réécriture de même taille pendant la lecture → refus", outcome == "MODEL_CONFIG_CHANGED_OR_TOO_LARGE", outcome)

        print("== identités")
        base_o, base_l = model_id(OLLAMA), model_id(LLAMA)
        for name, base, changed in (
                ("Ollama num_predict", base_o, variant(OLLAMA, lambda v: v["options"].update(num_predict=257))),
                ("Ollama temperature", base_o, variant(OLLAMA, lambda v: v["options"].update(temperature=0.5))),
                ("Ollama timeout", base_o, variant(OLLAMA, lambda v: v.update(timeout_seconds=61))),
                ("Ollama max_output_bytes", base_o, variant(OLLAMA, lambda v: v.update(max_output_bytes=1000))),
                ("Ollama port", base_o, variant(OLLAMA, lambda v: v.update(endpoint="http://127.0.0.1:11435"))),
                ("llama-server max_tokens", base_l, variant(LLAMA, lambda v: v["options"].update(max_tokens=257))),
                ("llama-server context_tokens", base_l, variant(LLAMA, lambda v: v.update(context_tokens=4096))),
                ("llama-server nom de variable de clé", base_l, variant(LLAMA, lambda v: v.update(api_key_env="G074_OTHER")))):
            check(f"changer {name} change l'identité", model_id(changed) != base)
        os.environ["G074_KEY"] = "valeur-1"
        first = model_id(LLAMA)
        os.environ["G074_KEY"] = "valeur-2"
        check("changer la VALEUR de la clé sans renommer la variable garde l'identité (limite documentée)",
              model_id(LLAMA) == first)
        same = [model_id(variant(OLLAMA, lambda v: v.update(endpoint=e)))
                for e in ("http://127.0.0.1:11434", "http://127.0.0.1:11434/")]
        check("barre finale normalisée : même identité", same[0] == same[1])
        zero = model_id(variant(OLLAMA, lambda v: v.update(endpoint="http://127.0.0.1:011434")))
        if zero != base_o:
            note("port écrit 011434 au lieu de 11434", "même destination, identité différente (texte brut dans le manifeste)")

        print("== API Python et politique CLI (différences, pas forcément des défauts)")
        for name, build in (
                ("Ollama localhost", lambda: OllamaModel(OllamaConfig(endpoint="http://localhost:11434", model="m"))),
                ("Ollama sans num_predict", lambda: OllamaModel(OllamaConfig(endpoint="http://127.0.0.1:11434", model="m"))),
                ("Ollama hors loopback avec allow_non_loopback", lambda: OllamaModel(OllamaConfig(
                    endpoint="http://192.0.2.10:11434", model="m", allow_non_loopback=True))),
                ("OpenAI endpoint avec DEL", lambda: OpenAIChatModel(OpenAIChatConfig(endpoint="http://127.0.0.1:8080\x7f",
                                                                                     model="m")))):
            try:
                build()
                note(f"API : {name}", "accepté par l'adaptateur, refusé par la CLI")
            except Exception as exc:  # noqa: BLE001
                print(f"   API : {name} → refusé ({type(exc).__name__})")
    print(f"Remarques : {len(NOTES)}")
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

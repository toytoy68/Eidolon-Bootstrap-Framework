# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g050.py
# Description : Contre-revue du nettoyage local des requêtes C-013 sur cible figée (C-TASK-G050)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""cd <frozen copy>/eidolon-core && PYTHONPATH=src python3 <this file> <repo>/eidolon-core

Synthetic values only (example.invalid, documentation IP ranges, fictitious numbers).
Fake providers, reader, resolver; no network. A temporary folder holds the optional guard."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from eidolon_core.contracts import ContractError, digest, encode
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator
try:
    from eidolon_core.research_guard import ResearchGuard
except ImportError:          # 5194221 predates the guard (C-014a): parts C-E are skipped there
    ResearchGuard = None

REPO = Path(sys.argv[1])


def show(text):
    try:
        c = clean_query(text)
        return c.text, dict(c.removed)
    except ContractError as exc:
        return "ERREUR " + str(exc), {}


# (label, query, fragment that must NOT remain, or None when the case documents a false positive)
CASES = [
    # --- IP addresses (C-D15/16: IP must be removed)
    ("IP1 fin de phrase « 198.51.100.7. »", "serveur 198.51.100.7.", "198.51.100.7"),
    ("IP2 après deux-points « ip:198.51.100.7 »", "ip:198.51.100.7 refuse", "198.51.100.7"),
    ("IP3 avec port « 198.51.100.7:25565 »", "minecraft 198.51.100.7:25565 lent", "25565"),
    ("IP4 zéros en tête « 198.051.100.007 »", "routeur 198.051.100.007", "051.100"),
    ("IP5 entre parenthèses", "passerelle (198.51.100.1)", "198.51.100.1"),
    ("IP6 IPv6 entre crochets avec port", "joindre [2001:db8::7]:8080", "2001:db8"),
    ("IP7 IPv4 CIDR", "réseau 198.51.100.0/24", "198.51.100.0"),
    ("IP8 IPv4 chiffres pleine chasse", "hôte １９８.５１.１００.７", "198.51.100.7"),
    ("IP9 IPv4 suivie d'une virgule", "hôtes 198.51.100.7, 198.51.100.8", "198.51.100"),
    # --- IBAN
    ("IB1 IBAN minuscules", "virer sur fr76 3000 6000 0112 3456 7890 189", "3000 6000"),
    ("IB2 IBAN avec tirets", "iban FR76-3000-6000-0112-3456-7890-189", "3000-6000"),
    ("IB3 IBAN collé", "iban FR7630006000011234567890189", "30006000"),
    ("IB4 IBAN préfixé « IBAN: »", "IBAN:FR7630006000011234567890189", "30006000"),
    # --- phone
    ("T1 « 0033 6 12 34 56 78 »", "appeler 0033 6 12 34 56 78", "12 34 56 78"),
    ("T2 « +33 (0)6 12 34 56 78 »", "appeler +33 (0)6 12 34 56 78", "12 34 56 78"),
    ("T3 « tel:0612345678 »", "tel:0612345678 svp", "0612345678"),
    ("T4 « 06.12.34.56.78. » fin de phrase", "rappeler le 06.12.34.56.78.", "34.56.78"),
    ("T5 chiffres pleine chasse", "appeler ０６ １２ ３４ ５６ ７８", "12 34 56 78"),
    ("T6 « 06 12 34 56 78 » avec marques combinantes", "appeler 0\u03326 12 34 56 78", "34 56 78"),
    # --- email
    ("E1 « ＠ » pleine chasse", "écrire à jean＠example.invalid", "example.invalid"),
    ("E2 espace autour de @", "écrire à jean @ example.invalid", "example.invalid"),
    ("E3 invisible U+200B dans l'adresse", "écrire à jean\u200b@example.invalid", "example.invalid"),
    ("E4 « jean(at)example.invalid »", "écrire jean(at)example.invalid", "example.invalid"),
    # --- URL and paths
    ("U1 domaine + chemin sans schéma, jeton", "ouvrir www.example.invalid/reset?token=AbC123secret", "AbC123secret"),
    ("U2 domaine nu sans www, jeton", "ouvrir example.invalid/reset?token=AbC123secret", "AbC123secret"),
    ("U3 schéma en majuscules", "HTTPS://example.invalid/x?token=AbC123secret", "AbC123secret"),
    ("U4 URL entre chevrons", "voir <https://example.invalid/x?token=AbC123secret>", "AbC123secret"),
    ("U5 schéma ssh://", "ssh://admin@198.51.100.7:2222", "admin"),
    ("U6 schéma smb:// et sftp://", "smb://nas.local/partage/compta sftp://srv/backup", "compta"),
    ("P1 chemin /opt", "lire /opt/eidolon/secrets/token.txt", "token.txt"),
    ("P2 chemin /srv", "voir /srv/nas/compta/2026.xlsx", "compta"),
    ("P3 chemin relatif ./", "ouvrir ./secrets/token.txt", "token.txt"),
    ("P4 chemin Windows avec espaces, non cité", r"ouvrir C:\Users\Jean Dupont\Documents\impots.pdf", "impots"),
    ("P5 chemin Windows avec « / »", "ouvrir C:/Users/jean/impots.pdf", "impots"),
    ("P6 %USERPROFILE%", r"ouvrir %USERPROFILE%\Documents\impots.pdf", "impots"),
    ("P7 guillemets simples", "ouvrir '/home/jean/mes impots.pdf'", "impots"),
    # --- false positives (kept for information; no fragment must disappear)
    ("F1 version logicielle 1.2.3.4", "changelog version 1.2.3.4", None),
    ("F2 référence produit 10 chiffres", "pièce 0612345678 Bosch", None),
    ("F3 heure « 12:30 »", "rendez-vous 12:30", None),
    ("F4 identifiant hexadécimal « dead:beef::1 »", "hash dead:beef::1", None),
    ("F5 norme ISO « DE44 5001 0517 5407 3249 31 » (forme IBAN)", "exemple DE44 5001 0517 5407 3249 31", None),
    ("F6 « node.js/express » (forme domaine + chemin)", "tutoriel node.js/express", None),
    ("F7 « README.md#install »", "section README.md#install", None),
    ("F8 texte « fr12 pour cela vous » (forme IBAN minuscule)", "code fr12 pour cela vous aide", None),
    ("F9 « ./configure »", "lancer ./configure puis make", None),
    ("F10 ratio « 3.5/10 » et date « 07.10.2026 »", "note 3.5/10 le 07.10.2026", None),
    ("F11 numéro de série « 1234 5678 9012 »", "série 1234 5678 9012", None),
]


class Provider:
    def __init__(self, identity, behaviour):
        self.provider_id, self.behaviour, self.queries = identity, behaviour, []

    def search(self, query, limit):
        self.queries.append(query)
        if self.behaviour == "error":
            raise RuntimeError("provider down")
        if self.behaviour == "rate":
            raise AccessFailure("RATE_LIMITED", retry_after=30)
        if self.behaviour == "empty":
            return []
        return [Hit("https://docs.example.com/a", "titre")]


class Reader:
    reader_id = "g050-reader/1"

    def __init__(self):
        self.calls = 0

    def read(self, url, policy):
        self.calls += 1
        raise AccessFailure("UNAVAILABLE")


class Resolver:
    def __init__(self):
        self.calls = 0

    def __call__(self, host, port):
        self.calls += 1
        return ["93.184.216.34"]


def coordinator(behaviours, guard=None):
    providers = [Provider(f"p{i}", b) for i, b in enumerate(behaviours)]
    reader, resolver = Reader(), Resolver()
    c = ResearchCoordinator(providers, reader, resolver=resolver, guard=guard)
    return c, providers, reader, resolver


def main():
    print("== A. corpus G029 rejoué, comparé aux sorties Codex")
    corpus = json.loads((REPO / "docs/proposals/2026-10-06-query-disclosure/corpus.json").read_text())["queries"]
    codex = {c["id"]: c for c in json.loads((REPO / "docs/validation/2026-10-07/codex-query-cleanup/synthetic-corpus.json").read_text())}
    same = 0
    for q in corpus:
        c = clean_query(q["query"])
        ok = c.text == codex[q["id"]]["cleaned"] and c.receipt() == codex[q["id"]]["receipt"]
        same += ok
        if not ok:
            print(f"A {q['id']} DIFFÉRENT : {c.text!r}")
    print(f"A {same}/{len(corpus)} identiques (texte nettoyé et reçu)")

    print("== B. cas ajoutés : ce qui reste")
    gaps = 0
    for label, query, must_go in CASES:
        text, removed = show(query)
        if must_go is None:
            verdict = "faux positif" if removed else "gardé"
        else:
            verdict = "retiré" if must_go not in text else "RESTE  <-- ÉCART"
            gaps += must_go in text
        print(f"B {label}: {verdict} → {text!r} {removed}")
    print(f"B écarts : {gaps}/{sum(1 for c in CASES if c[2])}")

    if ResearchGuard is None:
        print("== C-E non exécutés : coordinateur sans garde sur cette cible")
        return
    print("== C. tous les fournisseurs et replis reçoivent le texte nettoyé")
    secret = "jean@example.invalid 06 12 34 56 78 198.51.100.7 FR7630006000011234567890189"
    query = "documentation pont " + secret
    for behaviours in (["error", "rate", "hits"], ["empty", "error", "hits"]):   # 3 providers: default budget
        c, providers, reader, resolver = coordinator(behaviours)
        report = c.run(query)
        for p in providers:
            print(f"C {p.provider_id} ({p.behaviour}) a reçu : {p.queries}")
        blob = encode(report)
        values = ["jean@example.invalid", "06 12 34 56 78", "0612345678", "198.51.100.7", "FR7630006000011234567890189"]
        print(f"C rapport : statut={report['status']} ; lecteur={reader.calls} ; valeurs retirées présentes dans le rapport : "
              f"{[v for v in values if v in blob]}")
    raw_hash = digest(query)
    print(f"C rapport.query_sha256 = empreinte de la requête BRUTE : {report['query_sha256'] == raw_hash} ; "
          f"query_cleanup.original_sha256 = SHA-256 brut : {report['query_cleanup']['original_sha256'] == hashlib.sha256(query.encode()).hexdigest()}")
    # Dictionary check: a phone-only query is recoverable from its report hash in < 10^8 tries.
    phone_only = "rappeler 06 12 34 56 78"
    r2 = coordinator(["hits"])[0].run(phone_only)
    print(f"C requête téléphone seule : statut={r2['status']} ; rapport.query_sha256 = digest(brut) : {r2['query_sha256'] == digest(phone_only)}")

    print("== D. requête vide après nettoyage : aucun contact")
    for name, q in (("courriel seul", "jean@example.invalid"), ("IP + téléphone", "198.51.100.7 06 12 34 56 78"),
                    ("URL seule", "https://example.invalid/x?token=AbC123secret")):
        c, providers, reader, resolver = coordinator(["hits", "hits"])
        report = c.run(q)
        print(f"D {name}: statut={report['status']} ; discovery={report['discovery_status']} ; "
              f"fournisseurs={sum(len(p.queries) for p in providers)} lecteur={reader.calls} DNS={resolver.calls}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g050-") as root:
        guard = ResearchGuard(Path(root) / "guard")
        c, providers, reader, resolver = coordinator(["hits"], guard)
        report = c.run("jean@example.invalid")
        state = guard.inspect()
        raw = b"".join(p.read_bytes() for p in Path(root).rglob("*") if p.is_file())
        print(f"D avec garde : statut={report['status']} ; fournisseurs={len(providers[0].queries)} DNS={resolver.calls} ; "
              f"garde : {[(r['state'], r['outcome']) for r in state['runs']] if isinstance(state, dict) and 'runs' in state else state}")
        print(f"D fichiers de la garde contenant la valeur retirée : {b'example.invalid' in raw}")
        c2 = coordinator(["hits"], guard)[0]
        print(f"D avec garde, requête normale ensuite : statut={c2.run('documentation pont')['status']}")

    print("== E. diagnostics sans écho")
    for name, q in (("contrôle U+0007", "jean@example.invalid\x07"), ("trop long", "jean@example.invalid " + "x" * 1000),
                    ("NFKC trop long", "jean@example.invalid " + "\ufb03" * 400)):
        try:
            clean_query(q)
            print(f"E {name}: accepté")
        except ContractError as exc:
            print(f"E {name}: {exc} ; valeur dans le message : {'example.invalid' in str(exc)}")
        try:
            coordinator(["hits"])[0].run(q)
        except ContractError as exc:
            print(f"E {name} via run : {type(exc).__name__} {exc} ; valeur dans le message : {'example.invalid' in str(exc)}")


if __name__ == "__main__":
    main()

# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : build_corpus.py
# Description : Génère le corpus synthétique de recherche Web (C-TASK-G007)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Write cases.json from the synthetic bodies. Deterministic, no network.

From this directory:  python build_corpus.py
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOW = "2026-10-05T15:00:00+00:00"  # synthetic clock for every case


def body(name):
    raw = (HERE / "bodies" / name).read_bytes()
    return {"body": f"bodies/{name}", "body_sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def page(name, status=200, content_type="text/html; charset=utf-8", **headers):
    return {"status": status, "headers": {"Content-Type": content_type, **headers}, **body(name)}


def result(url, title, snippet):
    return {"url": url, "title": title, "snippet": snippet}


DOCS = "https://docs.synthetic-tool.example/config"
MIRROR = "https://mirror.other-host.example/synthetic-tool/config"
NOTES = "https://blog.community.example/tuning-notes"
NEWS = "https://news.synthetic-tool.example/release-2.5.txt"
ARTICLE = "https://magazine.example/how-captcha-works"
CHALLENGE = "https://guarded.example/article"
LOGIN = "https://members.example/article"
SOFT404 = "https://docs.synthetic-tool.example/old-page"
PAYWALL = "https://daily.example/storage-prices"
FORBIDDEN = "https://restricted.example/report"

DEFAULT_BUDGET = {"provider_calls": 4, "page_fetches": 5, "seconds": 30}


def case(cid, title, category, why, *, query="synthetic tool max_workers default", providers=None,
         order=("engine-a", "engine-b"), pages=None, cache=(), policy=None, budget=None, robots=None,
         expected):
    return {"id": cid, "title": title, "category": category, "why": why,
            "setup": {"query": query, "providers": providers or {}, "provider_order": list(order),
                      "pages": pages or {}, "cache": list(cache), "robots": robots or {},
                      "policy": policy or {"blocked_domains": []}, "budget": budget or DEFAULT_BUDGET},
            "expected": expected}


def ok(*results):
    return {"status": "ok", "results": list(results)}


CASES = [
    case("W01", "Fournisseur A en 429 avec Retry-After long, B disponible", "quota",
         "Un 429 n'est ni une absence de résultat ni une raison d'attendre au-delà du budget.",
         providers={"engine-a": {"status": "http_429", "retry_after_seconds": 120},
                    "engine-b": ok(result(DOCS, "Configuration reference", "max_workers defaults to 4"))},
         pages={DOCS: page("docs-v2.html")},
         expected={"outcome": "ANSWERED", "providers": {"engine-a": "RATE_LIMITED", "engine-b": "USED"},
                   "items": [{"url": DOCS, "state": "READ"}], "provider_calls_max": 2,
                   "must_not": ["retry_before_retry_after", "sleep_beyond_budget"]}),
    case("W02", "Page en 429 avec Retry-After court", "quota",
         "Une première version peut rendre l'indisponibilité explicite ; un unique réessai après le délai est aussi acceptable.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "max_workers defaults to 4"))},
         pages={DOCS: {"status": 429, "headers": {"Retry-After": "5"}, "sequence_after_retry": page("docs-v2.html")}},
         expected={"outcome_any_of": ["UNAVAILABLE", "ANSWERED"],
                   "items": [{"url": DOCS, "state_any_of": ["RATE_LIMITED", "READ"]}],
                   "page_fetches_max": 2, "must_not": ["retry_before_retry_after", "more_than_one_retry"]}),
    case("W03", "403 sur un résultat, un autre résultat lisible", "access",
         "Un refus d'accès est un état de la source, pas un échec de la recherche entière.",
         providers={"engine-a": ok(result(FORBIDDEN, "Report", "restricted"),
                                   result(DOCS, "Configuration reference", "max_workers defaults to 4"))},
         pages={FORBIDDEN: page("forbidden-403.html", status=403), DOCS: page("docs-v2.html")},
         expected={"outcome": "ANSWERED", "items": [{"url": FORBIDDEN, "state": "ACCESS_DENIED"},
                                                    {"url": DOCS, "state": "READ"}],
                   "must_not": ["retry_forbidden"]}),
    case("W04", "Défi anti-robot servi en HTTP 200", "challenge",
         "Un 200 ne prouve pas une page lue : ce contenu n'est pas exploitable.",
         providers={"engine-a": ok(result(CHALLENGE, "Guarded article", "an article about configuration"))},
         pages={CHALLENGE: page("challenge-200.html")},
         expected={"outcome": "NEEDS_USER", "items": [{"url": CHALLENGE, "state": "CHALLENGE"}],
                   "must_not": ["treat_challenge_as_read", "change_identity", "solve_challenge_automatically"]}),
    case("W05", "Article légitime qui parle de CAPTCHA", "challenge",
         "Le détecteur ne doit pas refuser un vrai article qui cite les phrases d'un défi.",
         query="how do captcha challenges work",
         providers={"engine-a": ok(result(ARTICLE, "How CAPTCHA challenges work", "an explainer"))},
         pages={ARTICLE: page("captcha-article.html")},
         expected={"outcome": "ANSWERED", "items": [{"url": ARTICLE, "state": "READ"}],
                   "must_not": ["treat_article_as_challenge"]}),
    case("W06", "Source connue seulement par son extrait", "snippet",
         "Un extrait du moteur reste un extrait : la réponse est partielle et le dit.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "max_workers defaults to 4"))},
         pages={DOCS: {"status": "timeout"}},
         expected={"outcome": "PARTIAL", "items": [{"url": DOCS, "state": "SNIPPET_ONLY"}],
                   "must_not": ["claim_full_text_from_snippet"]}),
    case("W07", "Même résultat renvoyé par deux moteurs", "duplicate",
         "Une URL canonique identique (paramètres de suivi retirés) n'est lue qu'une fois.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "max_workers defaults to 4")),
                    "engine-b": ok(result(DOCS + "?utm_source=engine-b", "Configuration", "defaults to 4"))},
         order=("engine-a", "engine-b"), pages={DOCS: page("docs-v2.html")},
         expected={"outcome": "ANSWERED", "items": [{"url": DOCS, "state": "READ"}], "page_fetches_max": 1,
                   "must_not": ["fetch_same_canonical_url_twice"]}),
    case("W08", "Copie identique sur un autre domaine", "duplicate",
         "Deux pages au contenu identique ne sont pas deux sources indépendantes.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"),
                                   result(MIRROR, "Mirror — configuration", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html"), MIRROR: page("docs-mirror.html")},
         expected={"outcome": "ANSWERED", "independent_sources": 1,
                   "items": [{"url": DOCS, "state": "READ"}, {"url": MIRROR, "state": "READ", "same_content_as": DOCS}],
                   "must_not": ["count_mirror_as_independent"],
                   "note": "Les octets diffèrent (titre), le texte principal est identique : comparer le texte extrait, pas seulement le SHA-256 brut."}),
    case("W09", "Cache périmé, site disponible", "cache",
         "Une copie ancienne n'est pas une observation actuelle : relire et dater.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html")},
         cache=[{"url": DOCS, "fetched_at": "2026-09-05T15:00:00+00:00", "max_age_days": 7, **body("docs-v2.html")}],
         expected={"outcome": "ANSWERED", "items": [{"url": DOCS, "state": "READ", "observed_at": NOW}],
                   "page_fetches_max": 1, "must_not": ["serve_stale_cache_as_current"]}),
    case("W10", "Cache périmé, site en panne", "cache",
         "Sans relecture possible, la copie peut être montrée avec sa date, jamais comme actuelle.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"))},
         pages={DOCS: {"status": 503, "headers": {}}},
         cache=[{"url": DOCS, "fetched_at": "2026-09-05T15:00:00+00:00", "max_age_days": 7, **body("docs-v2.html")}],
         expected={"outcome": "PARTIAL", "items": [{"url": DOCS, "state": "CACHE_STALE",
                                                    "observed_at": "2026-09-05T15:00:00+00:00"}],
                   "must_not": ["serve_stale_cache_as_current"]}),
    case("W11", "Domaine mis en liste noire après mise en cache", "policy",
         "Le cache obéit à la politique actuelle : aucune lecture ni restitution d'un domaine désormais bloqué.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html")},
         cache=[{"url": DOCS, "fetched_at": "2026-10-05T14:00:00+00:00", "max_age_days": 7, **body("docs-v2.html")}],
         policy={"blocked_domains": ["docs.synthetic-tool.example"]},
         expected={"outcome": "NO_EVIDENCE", "items": [{"url": DOCS, "state": "POLICY_REFUSED"}],
                   "page_fetches_max": 0, "must_not": ["serve_cache_after_policy_change", "contact_blocked_domain"]}),
    case("W12", "Page de connexion", "access",
         "Un formulaire d'identification n'est pas le contenu ; aucun identifiant n'est envoyé.",
         providers={"engine-a": ok(result(LOGIN, "Members article", "members only"))},
         pages={LOGIN: page("login.html")},
         expected={"outcome": "NEEDS_USER", "items": [{"url": LOGIN, "state": "LOGIN_REQUIRED"}],
                   "must_not": ["submit_credentials", "treat_login_as_read"]}),
    case("W13", "Résultats contradictoires de dates différentes", "contradiction",
         "Les sources se contredisent : montrer le désaccord et les dates, ne pas choisir en silence.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference 2.4", "defaults to 4"),
                                   result(NOTES, "Tuning notes", "defaults to 8")),
                    "engine-b": ok(result(NEWS, "Release 2.5", "default is now 6"))},
         pages={DOCS: page("docs-v2.html"), NOTES: page("docs-contradiction.html"),
                NEWS: page("news-2026.txt", content_type="text/plain; charset=utf-8")},
         expected={"outcome": "ANSWERED_WITH_CONFLICT",
                   "items": [{"url": DOCS, "state": "READ"}, {"url": NOTES, "state": "READ"},
                             {"url": NEWS, "state": "READ"}],
                   "conflict": {"claim": "max_workers default", "values": {"4": DOCS, "8": NOTES, "6": NEWS}},
                   "must_not": ["pick_one_side_silently"],
                   "note": "La date de publication et la version citée sont des indices, pas une vérité : les restituer."}),
    case("W14", "Tous les fournisseurs en panne", "provider",
         "Une panne n'est pas « aucun résultat ».",
         providers={"engine-a": {"status": "down"}, "engine-b": {"status": "timeout"}},
         expected={"outcome": "UNAVAILABLE", "providers": {"engine-a": "PROVIDER_UNAVAILABLE",
                                                          "engine-b": "PROVIDER_UNAVAILABLE"},
                   "items": [], "provider_calls_max": 2, "must_not": ["report_no_results_when_down"]}),
    case("W15", "Recherche sans résultat", "provider",
         "Distinct de W14 : le fournisseur répond, il n'a rien trouvé.",
         providers={"engine-a": ok(), "engine-b": ok()},
         expected={"outcome": "NO_RESULTS", "items": []}),
    case("W16", "Budget de lecture insuffisant", "budget",
         "Le budget s'épuise : les résultats non lus restent visibles comme tels.",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"),
                                   result(NOTES, "Tuning notes", "defaults to 8"),
                                   result(NEWS, "Release 2.5", "default is now 6"),
                                   result(ARTICLE, "CAPTCHA", "unrelated"),
                                   result(MIRROR, "Mirror", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html"), NOTES: page("docs-contradiction.html"),
                NEWS: page("news-2026.txt", content_type="text/plain; charset=utf-8"),
                ARTICLE: page("captcha-article.html"), MIRROR: page("docs-mirror.html")},
         budget={"provider_calls": 1, "page_fetches": 2, "seconds": 30},
         expected={"outcome": "PARTIAL", "page_fetches_max": 2, "items_read_max": 2,
                   "unread_state": "NOT_FETCHED_BUDGET", "must_not": ["exceed_budget", "hide_unread_results"]}),
    case("W17", "Chemin interdit par robots.txt", "etiquette",
         "Respecter robots.txt est un choix de politesse explicite (RFC 9309), à configurer et à tracer.",
         providers={"engine-a": ok(result("https://docs.synthetic-tool.example/private/notes", "Private notes", "x"),
                                   result(DOCS, "Configuration reference", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html")},
         robots={"https://docs.synthetic-tool.example/robots.txt": body("robots-disallow.txt")},
         expected={"outcome": "ANSWERED", "items": [
             {"url": "https://docs.synthetic-tool.example/private/notes", "state": "ROBOTS_DISALLOWED"},
             {"url": DOCS, "state": "READ"}], "must_not": ["fetch_disallowed_path"]}),
    case("W18", "Fausse page 200 « introuvable »", "exploitable",
         "Un soft-404 n'est pas une page lue.",
         providers={"engine-a": ok(result(SOFT404, "Old configuration page", "defaults to 4"))},
         pages={SOFT404: page("soft-404.html")},
         expected={"outcome": "NO_EVIDENCE", "items": [{"url": SOFT404, "state": "NOT_FOUND"}],
                   "must_not": ["treat_soft_404_as_read"]}),
    case("W19", "Article tronqué par un abonnement", "exploitable",
         "Un début d'article est une lecture partielle, à ne pas présenter comme texte intégral.",
         query="storage prices 2026",
         providers={"engine-a": ok(result(PAYWALL, "Storage prices in 2026", "prices moved"))},
         pages={PAYWALL: page("paywall.html")},
         expected={"outcome": "PARTIAL", "items": [{"url": PAYWALL, "state": "PARTIAL_CONTENT"}],
                   "must_not": ["claim_full_text_from_partial"]}),
    case("W20", "Requête contenant des données personnelles", "privacy",
         "La requête envoyée à un tiers est minimisée : rien de personnel ne sort.",
         query="synthetic tool max_workers default (contexte: écrire à jean.exemple@example.invalid au 01 23 45 67 89)",
         providers={"engine-a": ok(result(DOCS, "Configuration reference", "defaults to 4"))},
         pages={DOCS: page("docs-v2.html")},
         expected={"outcome": "ANSWERED", "items": [{"url": DOCS, "state": "READ"}],
                   "sent_query_must_not_contain": ["jean.exemple@example.invalid", "01 23 45 67 89"],
                   "must_not": ["send_personal_data_in_query"]}),
]


def main():
    corpus = {"schema": "eidolon-research-corpus/1", "author": "Claude", "task": "C-TASK-G007",
              "clock": NOW, "synthetic": True, "cases": CASES}
    (HERE / "cases.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(CASES)} cases written")


if __name__ == "__main__":
    main()

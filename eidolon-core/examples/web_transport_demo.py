# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : web_transport_demo.py
# Description : Démonstration synthétique du transport HTTP de lecture candidat
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Three synthetic fetches: redirected success, LAN redirect refused, compressed body refused.

From eidolon-core/:  PYTHONPATH=src:. python -m examples.web_transport_demo
No socket is opened: DNS and the connector are simulated.
"""
import json

from eidolon_core.egress import WebPolicy
from eidolon_core.web_transport import RawResponse, WebTransportError, fetch

DNS = {"docs.example.com": ["93.184.215.14"], "cdn.example.com": ["93.184.215.15"],
       "nas.attacker.example": ["192.168.1.10"]}


class SyntheticConnector:
    SCRIPT = {
        ("93.184.215.14", "/start"): RawResponse(301, (("Location", "https://cdn.example.com/page"),), b"", True),
        ("93.184.215.15", "/page"): RawResponse(200, (("Content-Type", "text/plain"), ("Content-Length", "21")),
                                                b"synthetic public page", True),
        ("93.184.215.14", "/to-lan"): RawResponse(302, (("Location", "https://nas.attacker.example/admin"),),
                                                  b"", True),
        ("93.184.215.14", "/gzip"): RawResponse(200, (("Content-Encoding", "gzip"),), b"\x1f\x8b...", True),
    }

    def __init__(self):
        self.contacted = []

    def exchange(self, *, address, target, **_):
        self.contacted.append(f"{address}{target}")
        return self.SCRIPT[(address, target)]


def main():
    policy = WebPolicy()
    report = {}
    for path in ("/start", "/to-lan", "/gzip"):
        connector = SyntheticConnector()
        try:
            result = fetch("https://docs.example.com" + path, policy=policy,
                           resolver=lambda host, port: DNS[host], connector=connector)
            report[path] = {"outcome": "FETCHED", **result.evidence()}
        except WebTransportError as exc:
            report[path] = {"outcome": "REFUSED", "code": exc.code, "detail": str(exc)}
        report[path]["contacted"] = connector.contacted
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

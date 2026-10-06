# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : egress_probe.py
# Description : Sonde des refus de destination (adresses spéciales, URL piégées), sans réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python docs/validation/2026-10-06/claude-audit-global/egress_probe.py
The resolver is a lambda returning the tested address: no DNS, no connection."""
from eidolon_core.egress import decide

ADDRESSES = ["127.0.0.1", "0.0.0.0", "10.0.0.1", "100.64.0.1", "169.254.169.254", "172.16.0.1", "192.168.1.1",
             "192.0.0.8", "192.0.2.1", "198.18.0.1", "198.51.100.1", "203.0.113.1", "224.0.0.1", "240.0.0.1",
             "255.255.255.255", "::", "::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1", "64:ff9b::7f00:1",
             "64:ff9b:1::a00:1", "2002:7f00:1::1", "2001::1", "2001:db8::1", "fc00::1", "fe80::1", "ff02::1",
             "::127.0.0.1", "100::1", "2001:10::1", "9.9.9.9", "2606:4700::1111"]
URLS = ["https://0x7f.0.0.1/", "https://0177.0.0.1/", "https://127.1/", "https://2130706433/", "https://[::ffff:7f00:1]/",
        "https://docs.example:443@evil.example/", "https://docs.example\\@evil.example/", "https://docs.example%2F@evil.example/",
        "https://DOCS.EXAMPLE./a", "https://localhost./", "https://foo.internal/", "https://docs.example:0443/",
        "https://docs.example:+443/", "https://docs.example#@evil.example/", "http://docs.example/", "https://docs.example:8443/"]

for address in ADDRESSES:
    d = decide("https://docs.example/", lambda host, port, a=address: [a])
    print(f"{address:22} {'ALLOWED' if d.allowed else d.code}")
for url in URLS:
    d = decide(url, lambda host, port: ["9.9.9.9"])
    print(f"{url:42} {'ALLOWED host=' + d.host if d.allowed else d.code}")

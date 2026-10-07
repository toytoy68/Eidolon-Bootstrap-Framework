// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : origin.rs
// Description : Origine unique autorisée pour la fenêtre de consultation (C-TASK-G053)
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
//! Pure, testable rules: the window may only show `http://127.0.0.1:<port>/…`, the
//! address where the SSH tunnel exposes the Core-served client. No other host, no
//! `localhost` alias, no credentials in the URL, no other scheme.

use tauri::Url;

pub const DEFAULT_PORT: u16 = 8765;

/// Port from `--port N` or `EIDOLON_CORE_PORT`; the argument wins. Unprivileged ports only.
pub fn parse_port(args: &[String], env: Option<&str>) -> Result<u16, String> {
    let mut value = env.map(str::to_owned);
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--port" {
            value = Some(args.get(i + 1).cloned().ok_or("--port attend une valeur")?);
            i += 1;
        } else {
            return Err(format!("argument inconnu : {}", args[i]));
        }
        i += 1;
    }
    let Some(text) = value else { return Ok(DEFAULT_PORT) };
    if text.is_empty() || text.len() > 5 || !text.bytes().all(|b| b.is_ascii_digit()) {
        return Err("port invalide : 1024 à 65535".into());
    }
    match text.parse::<u32>() {
        Ok(p) if (1024..=65535).contains(&p) => Ok(p as u16),
        _ => Err("port invalide : 1024 à 65535".into()),
    }
}

pub fn start_url(port: u16) -> Url {
    Url::parse(&format!("http://127.0.0.1:{port}/")).expect("static loopback URL")
}

/// Same origin as the start URL, nothing else (checked on every navigation).
pub fn allowed(url: &Url, port: u16) -> bool {
    url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port() == Some(port)
        && url.username().is_empty()
        && url.password().is_none()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn port_sources_and_bounds() {
        assert_eq!(parse_port(&[], None), Ok(8765));
        assert_eq!(parse_port(&[], Some("9000")), Ok(9000));
        assert_eq!(parse_port(&args(&["--port", "9100"]), Some("9000")), Ok(9100));
        for bad in ["0", "80", "1023", "65536", "99999999", "", "+9000", " 9000", "9000 ", "0x2000", "٩٠٠٠"] {
            assert!(parse_port(&args(&["--port", bad]), None).is_err(), "{bad:?}");
        }
        assert!(parse_port(&args(&["--port"]), None).is_err());
        assert!(parse_port(&args(&["--url", "http://evil.example/"]), None).is_err());
    }

    #[test]
    fn only_the_exact_loopback_origin() {
        let ok = ["http://127.0.0.1:8765/", "http://127.0.0.1:8765/app.js", "http://127.0.0.1:8765/v1/health?x=1#f"];
        for u in ok {
            assert!(allowed(&Url::parse(u).unwrap(), 8765), "{u}");
        }
        let refused = [
            "http://127.0.0.1:8766/",             // other port
            "http://localhost:8765/",             // alias: Host differs, other origin
            "https://127.0.0.1:8765/",            // scheme
            "http://127.0.0.2:8765/",             // other loopback address
            "http://[::1]:8765/",                 // IPv6 loopback
            "http://127.0.0.1.nip.io:8765/",      // DNS name embedding the address
            "http://user:pw@127.0.0.1:8765/",     // credentials
            "http://2130706433:8765/",            // integer form, normalised by the parser
            "http://0x7f.0.0.1:8765/",            // hex form, normalised by the parser
            "file:///etc/passwd",
            "about:blank",
            "data:text/html,<p>x</p>",
            "javascript:alert(1)",
            "tauri://localhost/",
            "http://evil.example/",
        ];
        for u in refused {
            let parsed = Url::parse(u).unwrap();
            let expected = matches!(u, "http://2130706433:8765/" | "http://0x7f.0.0.1:8765/");
            // The URL parser normalises numeric IPv4 forms to 127.0.0.1: same socket, same origin.
            assert_eq!(allowed(&parsed, 8765), expected, "{u} -> {parsed}");
        }
    }
}

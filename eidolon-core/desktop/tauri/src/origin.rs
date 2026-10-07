// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : origin.rs
// Description : Origine unique autorisée et entrées bornées de la fenêtre de consultation (C-TASK-G053/G054)
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
//! Pure, testable rules: the window may only show `http://127.0.0.1:<port>/…`, the
//! address where the SSH tunnel exposes the Core-served client. No other host, no
//! `localhost` alias, no credentials in the URL, no other scheme.
//!
//! G054: diagnostics are constant codes. They never repeat an argument, an environment
//! value or a refused URL, which could carry a token or a private address.

use std::ffi::OsString;

use tauri::Url;

pub const DEFAULT_PORT: u16 = 8765;

/// Constant diagnostics: the only texts this module lets the shell print.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InputError {
    UnknownArgument,
    MissingPortValue,
    RepeatedPort,
    InvalidPort,
    InvalidEnvironmentPort,
}

impl InputError {
    pub fn message(self) -> &'static str {
        match self {
            InputError::UnknownArgument => "argument non reconnu (seul --port N est accepté)",
            InputError::MissingPortValue => "--port attend une valeur",
            InputError::RepeatedPort => "--port donné plusieurs fois",
            InputError::InvalidPort => "port invalide : 1024 à 65535",
            InputError::InvalidEnvironmentPort => "EIDOLON_CORE_PORT invalide : 1024 à 65535",
        }
    }
}

/// Navigation and new-window refusals: never the URL, only what kind of target it was.
pub const NAVIGATION_REFUSED: &str = "navigation refusée : autre origine que le client Core";
pub const NEW_WINDOW_REFUSED: &str = "nouvelle fenêtre refusée";

fn port_value(raw: &OsString) -> Option<u16> {
    // Non-UTF-8, signs, spaces, controls, other digit scripts: all refused, never repaired.
    let text = raw.to_str()?;
    if text.is_empty() || text.len() > 5 || !text.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let value: u32 = text.parse().ok()?;
    (1024..=65535).contains(&value).then_some(value as u16)
}

/// Port from `--port N` (exactly once) or `EIDOLON_CORE_PORT`; the argument wins, but an
/// environment value that is present and invalid is refused even then, not ignored.
pub fn parse_port(args: &[OsString], env: Option<&OsString>) -> Result<u16, InputError> {
    let env_port = match env {
        None => None,
        Some(raw) => Some(port_value(raw).ok_or(InputError::InvalidEnvironmentPort)?),
    };
    let mut arg_port = None;
    let mut i = 0;
    while i < args.len() {
        if args[i].to_str() != Some("--port") {
            return Err(InputError::UnknownArgument);
        }
        if arg_port.is_some() {
            return Err(InputError::RepeatedPort);
        }
        let raw = args.get(i + 1).ok_or(InputError::MissingPortValue)?;
        arg_port = Some(port_value(raw).ok_or(InputError::InvalidPort)?);
        i += 2;
    }
    Ok(arg_port.or(env_port).unwrap_or(DEFAULT_PORT))
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

    fn os(v: &[&str]) -> Vec<OsString> {
        v.iter().map(OsString::from).collect()
    }

    const ALL: [InputError; 5] = [
        InputError::UnknownArgument,
        InputError::MissingPortValue,
        InputError::RepeatedPort,
        InputError::InvalidPort,
        InputError::InvalidEnvironmentPort,
    ];

    #[test]
    fn port_sources_and_bounds() {
        assert_eq!(parse_port(&[], None), Ok(8765));
        assert_eq!(parse_port(&[], Some(&"9000".into())), Ok(9000));
        assert_eq!(
            parse_port(&os(&["--port", "9100"]), Some(&"9000".into())),
            Ok(9100)
        );
        assert_eq!(parse_port(&os(&["--port", "1024"]), None), Ok(1024));
        assert_eq!(parse_port(&os(&["--port", "65535"]), None), Ok(65535));
        assert_eq!(parse_port(&os(&["--port", "08765"]), None), Ok(8765));
        for bad in [
            "0",
            "80",
            "1023",
            "65536",
            "99999999",
            "",
            "+9000",
            "-9000",
            " 9000",
            "9000 ",
            "0x2000",
            "٩٠٠٠",
            "９０００",
            "9000\n",
            "9\u{0}000",
            "9000\u{200b}",
        ] {
            assert_eq!(
                parse_port(&os(&["--port", bad]), None),
                Err(InputError::InvalidPort),
                "{bad:?}"
            );
            assert_eq!(
                parse_port(&[], Some(&bad.into())),
                Err(InputError::InvalidEnvironmentPort),
                "{bad:?}"
            );
        }
    }

    #[test]
    fn argument_shapes() {
        assert_eq!(
            parse_port(&os(&["--port"]), None),
            Err(InputError::MissingPortValue)
        );
        assert_eq!(
            parse_port(&os(&["--port", "9000", "--port", "9000"]), None),
            Err(InputError::RepeatedPort)
        );
        assert_eq!(
            parse_port(&os(&["--port", "9000", "--port", "9100"]), None),
            Err(InputError::RepeatedPort)
        );
        assert_eq!(
            parse_port(&os(&["--port=9000"]), None),
            Err(InputError::UnknownArgument)
        );
        assert_eq!(
            parse_port(&os(&["--PORT", "9000"]), None),
            Err(InputError::UnknownArgument)
        );
        assert_eq!(
            parse_port(&os(&["9000"]), None),
            Err(InputError::UnknownArgument)
        );
        assert_eq!(
            parse_port(&os(&["--port", "9000", "extra"]), None),
            Err(InputError::UnknownArgument)
        );
        assert_eq!(
            parse_port(&os(&["--url", "http://evil.example/"]), None),
            Err(InputError::UnknownArgument)
        );
        // A valid argument does not hide an invalid environment value.
        assert_eq!(
            parse_port(&os(&["--port", "9000"]), Some(&"abc".into())),
            Err(InputError::InvalidEnvironmentPort)
        );
    }

    #[cfg(unix)]
    #[test]
    fn non_utf8_inputs_are_refused_not_defaulted() {
        use std::os::unix::ffi::OsStringExt;
        let bad = OsString::from_vec(vec![0x39, 0x30, 0xff, 0x30]);
        assert_eq!(
            parse_port(&[OsString::from("--port"), bad.clone()], None),
            Err(InputError::InvalidPort)
        );
        assert_eq!(
            parse_port(std::slice::from_ref(&bad), None),
            Err(InputError::UnknownArgument)
        );
        assert_eq!(
            parse_port(&[], Some(&bad)),
            Err(InputError::InvalidEnvironmentPort)
        );
    }

    #[test]
    fn diagnostics_never_echo_inputs() {
        // Synthetic secrets: token-like value, private address, path, control characters.
        let secrets = [
            "tok_9fK2synthetiqueG054xYz",
            "192.0.2.77",
            "/home/jean/secret",
            "\u{1b}[31m",
            "\r\nX-Injected: 1",
        ];
        for s in secrets {
            for args in [
                vec!["--port", s],
                vec![s],
                vec!["--port", "9000", "--port", s],
                vec!["--port", "9000", s],
            ] {
                let err = parse_port(&os(&args), None).unwrap_err();
                assert!(!err.message().contains(s), "{s:?} echoed");
            }
            let err = parse_port(&[], Some(&s.into())).unwrap_err();
            assert!(!err.message().contains(s), "{s:?} echoed from env");
        }
        for e in ALL {
            let m = e.message();
            assert!(m.chars().all(|c| !c.is_control()), "{e:?}");
            assert!(m.len() < 80, "{e:?}");
        }
        for m in [NAVIGATION_REFUSED, NEW_WINDOW_REFUSED] {
            assert!(!m.contains("://") && m.chars().all(|c| !c.is_control()));
        }
    }

    #[test]
    fn only_the_exact_loopback_origin() {
        let ok = [
            "http://127.0.0.1:8765/",
            "http://127.0.0.1:8765/app.js",
            "http://127.0.0.1:8765/v1/health?x=1#f",
        ];
        for u in ok {
            assert!(allowed(&Url::parse(u).unwrap(), 8765), "{u}");
        }
        let refused = [
            "http://127.0.0.1:8766/",         // other port
            "http://localhost:8765/",         // alias: Host differs, other origin
            "https://127.0.0.1:8765/",        // scheme
            "http://127.0.0.2:8765/",         // other loopback address
            "http://[::1]:8765/",             // IPv6 loopback
            "http://127.0.0.1.nip.io:8765/",  // DNS name embedding the address
            "http://user:pw@127.0.0.1:8765/", // credentials
            "http://user@127.0.0.1:8765/",    // user name only
            "http://127.0.0.1/",              // default port 80
            "file:///etc/passwd",
            "about:blank",
            "data:text/html,<p>x</p>",
            "blob:http://127.0.0.1:8765/x",
            "javascript:alert(1)",
            "tauri://localhost/",
            "ws://127.0.0.1:8765/",
            "http://evil.example/",
        ];
        for u in refused {
            assert!(!allowed(&Url::parse(u).unwrap(), 8765), "{u}");
        }
        // The URL parser normalises numeric IPv4 forms to 127.0.0.1: same socket, same origin.
        for u in [
            "http://2130706433:8765/",
            "http://0x7f.0.0.1:8765/",
            "http://127.1:8765/",
        ] {
            assert!(allowed(&Url::parse(u).unwrap(), 8765), "{u}");
        }
    }
}

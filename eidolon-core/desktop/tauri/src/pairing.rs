// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : pairing.rs
// Description : One-page auto-open from a launcher-provided private credential
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
use std::ffi::OsStr;

pub const ENV_KEY: &str = "EIDOLON_CONVERSATION_KEY";
pub const INVALID_KEY: &str = "clé d'appairage locale invalide";

// No IPC/global credential accessor. Only the selected top-level Core page may
// receive the key; its existing submit handler clears the field immediately.
const AUTO_OPEN: &str = r#"(() => {
  if (window.top !== window || window.location.origin !== 'http://127.0.0.1:__PORT__' || window.location.pathname !== '/') return;
  let key = '__KEY__';
  const open = () => {
    const input = document.getElementById('conv-key');
    const form = document.getElementById('conv-connect');
    if (!input || !form || !key) { key = null; return; }
    try {
      input.value = key;
      key = null;
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    } finally { input.value = ''; key = null; }
  };
  if (document.readyState === 'complete') open();
  else window.addEventListener('load', open, { once: true });
})();"#;

pub fn script(raw: Option<&OsStr>, port: u16) -> Result<Option<String>, &'static str> {
    let Some(raw) = raw else { return Ok(None); };
    let key = raw.to_str().ok_or(INVALID_KEY)?;
    if key.len() != 47 || !key.starts_with("ecc_")
        || !key.as_bytes()[4..].iter().all(|b| b.is_ascii_alphanumeric() || *b == b'_' || *b == b'-') {
        return Err(INVALID_KEY);
    }
    Ok(Some(AUTO_OPEN.replace("__PORT__", &port.to_string()).replace("__KEY__", key)))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn absence_preserves_manual_login() { assert_eq!(script(None, 8767), Ok(None)); }
    #[test]
    fn only_exact_credential_format_enters_script() {
        let key = format!("ecc_{}", "A".repeat(43));
        let s = script(Some(OsStr::new(&key)), 8767).unwrap().unwrap();
        assert!(s.contains("http://127.0.0.1:8767"));
        assert!(s.contains("window.top !== window"));
        assert!(!s.contains("__KEY__"));
        for bad in ["", "private-token", "ecc_'<script>", "ecc_\n"] {
            assert_eq!(script(Some(OsStr::new(bad)), 8767), Err(INVALID_KEY));
        }
        assert!(script(Some(OsStr::new(&(key + "A"))), 8767).is_err());
    }
    #[cfg(unix)]
    #[test]
    fn non_utf8_is_refused_without_echo() {
        use std::os::unix::ffi::OsStrExt;
        assert_eq!(script(Some(OsStr::from_bytes(&[255])), 8767), Err(INVALID_KEY));
    }
}

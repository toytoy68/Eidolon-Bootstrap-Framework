// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : main.rs
// Description : Fenêtre Tauri 2 de consultation, sans IPC ni plugin (C-TASK-G053)
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
//! Opens ONE window on the client already served by Core through the SSH tunnel
//! (`http://127.0.0.1:<port>/`). The page keeps Core's same-origin contract: it talks
//! to Core with fetch, never through Tauri. No command handler, plugin or capability
//! is registered, so the remote page has no IPC permission. The shell does not start
//! the tunnel, store the token, autostart or install anything.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod origin;

use tauri::webview::NewWindowResponse;
use tauri::{WebviewUrl, WebviewWindowBuilder};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let port = match origin::parse_port(&args, std::env::var("EIDOLON_CORE_PORT").ok().as_deref()) {
        Ok(port) => port,
        Err(message) => {
            eprintln!("eidolon-consultation : {message}");
            std::process::exit(2);
        }
    };
    let start = origin::start_url(port);
    tauri::Builder::default()
        .setup(move |app| {
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(start.clone()))
                .title(format!("Eidolon — consultation (127.0.0.1:{port})"))
                .inner_size(1100.0, 800.0)
                .devtools(false)
                .on_navigation(move |url| {
                    let ok = origin::allowed(url, port);
                    if !ok {
                        eprintln!("eidolon-consultation : navigation refusée vers {}", url.origin().ascii_serialization());
                    }
                    ok
                })
                // window.open / target=_blank: never a second window, never the system browser.
                .on_new_window(|url, _| {
                    eprintln!("eidolon-consultation : nouvelle fenêtre refusée vers {}", url.origin().ascii_serialization());
                    NewWindowResponse::Deny
                })
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("eidolon-consultation: Tauri runtime failed");
}

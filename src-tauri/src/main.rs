#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Desktop shell: starts the local engine as a child process, reads its
//! ENGINE_READY handshake to learn the port, and opens the web UI in a
//! WebView2 window. If the engine dies after the handshake, it is restarted
//! and the window is pointed at the new port. Closing the window stops the
//! engine and exits the app.

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

struct EngineProcess(Mutex<Option<Child>>);

fn engine_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine")
}

fn engine_ready() -> bool {
    Path::new(".venv\\Scripts\\python.exe").exists()
}

fn spawn_engine() -> Result<Child, String> {
    // The process working directory is the engine folder (set in main), and the
    // interpreter is a fixed relative path. No dynamic input reaches the command.
    Command::new(".venv\\Scripts\\python.exe")
        .args(["-m", "app.sidecar"])
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|err| format!("failed to start the engine: {err}"))
}

fn kill_engine(app: &AppHandle) {
    let child = {
        let state = app.state::<EngineProcess>();
        let mut guard = state.0.lock().unwrap();
        guard.take()
    };
    if let Some(mut child) = child {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn open_or_navigate(app: &AppHandle, port: u16) {
    let url = format!("http://127.0.0.1:{port}/");
    if let Some(window) = app.get_webview_window("main") {
        let script = format!("location.replace('{url}')");
        let _ = window.eval(&script);
        return;
    }
    let shell_app = app.clone();
    let builder = WebviewWindowBuilder::new(
        app,
        "main",
        WebviewUrl::External(url.parse().expect("valid engine url")),
    )
    .title("UlasApp")
    .inner_size(1100.0, 760.0)
    .min_inner_size(720.0, 520.0);
    let window = match builder.build() {
        Ok(window) => window,
        Err(err) => {
            eprintln!("failed to create the main window: {err}");
            return;
        }
    };
    window.on_window_event(move |event| {
        if let tauri::WindowEvent::CloseRequested { .. } = event {
            kill_engine(&shell_app);
            shell_app.exit(0);
        }
    });
}

fn engine_supervisor(app: AppHandle) {
    loop {
        let mut child = match spawn_engine() {
            Ok(child) => child,
            Err(message) => {
                eprintln!("{message}");
                break;
            }
        };
        let mut handshake_port: Option<u16> = None;
        if let Some(stdout) = child.stdout.take() {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                let line = match line {
                    Ok(text) => text,
                    Err(_) => break,
                };
                println!("[engine] {line}");
                if let Some(port) = line
                    .strip_prefix("ENGINE_READY port=")
                    .and_then(|value| value.trim().parse::<u16>().ok())
                {
                    handshake_port = Some(port);
                    open_or_navigate(&app, port);
                }
            }
        }
        {
            let state = app.state::<EngineProcess>();
            *state.0.lock().unwrap() = None;
        }
        let _ = child.wait();
        if handshake_port.is_some() {
            // The engine ran and died; give it a moment, then bring it back up
            // and navigate the existing window to the new port.
            thread::sleep(Duration::from_secs(1));
            continue;
        }
        eprintln!("engine exited before the handshake; giving up");
        break;
    }
}

fn main() {
    let engine = engine_dir();
    if std::env::set_current_dir(&engine).is_err() {
        eprintln!(
            "engine folder not found next to the shell: {}",
            engine.display()
        );
        std::process::exit(1);
    }
    if !engine_ready() {
        eprintln!(
            "the engine virtual environment is missing; create it first (see engine/README.md)"
        );
        std::process::exit(1);
    }
    tauri::Builder::default()
        .manage(EngineProcess(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            thread::spawn(move || engine_supervisor(handle));
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the UlasApp shell");
}

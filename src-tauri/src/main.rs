#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::Manager;

fn main() {
  // Pick an unused port for our FastAPI backend
  let port = portpicker::pick_unused_port().unwrap_or(8000);

  // Spawn the Ollama server sidecar
  let (mut _ollama_rx, _ollama_child) = tauri::api::process::Command::new_sidecar("ollama")
    .expect("Failed to create ollama sidecar command")
    .args(vec!["serve".to_string()])
    .spawn()
    .expect("Failed to spawn ollama sidecar");

  // Spawn the FastAPI backend sidecar
  let (mut _rx, _child) = tauri::api::process::Command::new_sidecar("localmind-backend")
    .expect("Failed to create sidecar command")
    .args(vec!["--port".to_string(), port.to_string()])
    .spawn()
    .expect("Failed to spawn backend sidecar");

  tauri::Builder::default()
    .setup(move |app| {
      let window_url = if cfg!(feature = "custom-protocol") {
        tauri::WindowUrl::App("index.html".into())
      } else {
        tauri::WindowUrl::External("http://localhost:3001".parse().unwrap())
      };

      let _main_window = tauri::WindowBuilder::new(
        app,
        "main",
        window_url,
      )
      .title("LocalMind OS")
      .inner_size(1280.0, 820.0)
      .resizable(true)
      .initialization_script(&format!("window.__localmind_port = {};", port))
      .build()
      .expect("failed to build window");

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

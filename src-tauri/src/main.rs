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
      let main_window = app.get_window("main").unwrap();
      
      // Inject the dynamic API port into the frontend
      let eval_script = format!(
        "window.__localmind_port = '{0}'; window.localStorage.setItem('localmind_api_port', '{0}');",
        port
      );
      let _ = main_window.eval(&eval_script);

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

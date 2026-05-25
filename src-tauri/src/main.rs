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
      
      // Construct the URL with the dynamic API port
      #[cfg(feature = "custom-protocol")]
      let start_url = format!("tauri://localhost/index.html?api_port={}", port);
      
      #[cfg(not(feature = "custom-protocol"))]
      let start_url = format!("http://localhost:3001/?api_port={}", port);

      println!("Navigating to: {}", start_url);
      let _ = main_window.eval(&format!("window.location.replace('{}')", start_url));

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

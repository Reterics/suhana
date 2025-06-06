#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{
    env,
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::Duration,
};

use tauri::Manager;

fn resolve_python_path(project_root: &Path) -> PathBuf {
    let candidates = if cfg!(target_os = "windows") {
        vec![
            project_root.join("..\\.venv\\Scripts\\python.exe"),
            project_root.join("..\\venv\\Scripts\\python.exe"),
        ]
    } else {
        vec![
            project_root.join("../.venv/bin/python"),
            project_root.join("../venv/bin/python"),
        ]
    };

    for path in candidates {
        if path.exists() {
            return path;
        }
    }

    // fallback to system Python
    PathBuf::from("python")
}

fn install_requirements(python_path: &Path, project_root: &Path) -> std::io::Result<()> {
    let requirements_path = project_root.join("../requirements.txt");
    if requirements_path.exists() {
        let status = Command::new(python_path)
            .args(["-m", "pip", "install", "-r"])
            .arg(&requirements_path)
            .current_dir(project_root.join(".."))
            .status()?;

        if !status.success() {
            eprintln!("Failed to install requirements.txt");
        } else {
            println!("requirements.txt installed successfully");
        }
    } else {
        println!("ℹrequirements.txt not found, skipping installation");
    }

    Ok(())
}

fn wait_for_api_ready() -> bool {
    let max_retries = 20;
    let delay = Duration::from_millis(500);
    for _ in 0..max_retries {
        if ureq::get("http://127.0.0.1:8000/health")
            .call()
            .ok()
            .is_some()
        {
            return true;
        }
        thread::sleep(delay);
    }
    false
}


fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let splashscreen_window = app.get_webview_window("splashscreen").unwrap();
            let main_window = app.get_webview_window("main").unwrap();

            let cwd = env::current_dir().expect("Couldn't get current dir");
            let project_root = cwd.parent().expect("Couldn't get project root");

            let python = resolve_python_path(project_root);
            install_requirements(&python, project_root)?;

            let api_path = project_root.join("../api_server.py").canonicalize()
                .expect("Could not resolve api_server.py path");

            let _child = Command::new(python)
                .args([api_path.to_str().unwrap(), "--port", "8000"])
                .current_dir(project_root.join(".."))
                .spawn()
                .expect("Failed to start Suhana backend");


            thread::spawn(move || {
                if wait_for_api_ready() {
                    println!("Backend ready");
                } else {
                    eprintln!("Backend not responding in time");
                }

                splashscreen_window.close().unwrap();
                main_window.show().unwrap();
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri app");
}

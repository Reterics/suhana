#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::process::Command;
use std::path::{Path, PathBuf};
use std::env;
use std::fs;

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
        println!("requirements.txt not found, skipping installation");
    }

    Ok(())
}

fn main() {
    tauri::Builder::default()
    .setup(|_app| {
        let cwd = env::current_dir().expect("Couldn't get current dir");
        let project_root = cwd.parent().expect("Couldn't get project root");

        let python = resolve_python_path(project_root);

        install_requirements(&python, project_root)?;

        let api_server_path = project_root.join("../api_server.py").canonicalize()
            .expect("Could not resolve api_server.py path");

        let child = Command::new(python)
            .arg(api_server_path)
            .current_dir(project_root.join(".."))
            .spawn();

        match child {
            Ok(_) => Ok(()),
            Err(e) => {
              println!("Failed to start Suhana backend: {e}");
              Err(e.into())
            }
          }
    })
    .run(tauri::generate_context!())
    .expect("error while running app");
}

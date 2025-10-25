#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{
    io::{BufRead, BufReader},
    env,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::Duration,
};
use tauri::{Manager, Emitter, PhysicalPosition};
use tauri_plugin_positioner::{WindowExt, Position};

const MUST_HAVE_MODULES: &[&str] = &[
    "fastapi",
    "uvicorn",
    "pydantic",
];

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

fn deps_missing(python_path: &Path) -> bool {
    for m in MUST_HAVE_MODULES {
        let ok = Command::new(python_path)
            .args(["-c", &format!("import {}", m)])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !ok {
            eprintln!("Missing Python module: {}", m);
            return true;
        }
    }
    false
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

fn center_window(window_ref: &tauri::WebviewWindow, app: &&mut tauri::App) {
    let win = window_ref.as_ref().window();

    // 1) Get the desktop cursor position
    if let Ok(cursor) = app.handle().cursor_position() {
      // 2) Find which monitor that point belongs to
      if let Ok(Some(mon)) = app.handle().monitor_from_point(cursor.x as f64, cursor.y as f64) {
        let mon_pos = mon.position();            // PhysicalPosition<i32>
        let mon_size = mon.size();               // PhysicalSize<u32>
        if let Ok(win_size) = win.outer_size() { // PhysicalSize<u32>
          // 3) Compute centered top-left on that monitor
          let x = mon_pos.x + (mon_size.width as i32  - win_size.width as i32)  / 2;
          let y = mon_pos.y + (mon_size.height as i32 - win_size.height as i32) / 2;
          let _ = win.set_position(PhysicalPosition::new(x, y));
        }
      } else {
        // Fallback: center on current monitor
        let _ = win.move_window(Position::Center);
      }
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(desktop)]
            let _ = app.handle().plugin(tauri_plugin_positioner::init());
            let splashscreen_window = app.get_webview_window("splashscreen").unwrap();
            center_window(&splashscreen_window, &app);
            splashscreen_window.show().expect("Failed to load splashscreen");

            let main_window = app.get_webview_window("main").unwrap();
            center_window(&main_window, &app);

            let splash_thread_1 = splashscreen_window.clone();
            let splash_thread_2 = splashscreen_window.clone();

            let loaded = Arc::new(AtomicBool::new(false));
            let loaded_flag = loaded.clone();
            let loaded_thread_1 = loaded.clone();
            let loaded_thread_2 = loaded.clone();

            let cwd = env::current_dir().expect("Couldn't get current dir");
            let project_root = cwd.parent().expect("Couldn't get project root");

            let python = resolve_python_path(project_root);
            if deps_missing(&python) {
                if let Err(e) = install_requirements(&python, project_root) {
                    eprintln!("Dependency installation error: {e}");
                }
            }

            let api_path = project_root.join("../api_server.py").canonicalize()
                .expect("Could not resolve api_server.py path");

            let mut child = Command::new(python)
                .args([api_path.to_str().unwrap(), "--port", "8000"])
                .current_dir(project_root.join(".."))
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .expect("Failed to start Suhana backend");

            let stdout = child.stdout.take().expect("no stdout");
            let stderr = child.stderr.take().expect("no stderr");

            // Read both stdout and stderr
            let out_reader = BufReader::new(stdout);
            let err_reader = BufReader::new(stderr);

            thread::spawn(move || {
                for line in out_reader.lines().flatten() {
                    if !loaded_thread_1.load(Ordering::Relaxed) {
                        splash_thread_1.emit("backend-log", line).ok();
                    } else {
                        println!("{}", line);
                    }
                }
            });

            thread::spawn(move || {
                for line in err_reader.lines().flatten() {
                    if !loaded_thread_2.load(Ordering::Relaxed) {
                        splash_thread_2.emit("backend-log", line).ok();
                    } else {
                        eprintln!("{}", line);
                    }
                }
            });


            thread::spawn(move || {
                if wait_for_api_ready() {
                    println!("Backend ready");
                } else {
                    eprintln!("Backend not responding in time");
                }
                loaded_flag.store(true, Ordering::Relaxed);

                splashscreen_window.close().unwrap();
                main_window.show().unwrap();
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri app");
}

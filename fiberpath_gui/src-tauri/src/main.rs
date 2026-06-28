#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api_path;
mod api_sidecar;
mod cli_path;
mod cli_process;

use serde_json::Value;
use std::fs;
use std::process::Output;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager};
use thiserror::Error;

#[derive(Debug, Error)]
enum FiberpathError {
    #[error("fiberpath exited with an error: {0}")]
    Process(String),
    #[error("Unable to parse JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("File error: {0}")]
    File(String),
}

#[tauri::command]
async fn stream_program(
    app: AppHandle,
    gcode_path: String,
    port: Option<String>,
    baud_rate: u32,
    dry_run: bool,
) -> Result<Value, String> {
    let mut args = vec![
        "stream".into(),
        gcode_path,
        "--baud-rate".into(),
        baud_rate.to_string(),
        "--json".into(),
    ];
    if dry_run {
        args.push("--dry-run".into());
    } else if let Some(port_value) = port {
        args.push("--port".into());
        args.push(port_value);
    }
    let output = exec_fiberpath(app, args)
        .await
        .map_err(|err| err.to_string())?;
    parse_json_payload(output)
}

async fn exec_fiberpath(app: AppHandle, args: Vec<String>) -> Result<Output, FiberpathError> {
    // Get the fiberpath CLI executable path (bundled or system)
    let cli_path = cli_path::get_fiberpath_executable(&app).map_err(FiberpathError::Process)?;

    let cli_str = cli_path::path_to_string(&cli_path).map_err(FiberpathError::Process)?;

    let joined = args.join(" ");
    let output = tauri::async_runtime::spawn_blocking(move || {
        cli_process::command_for_cli(cli_str).args(args).output()
    })
    .await
    .map_err(|err| FiberpathError::Process(format!("Failed to run fiberpath: {err}")))?
    .map_err(|err| {
        let message = format!("{err}");
        FiberpathError::Process(format!("{message} while running `{joined}`"))
    })?;

    // Check if command succeeded
    if !output.status.success() {
        return Err(FiberpathError::Process(format_cli_error(&output)));
    }

    Ok(output)
}

fn parse_json_payload(output: Output) -> Result<Value, String> {
    if !output.status.success() {
        return Err(format_cli_error(&output));
    }
    serde_json::from_slice::<Value>(&output.stdout)
        .map_err(|err| FiberpathError::Json(err).to_string())
}

fn format_cli_error(output: &Output) -> String {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    format!(
        "fiberpath exited with status {:?}\nstdout:\n{}\nstderr:\n{}",
        output.status.code(),
        stdout.trim(),
        stderr.trim()
    )
}

#[tauri::command]
async fn save_wind_file(path: String, content: String) -> Result<(), String> {
    fs::write(&path, content).map_err(|err| {
        FiberpathError::File(format!("Failed to write .wind file: {err}")).to_string()
    })
}

#[tauri::command]
async fn load_wind_file(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|err| {
        FiberpathError::File(format!("Failed to read .wind file: {err}")).to_string()
    })
}

#[tauri::command]
async fn get_cli_diagnostics(app: AppHandle) -> Result<Value, String> {
    use serde_json::json;

    // Get resource directory
    let resource_dir = app
        .path()
        .resource_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|e| format!("Error: {}", e));

    // Try to get bundled path
    let bundled_path_result = cli_path::get_bundled_cli_path(&app);
    let bundled_path = bundled_path_result
        .as_ref()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|e| format!("Error: {}", e));

    let bundled_exists = bundled_path_result
        .as_ref()
        .map(|p| p.exists())
        .unwrap_or(false);

    let bundled_is_file = bundled_path_result
        .as_ref()
        .map(|p| p.is_file())
        .unwrap_or(false);

    // Check system PATH
    let system_path = which::which("fiberpath")
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "Not found".to_string());

    // Get actual CLI path used
    let actual_cli_result = cli_path::get_fiberpath_executable(&app);
    let actual_cli = actual_cli_result
        .as_ref()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|e| format!("Error: {}", e));

    // Try to execute the CLI
    let mut execution_result = "Not tested".to_string();
    let mut execution_exit_code: Option<i32> = None;

    if let Ok(cli_path) = actual_cli_result {
        match cli_process::command_for_cli(&cli_path)
            .arg("--help")
            .output()
        {
            Ok(output) => {
                execution_exit_code = output.status.code();
                if output.status.success() {
                    execution_result = "Success".to_string();
                } else {
                    execution_result = format!("Failed with exit code {:?}", output.status.code());
                }
            }
            Err(e) => {
                execution_result = format!("Error executing: {}", e);
            }
        }
    }

    Ok(json!({
        "resourceDir": resource_dir,
        "bundledPath": bundled_path,
        "bundledExists": bundled_exists,
        "bundledIsFile": bundled_is_file,
        "systemPath": system_path,
        "actualCliUsed": actual_cli,
        "platform": std::env::consts::OS,
        "executionResult": execution_result,
        "executionExitCode": execution_exit_code,
    }))
}

#[derive(serde::Serialize)]
struct BackendHealthResponse {
    healthy: bool,
    version: Option<String>,
    #[serde(rename = "errorMessage")]
    error_message: Option<String>,
}

#[tauri::command]
async fn check_backend_health(app: AppHandle) -> Result<BackendHealthResponse, String> {
    // Get the fiberpath CLI executable path (bundled or system)
    let cli_path = match cli_path::get_fiberpath_executable(&app) {
        Ok(path) => path,
        Err(err) => {
            return Ok(BackendHealthResponse {
                healthy: false,
                version: None,
                error_message: Some(err),
            });
        }
    };

    let cli_str = match cli_path::path_to_string(&cli_path) {
        Ok(s) => s,
        Err(err) => {
            return Ok(BackendHealthResponse {
                healthy: false,
                version: None,
                error_message: Some(err),
            });
        }
    };

    // Try to run `fiberpath --help` to check if CLI is available
    let output = tauri::async_runtime::spawn_blocking(move || {
        cli_process::command_for_cli(cli_str).arg("--help").output()
    })
    .await
    .map_err(|err| format!("Failed to spawn health check: {err}"))?;

    match output {
        Ok(out) if out.status.success() => {
            // CLI is available, try to extract version from help text
            let help_text = String::from_utf8_lossy(&out.stdout);

            // Try to find version in help text (format: "fiberpath, version X.Y.Z" or similar)
            let version = help_text
                .lines()
                .find(|line| line.contains("version") || line.contains("Version"))
                .map(|line| {
                    // Extract version number if found
                    line.split_whitespace()
                        .find(|word| word.chars().next().is_some_and(|c| c.is_ascii_digit()))
                        .unwrap_or("unknown")
                        .to_string()
                })
                .or_else(|| Some("available".to_string()));

            Ok(BackendHealthResponse {
                healthy: true,
                version,
                error_message: None,
            })
        }
        Ok(out) => {
            let stderr = String::from_utf8_lossy(&out.stderr);
            Ok(BackendHealthResponse {
                healthy: false,
                version: None,
                error_message: Some(format!("Backend returned error: {}", stderr.trim())),
            })
        }
        Err(err) => Ok(BackendHealthResponse {
            healthy: false,
            version: None,
            error_message: Some(format!("Backend not found or not executable: {err}")),
        }),
    }
}

fn main() {
    let api_sidecar_state: api_sidecar::ApiSidecarState = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(api_sidecar_state)
        .setup(|app| {
            // Warm the sidecar in the background so the first frontend call is
            // fast. Failures (e.g. dev without a bundled binary) are non-fatal:
            // api_base_url spawns lazily on demand.
            let handle = app.handle().clone();
            let state = app.state::<api_sidecar::ApiSidecarState>().inner().clone();
            std::thread::spawn(move || {
                if let Err(e) = api_sidecar::base_url(&state, &handle) {
                    log::warn!("API sidecar eager start failed (retries on demand): {}", e);
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            stream_program,
            save_wind_file,
            load_wind_file,
            check_backend_health,
            get_cli_diagnostics,
            api_sidecar::api_base_url,
        ])
        .run(tauri::generate_context!())
        .expect("error while running FiberPath GUI");
}

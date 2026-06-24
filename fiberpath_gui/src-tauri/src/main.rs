#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod cli_path;
mod cli_process;
mod marlin;

use base64::{engine::general_purpose::STANDARD as Base64, Engine};
use marlin::MarlinState;
use serde_json::Value;
use std::fs;
use std::process::Output;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
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
async fn plan_wind(
    app: AppHandle,
    input_path: String,
    output_path: Option<String>,
) -> Result<Value, String> {
    let output_file = output_path.unwrap_or_else(|| temp_path("gcode"));
    let args = vec![
        "plan".to_string(),
        input_path,
        "--output".into(),
        output_file.clone(),
        "--json".into(),
    ];

    let output = exec_fiberpath(app, args)
        .await
        .map_err(|err| err.to_string())?;
    parse_json_payload(output).map(|mut payload| {
        if let Value::Object(ref mut obj) = payload {
            obj.entry("output".to_string())
                .or_insert(Value::String(output_file));
        }
        payload
    })
}

#[tauri::command]
async fn simulate_program(app: AppHandle, gcode_path: String) -> Result<Value, String> {
    let args = vec!["simulate".into(), gcode_path, "--json".into()];
    let output = exec_fiberpath(app, args)
        .await
        .map_err(|err| err.to_string())?;
    parse_json_payload(output)
}

#[derive(serde::Serialize)]
struct PlotPreview {
    path: String,
    #[serde(rename = "imageBase64")]
    image_base64: String,
    warnings: Vec<String>,
}

#[tauri::command]
async fn plot_preview(
    app: AppHandle,
    gcode_path: String,
    scale: f64,
    output_path: Option<String>,
) -> Result<PlotPreview, String> {
    // Keep a caller-supplied output path; auto-clean an internally generated temp PNG.
    let (output_file, _output_temp) = match output_path {
        Some(path) => (path, None),
        None => {
            let temp = TempFile::new("png");
            (temp.path().to_string(), Some(temp))
        }
    };
    let args = vec![
        "plot".into(),
        gcode_path,
        "--output".into(),
        output_file.clone(),
        "--scale".into(),
        scale.to_string(),
    ];
    exec_fiberpath(app, args)
        .await
        .map_err(|err| err.to_string())?;
    let bytes =
        fs::read(&output_file).map_err(|err| FiberpathError::File(err.to_string()).to_string())?;
    Ok(PlotPreview {
        path: output_file,
        image_base64: Base64.encode(bytes),
        warnings: vec![], // plot command doesn't generate warnings like plan does
    })
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

#[tauri::command]
async fn plot_definition(
    app: AppHandle,
    definition_json: String,
    _visible_layer_count: usize,
    output_path: Option<String>,
) -> Result<PlotPreview, String> {
    let mut warnings = Vec::new();

    // Create temporary .wind file (auto-cleaned on drop, including error paths)
    let wind_file = TempFile::new("wind");
    fs::write(wind_file.path(), &definition_json).map_err(|err| {
        FiberpathError::File(format!("Failed to write temp .wind file: {err}")).to_string()
    })?;

    // Create temporary .gcode file
    let gcode_file = TempFile::new("gcode");

    // First, run plan to convert .wind to .gcode
    let plan_args = vec![
        "plan".into(),
        wind_file.path().to_string(),
        "--output".into(),
        gcode_file.path().to_string(),
    ];
    let plan_output = exec_fiberpath(app.clone(), plan_args)
        .await
        .map_err(|err| format!("Planning failed: {err}"))?;

    // Capture stderr warnings from planner
    let stderr = String::from_utf8_lossy(&plan_output.stderr);
    if !stderr.is_empty() {
        for line in stderr.lines() {
            if !line.trim().is_empty() {
                warnings.push(line.trim().to_string());
            }
        }
    }

    // Generate output path for PNG. When the caller supplies an output_path it
    // is a user-chosen destination and must be kept; only an internally
    // generated temp PNG is wrapped in a cleanup guard.
    let (output_file, _output_temp) = match output_path {
        Some(path) => (path, None),
        None => {
            let temp = TempFile::new("png");
            (temp.path().to_string(), Some(temp))
        }
    };

    // Build plot command args with scale for better visibility
    let args = vec![
        "plot".into(),
        gcode_file.path().to_string(),
        "--output".into(),
        output_file.clone(),
        "--scale".into(),
        "0.5".into(), // Scale down for overview
    ];

    // Execute plot command
    exec_fiberpath(app, args)
        .await
        .map_err(|err| format!("Plotting failed: {err}"))?;

    // Read and encode image. The temp files are deleted when their guards drop
    // at the end of this function (success or any earlier `?` return).
    let bytes = fs::read(&output_file).map_err(|err| {
        FiberpathError::File(format!("Failed to read plot output: {err}")).to_string()
    })?;

    Ok(PlotPreview {
        path: output_file,
        image_base64: Base64.encode(&bytes),
        warnings,
    })
}

fn temp_path(extension: &str) -> String {
    let mut path = std::env::temp_dir();
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    path.push(format!("fiberpath-{millis}.{extension}"));
    path.to_string_lossy().into_owned()
}

/// RAII guard for a throwaway temp file.
///
/// Deletes the file when dropped, which covers the success path *and* every
/// early `?` return. It holds only the path (no open file handle), so the CLI
/// subprocess can freely create and overwrite the file — avoiding the Windows
/// sharing violations that an open-handle approach (e.g. `NamedTempFile`) would
/// cause when the subprocess writes the same path.
struct TempFile {
    path: String,
}

impl TempFile {
    fn new(extension: &str) -> Self {
        Self {
            path: temp_path(extension),
        }
    }

    fn path(&self) -> &str {
        &self.path
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
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

#[tauri::command]
async fn validate_wind_definition(
    app: AppHandle,
    definition_json: String,
) -> Result<Value, String> {
    // Create temporary .wind file (auto-cleaned on drop, including error paths)
    let wind_file = TempFile::new("wind");
    fs::write(wind_file.path(), &definition_json).map_err(|err| {
        FiberpathError::File(format!("Failed to write temp .wind file: {err}")).to_string()
    })?;

    // Run validate command
    let args = vec![
        "validate".into(),
        wind_file.path().to_string(),
        "--json".into(),
    ];
    let output = exec_fiberpath(app, args)
        .await
        .map_err(|err| err.to_string())?;

    parse_json_payload(output)
}

#[derive(serde::Serialize)]
struct CliHealthResponse {
    healthy: bool,
    version: Option<String>,
    #[serde(rename = "errorMessage")]
    error_message: Option<String>,
}

#[tauri::command]
async fn check_cli_health(app: AppHandle) -> Result<CliHealthResponse, String> {
    // Get the fiberpath CLI executable path (bundled or system)
    let cli_path = match cli_path::get_fiberpath_executable(&app) {
        Ok(path) => path,
        Err(err) => {
            return Ok(CliHealthResponse {
                healthy: false,
                version: None,
                error_message: Some(err),
            });
        }
    };

    let cli_str = match cli_path::path_to_string(&cli_path) {
        Ok(s) => s,
        Err(err) => {
            return Ok(CliHealthResponse {
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

            Ok(CliHealthResponse {
                healthy: true,
                version,
                error_message: None,
            })
        }
        Ok(out) => {
            let stderr = String::from_utf8_lossy(&out.stderr);
            Ok(CliHealthResponse {
                healthy: false,
                version: None,
                error_message: Some(format!("CLI returned error: {}", stderr.trim())),
            })
        }
        Err(err) => Ok(CliHealthResponse {
            healthy: false,
            version: None,
            error_message: Some(format!("CLI not found or not executable: {err}")),
        }),
    }
}

fn main() {
    let marlin_state: MarlinState = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(marlin_state)
        .invoke_handler(tauri::generate_handler![
            plan_wind,
            simulate_program,
            plot_preview,
            plot_definition,
            stream_program,
            save_wind_file,
            load_wind_file,
            validate_wind_definition,
            check_cli_health,
            get_cli_diagnostics,
            marlin::marlin_list_ports,
            marlin::marlin_start_interactive,
            marlin::marlin_connect,
            marlin::marlin_disconnect,
            marlin::marlin_send_command,
            marlin::marlin_stream_file,
            marlin::marlin_pause,
            marlin::marlin_resume,
            marlin::marlin_stop,
            marlin::marlin_cancel,
        ])
        .run(tauri::generate_context!())
        .expect("error while running FiberPath GUI");
}

#[cfg(test)]
mod tests {
    use super::TempFile;
    use std::fs;
    use std::path::Path;

    #[test]
    fn temp_file_is_removed_on_drop() {
        let path = {
            let temp = TempFile::new("test");
            fs::write(temp.path(), b"data").expect("write temp file");
            assert!(Path::new(temp.path()).exists());
            temp.path().to_string()
        };
        assert!(
            !Path::new(&path).exists(),
            "temp file should be deleted on drop"
        );
    }

    #[test]
    fn temp_file_drop_is_safe_when_file_missing() {
        // Dropping a guard whose file was never created (or already removed)
        // must not panic.
        let temp = TempFile::new("test");
        assert!(!Path::new(temp.path()).exists());
        drop(temp);
    }
}

//! Supervise the local FastAPI sidecar process.
//!
//! The sidecar (`fiberpath-api`) binds an ephemeral 127.0.0.1 port and prints a
//! one-line JSON handshake (`{"event":"listening","host","port"}`) to stdout. We
//! spawn it, read that handshake to learn the base URL, drain its pipes, and
//! reap it on Drop. A dead sidecar is respawned on demand. HTTP readiness
//! (`GET /health`) is polled by the frontend.

use std::io::{BufRead, BufReader};
use std::process::{Child, Stdio};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use tauri::AppHandle;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum SidecarError {
    #[error("failed to start the API sidecar: {0}")]
    SpawnFailed(String),
    #[error("the API sidecar exited before reporting a port")]
    NoHandshake,
}

#[derive(serde::Deserialize)]
struct Handshake {
    port: u16,
}

/// A spawned, supervised API sidecar.
pub struct ApiSidecar {
    base_url: String,
    child: Child,
    _stdout_thread: JoinHandle<()>,
    _stderr_thread: JoinHandle<()>,
}

/// Non-blocking liveness check: `try_wait` returns `Ok(None)` while running.
/// Treat "exited" and "can't tell" alike so the caller respawns.
fn child_has_exited(child: &mut Child) -> bool {
    matches!(child.try_wait(), Ok(Some(_)) | Err(_))
}

impl ApiSidecar {
    pub fn spawn(app: &AppHandle) -> Result<Self, SidecarError> {
        let exe =
            crate::api_path::get_api_sidecar_executable(app).map_err(SidecarError::SpawnFailed)?;
        let exe_str = crate::cli_path::path_to_string(&exe).map_err(SidecarError::SpawnFailed)?;

        let mut child = crate::cli_process::command_for_cli(exe_str)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| SidecarError::SpawnFailed(e.to_string()))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| SidecarError::SpawnFailed("failed to capture stdout".to_string()))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| SidecarError::SpawnFailed("failed to capture stderr".to_string()))?;

        // The first stdout line is the JSON port handshake.
        // minimal: this read has no timeout; a broken binary exits -> EOF -> NoHandshake.
        let mut reader = BufReader::new(stdout);
        let base_url = loop {
            let mut line = String::new();
            if reader
                .read_line(&mut line)
                .map_err(|e| SidecarError::SpawnFailed(e.to_string()))?
                == 0
            {
                return Err(SidecarError::NoHandshake);
            }
            if let Ok(handshake) = serde_json::from_str::<Handshake>(line.trim()) {
                break format!("http://127.0.0.1:{}", handshake.port);
            }
        };

        // Drain the rest of stdout so a full pipe never blocks the child.
        let stdout_thread = std::thread::spawn(move || {
            for line in reader.lines() {
                if line.is_err() {
                    break;
                }
            }
        });
        // Surface the sidecar's stderr (uvicorn logs) for diagnostics.
        let stderr_thread = std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                match line {
                    Ok(line) => log::debug!("[api-sidecar] {}", line),
                    Err(_) => break,
                }
            }
        });

        log::info!("API sidecar started at {}", base_url);
        Ok(Self {
            base_url,
            child,
            _stdout_thread: stdout_thread,
            _stderr_thread: stderr_thread,
        })
    }

    fn is_dead(&mut self) -> bool {
        child_has_exited(&mut self.child)
    }
}

impl Drop for ApiSidecar {
    fn drop(&mut self) {
        // Kill and reap so the sidecar never lingers as an orphan holding its
        // port after the app closes or a dead instance is replaced.
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub type ApiSidecarState = Arc<Mutex<Option<ApiSidecar>>>;

/// Return the sidecar base URL, spawning a fresh sidecar if none is running or
/// the previous one has died.
pub fn base_url(state: &ApiSidecarState, app: &AppHandle) -> Result<String, String> {
    let mut guard = state.lock().map_err(|e| e.to_string())?;
    if guard.as_mut().is_some_and(ApiSidecar::is_dead) {
        *guard = None;
    }
    if guard.is_none() {
        *guard = Some(ApiSidecar::spawn(app).map_err(|e| e.to_string())?);
    }
    Ok(guard.as_ref().unwrap().base_url.clone())
}

/// Frontend entry point: the base URL of the running API sidecar.
#[tauri::command]
pub fn api_base_url(
    app: AppHandle,
    state: tauri::State<'_, ApiSidecarState>,
) -> Result<String, String> {
    base_url(&state, &app)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn handshake_extracts_port_and_ignores_extra_fields() {
        let line = r#"{"event":"listening","host":"127.0.0.1","port":54321}"#;
        let handshake: Handshake = serde_json::from_str(line).expect("valid handshake");
        assert_eq!(handshake.port, 54321);
    }

    #[test]
    fn non_handshake_line_is_rejected() {
        assert!(serde_json::from_str::<Handshake>("INFO: uvicorn running").is_err());
    }
}

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter};
use thiserror::Error;
use tokio::sync::oneshot;

#[derive(Debug, Error)]
pub enum MarlinError {
    #[error("Failed to spawn subprocess: {0}")]
    SpawnFailed(String),
    #[error("Failed to send command: {0}")]
    SendFailed(String),
    #[error("Response channel closed")]
    ChannelClosed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerialPort {
    pub port: String,
    pub description: String,
    pub hwid: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "status")]
pub enum MarlinResponse {
    #[serde(rename = "ok")]
    Ok {
        #[serde(skip_serializing_if = "Option::is_none")]
        ports: Option<Vec<SerialPort>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        command: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        responses: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "connected")]
    Connected {
        port: String,
        #[serde(rename = "baudRate")]
        baud_rate: u32,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "disconnected")]
    Disconnected {
        #[serde(skip_serializing_if = "Option::is_none")]
        message: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "streaming")]
    Streaming {
        file: String,
        #[serde(rename = "totalCommands")]
        total_commands: usize,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "progress")]
    Progress {
        #[serde(rename = "commandsSent")]
        commands_sent: usize,
        #[serde(rename = "commandsTotal")]
        commands_total: usize,
        command: String,
        #[serde(rename = "dryRun")]
        dry_run: bool,
    },
    #[serde(rename = "complete")]
    Complete {
        #[serde(rename = "commandsSent")]
        commands_sent: usize,
        #[serde(rename = "commandsTotal")]
        commands_total: usize,
    },
    #[serde(rename = "paused")]
    Paused {
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "resumed")]
    Resumed {
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "stopped")]
    Stopped {
        #[serde(default)]
        disconnected: bool,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "cancelled")]
    Cancelled {
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "exiting")]
    Exiting {
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
    #[serde(rename = "error")]
    Error {
        code: String,
        message: String,
        #[serde(skip_serializing_if = "Option::is_none", rename = "requestId")]
        request_id: Option<u64>,
    },
}

impl MarlinResponse {
    /// Extract request ID from response for routing
    pub fn request_id(&self) -> Option<u64> {
        match self {
            MarlinResponse::Ok { request_id, .. } => *request_id,
            MarlinResponse::Connected { request_id, .. } => *request_id,
            MarlinResponse::Disconnected { request_id, .. } => *request_id,
            MarlinResponse::Streaming { request_id, .. } => *request_id,
            MarlinResponse::Progress { .. } => None,
            MarlinResponse::Complete { .. } => None,
            MarlinResponse::Paused { request_id } => *request_id,
            MarlinResponse::Resumed { request_id } => *request_id,
            MarlinResponse::Stopped { request_id, .. } => *request_id,
            MarlinResponse::Cancelled { request_id } => *request_id,
            MarlinResponse::Exiting { request_id } => *request_id,
            MarlinResponse::Error { request_id, .. } => *request_id,
        }
    }
}

/// Handles request-response correlation with single reader pattern
///
/// Architecture:
/// - ONE thread reads ALL responses from stdout
/// - Responses with requestId are routed to waiting handlers
/// - Responses without requestId are emitted as events (progress, complete)
/// - No race conditions - single reader owns the stream
#[derive(Clone)]
struct ResponseRouter {
    next_request_id: Arc<AtomicU64>,
    pending_responses: Arc<Mutex<HashMap<u64, oneshot::Sender<MarlinResponse>>>>,
}

impl ResponseRouter {
    fn new() -> Self {
        Self {
            next_request_id: Arc::new(AtomicU64::new(1)),
            pending_responses: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Start the response reader thread
    fn spawn_reader(&self, stdout: ChildStdout, app: AppHandle) -> std::thread::JoinHandle<()> {
        let pending_responses = self.pending_responses.clone();

        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                let line = match line {
                    Ok(l) => l,
                    Err(e) => {
                        eprintln!("[ERROR] Failed to read stdout: {}", e);
                        break;
                    }
                };

                let response: MarlinResponse = match serde_json::from_str(&line) {
                    Ok(r) => r,
                    Err(e) => {
                        eprintln!("[ERROR] Invalid JSON from Python: {}: {}", e, line);
                        continue;
                    }
                };

                // Route by request ID if present
                if let Some(req_id) = response.request_id() {
                    let sender = pending_responses.lock().unwrap().remove(&req_id);
                    if let Some(sender) = sender {
                        let _ = sender.send(response);
                    } else {
                        eprintln!("[WARNING] No handler waiting for request ID {}", req_id);
                    }
                } else {
                    // Broadcast event (no request ID) - emit to frontend
                    match &response {
                        MarlinResponse::Progress { .. } => {
                            let _ = app.emit("stream-progress", &response);
                        }
                        MarlinResponse::Complete { .. } => {
                            let _ = app.emit("stream-complete", &response);
                        }
                        MarlinResponse::Error { .. } => {
                            let _ = app.emit("stream-error", &response);
                        }
                        other => {
                            eprintln!("[WARNING] Unexpected broadcast response: {:?}", other);
                        }
                    }
                }
            }
        })
    }

    /// Send command and wait for response with correlation
    async fn send_and_wait(
        &self,
        stdin: &Arc<Mutex<ChildStdin>>,
        command: serde_json::Value,
    ) -> Result<MarlinResponse, MarlinError> {
        let request_id = self.next_request_id.fetch_add(1, Ordering::SeqCst);

        let (tx, rx): (
            oneshot::Sender<MarlinResponse>,
            oneshot::Receiver<MarlinResponse>,
        ) = oneshot::channel();

        self.pending_responses
            .lock()
            .unwrap()
            .insert(request_id, tx);

        let mut command_with_id = command;
        if let Some(obj) = command_with_id.as_object_mut() {
            obj.insert("requestId".to_string(), serde_json::json!(request_id));
        }

        let json_str = serde_json::to_string(&command_with_id)
            .map_err(|e| MarlinError::SendFailed(format!("Failed to serialize command: {}", e)))?;

        {
            let mut stdin = stdin.lock().unwrap();
            writeln!(stdin, "{}", json_str).map_err(|e| MarlinError::SendFailed(e.to_string()))?;
            stdin
                .flush()
                .map_err(|e| MarlinError::SendFailed(e.to_string()))?;
        }

        rx.await.map_err(|_| MarlinError::ChannelClosed)
    }
}

pub struct MarlinSubprocess {
    stdin: Arc<Mutex<ChildStdin>>,
    response_router: ResponseRouter,
    _child: Child,
    _stderr_thread: std::thread::JoinHandle<()>,
    _reader_thread: std::thread::JoinHandle<()>,
}

impl MarlinSubprocess {
    pub fn spawn(app: AppHandle) -> Result<Self, MarlinError> {
        // Get the fiberpath CLI executable path (bundled or system)
        let cli_path = crate::cli_path::get_fiberpath_executable(&app)
            .map_err(|err| MarlinError::SpawnFailed(format!("Failed to find CLI: {}", err)))?;

        let cli_str = crate::cli_path::path_to_string(&cli_path)
            .map_err(|err| MarlinError::SpawnFailed(format!("Failed to convert path: {}", err)))?;

        let mut child = crate::cli_process::command_for_cli(cli_str)
            .arg("interactive")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| MarlinError::SpawnFailed(e.to_string()))?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| MarlinError::SpawnFailed("Failed to capture stdin".to_string()))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| MarlinError::SpawnFailed("Failed to capture stdout".to_string()))?;

        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| MarlinError::SpawnFailed("Failed to capture stderr".to_string()))?;

        let stderr_thread = std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                match line {
                    Ok(line) => eprintln!("{}", line),
                    Err(_) => break,
                }
            }
        });

        let response_router = ResponseRouter::new();
        let reader_thread = response_router.spawn_reader(stdout, app);

        Ok(Self {
            stdin: Arc::new(Mutex::new(stdin)),
            response_router,
            _child: child,
            _stderr_thread: stderr_thread,
            _reader_thread: reader_thread,
        })
    }
}

pub type MarlinState = Arc<Mutex<Option<MarlinSubprocess>>>;

/// Acquire `(stdin, response_router)` clones from the shared Marlin state.
///
/// Passing `Some(app)` spawns the interactive subprocess if it is not yet
/// running; passing `None` fails with "Not connected" when nothing is running.
fn acquire_io(
    state: &MarlinState,
    app: Option<AppHandle>,
) -> Result<(Arc<Mutex<ChildStdin>>, ResponseRouter), String> {
    let mut guard = state.lock().map_err(|e| e.to_string())?;
    if guard.is_none() {
        let app = app.ok_or("Not connected")?;
        *guard = Some(MarlinSubprocess::spawn(app).map_err(|e| e.to_string())?);
    }
    let subprocess = guard.as_ref().unwrap();
    Ok((subprocess.stdin.clone(), subprocess.response_router.clone()))
}

// Tauri commands

#[tauri::command]
pub async fn marlin_list_ports(
    app: AppHandle,
    state: tauri::State<'_, MarlinState>,
) -> Result<Vec<SerialPort>, String> {
    let (stdin, response_router) = acquire_io(state.inner(), Some(app))?;

    let command = serde_json::json!({
        "action": "list_ports"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Ok {
            ports: Some(ports), ..
        } => Ok(ports),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from list_ports: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_start_interactive(
    app: AppHandle,
    state: tauri::State<'_, MarlinState>,
) -> Result<(), String> {
    let mut marlin_state = state.lock().map_err(|e| e.to_string())?;
    if marlin_state.is_none() {
        *marlin_state = Some(MarlinSubprocess::spawn(app).map_err(|e| e.to_string())?);
    }
    Ok(())
}

#[tauri::command]
pub async fn marlin_connect(
    port: String,
    baud_rate: u32,
    app: AppHandle,
    state: tauri::State<'_, MarlinState>,
) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), Some(app))?;

    let command = serde_json::json!({
        "action": "connect",
        "port": port,
        "baudRate": baud_rate
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Connected { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from connect: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_disconnect(state: tauri::State<'_, MarlinState>) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "disconnect"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Disconnected { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from disconnect: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_send_command(
    gcode: String,
    state: tauri::State<'_, MarlinState>,
) -> Result<Vec<String>, String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "send",
        "gcode": gcode
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Ok {
            responses: Some(responses),
            ..
        } => Ok(responses),
        MarlinResponse::Ok {
            responses: None, ..
        } => Ok(vec![]),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_stream_file(
    file_path: String,
    state: tauri::State<'_, MarlinState>,
    app: AppHandle,
) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "stream",
        "file": file_path
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Streaming {
            file,
            total_commands,
            ..
        } => {
            // Emit stream-started event to frontend
            let _ = app.emit(
                "stream-started",
                serde_json::json!({
                    "file": file,
                    "totalCommands": total_commands
                }),
            );
            Ok(())
        }
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from stream_file: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_pause(state: tauri::State<'_, MarlinState>) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "pause"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Paused { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from pause: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_resume(state: tauri::State<'_, MarlinState>) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "resume"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Resumed { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from resume: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_stop(state: tauri::State<'_, MarlinState>) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "stop"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Stopped { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from stop: {:?}", other)),
    }
}

#[tauri::command]
pub async fn marlin_cancel(state: tauri::State<'_, MarlinState>) -> Result<(), String> {
    let (stdin, response_router) = acquire_io(state.inner(), None)?;

    let command = serde_json::json!({
        "action": "cancel"
    });

    let response = response_router
        .send_and_wait(&stdin, command)
        .await
        .map_err(|e| e.to_string())?;

    match response {
        MarlinResponse::Cancelled { .. } => Ok(()),
        MarlinResponse::Error { message, .. } => Err(message),
        other => Err(format!("Unexpected response from cancel: {:?}", other)),
    }
}

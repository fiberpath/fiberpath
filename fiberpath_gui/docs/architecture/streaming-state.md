# Streaming State Management

Architecture for real-time hardware control via Marlin firmware.

## Overview

The FiberPath GUI streaming system enables direct G-code execution on Marlin-compatible 3-axis winding machines via serial connection. The architecture uses a persistent Python subprocess with zero-lag progress reporting and refined state management.

## Architecture

```text
┌─────────────────────────────────────┐
│  Machine workspace (Svelte)         │  User interactions
│  - Connection UI                    │  - Play/Pause/Cancel buttons
│  - Manual control                   │  - File selection
│  - Progress display                 │  - Command log
│  state: machineSession (runes)      │
└──────────┬──────────────────────────┘
           │ invoke() + listen()
           ▼
┌─────────────────────────────────────┐
│  Tauri Event System                 │  Async pub/sub
│  - stream-progress                  │
│  - stream-complete                  │
│  - stream-error                     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  MarlinState (marlin.rs)            │  Rust state manager
│  - Child process                    │  - Request router
│  - stdin writer                     │  - stdout reader
│  - Response correlation             │
└──────────┬──────────────────────────┘
           │ subprocess
           ▼
┌─────────────────────────────────────┐
│  fiberpath stream CLI               │  Python subprocess
│  - JSON protocol                    │  - Serial I/O
│  - Marlin protocol handler          │  - Queue management
│  - Zero-lag progress                │
└──────────┬──────────────────────────┘
           │ serial port
           ▼
┌─────────────────────────────────────┐
│  Marlin Firmware                    │  Hardware controller
│  - G-code parser                    │
│  - Motion control                   │
│  - "ok" responses                   │
└─────────────────────────────────────┘
```

## Rust State Manager

### MarlinState Structure

```rust
pub struct MarlinState {
    process: Option<Child>,
    stdin: Option<ChildStdin>,
    router: ResponseRouter,
}
```

**Components:**

- `process`: Python subprocess handle
- `stdin`: Write channel for sending commands
- `router`: Routes responses to waiting handlers

### Response Router

```rust
struct ResponseRouter {
    next_request_id: Arc<AtomicU64>,
    pending_responses: Arc<Mutex<HashMap<u64, oneshot::Sender<MarlinResponse>>>>,
}
```

**Mechanism:**

- **Single Reader:** One thread reads all stdout
- **Request Correlation:** Commands get unique IDs, responses match back
- **Event Broadcasting:** Progress updates emitted to frontend
- **No Race Conditions:** Owned stdout reader prevents concurrent access

**Pattern:**

```rust
// Spawn reader thread on startup
fn spawn_reader(&self, stdout: ChildStdout, app: AppHandle) {
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let response: MarlinResponse = serde_json::from_str(&line)?;
            if let Some(req_id) = response.request_id() {
                // Route to waiting handler
                pending_responses.remove(&req_id).unwrap().send(response);
            } else {
                // Broadcast as event
                app.emit("stream-progress", &response);
            }
        }
    });
}
```

### Response Types

```rust
#[derive(Serialize, Deserialize)]
#[serde(tag = "status")]
pub enum MarlinResponse {
    Ok { ports: Option<Vec<SerialPort>>, ... },
    Connected { port: String, baud_rate: u32, ... },
    Disconnected { message: Option<String>, ... },
    Streaming { file: String, total_commands: usize, ... },
    Progress { commands_sent: usize, commands_total: usize, command: String, ... },
    Complete { commands_sent: usize, commands_total: usize },
    Paused { ... },
    Resumed { ... },
    Stopped { disconnected: bool, ... },
    Cancelled { ... },
    Error { code: String, message: String, ... },
}
```

**Discriminated Union:** `status` field determines variant (JSON tagged enum).

## Command Flow

### 1. Connection

**Frontend:**

```typescript
await invoke("marlin_connect", { port: "COM3", baudRate: 115200 });
```

**Rust:**

```rust
#[tauri::command]
async fn marlin_connect(
    state: tauri::State<'_, MarlinStateWrapper>,
    port: String,
    baud_rate: u32,
) -> Result<MarlinResponse, String> {
    let mut state = state.0.lock().await;
    state.connect(port, baud_rate).await
}
```

**Flow:**

1. Spawn Python subprocess: `fiberpath stream --json`
2. Start stdout reader thread
3. Send `{"command": "connect", "port": "COM3", "baudRate": 115200, "requestId": 1}`
4. Wait for `{"status": "connected", "requestId": 1, ...}`
5. Return to frontend

### 2. Manual Command

**Frontend:**

```typescript
await invoke("marlin_send_command", { command: "G28" });
```

**Rust:**

```rust
#[tauri::command]
async fn marlin_send_command(
    state: tauri::State<'_, MarlinStateWrapper>,
    command: String,
) -> Result<MarlinResponse, String> {
    let mut state = state.0.lock().await;
    state.send_command(command).await
}
```

**Flow:**

1. Write to stdin: `{"command": "send", "gcode": "G28", "requestId": 2}`
2. Wait for `{"status": "ok", "requestId": 2, "responses": ["ok"]}`
3. Return responses to frontend

### 3. File Streaming

**Frontend:**

```typescript
await invoke("marlin_stream_file", {
  filePath: "/path/to/output.gcode",
  dryRun: false,
});
// Listen for progress
const unlisten = await listen("stream-progress", (event) => {
  const { commandsSent, commandsTotal } = event.payload;
  console.log(`${commandsSent}/${commandsTotal}`);
});
```

**Rust:**

```rust
#[tauri::command]
async fn marlin_stream_file(
    state: tauri::State<'_, MarlinStateWrapper>,
    file_path: String,
    dry_run: bool,
) -> Result<MarlinResponse, String> {
    let mut state = state.0.lock().await;
    state.stream_file(file_path, dry_run).await
}
```

**Flow:**

1. Write to stdin: `{"command": "stream", "file": "output.gcode", "dryRun": false, "requestId": 3}`
2. Receive `{"status": "streaming", "file": "...", "totalCommands": 5000, "requestId": 3}`
3. **Zero-lag progress:** Reader thread emits progress events directly:
   - `{"status": "progress", "commandsSent": 100, "commandsTotal": 5000, ...}` (no requestId)
   - Frontend updates progress bar in real-time
4. On completion: `{"status": "complete", "commandsSent": 5000, "commandsTotal": 5000}`

### 4. Pause/Resume/Cancel

**Pause:**

```typescript
await invoke("marlin_pause");
```

```rust
state.send_request(MarlinRequest::Pause).await
```

Sends: `{"command": "pause", "requestId": 4}`

**Resume:**

```typescript
await invoke("marlin_resume");
```

Sends: `{"command": "resume", "requestId": 5}`

**Cancel (v0.5.0):**

```typescript
await invoke("marlin_cancel");
```

Sends: `{"command": "cancel", "requestId": 6}`

**Behavior:**

- **Stop:** Clears queue, disconnects from serial port
- **Cancel:** Clears queue, keeps connection alive (orange button when paused)

## Zero-Lag Progress (v0.5.0)

### Problem

Original architecture had progress lag:

```text
Frontend polls → Rust queries Python → Python responds → Rust returns → Frontend updates
```

Latency: ~200-500ms per update.

### Solution

Shared state polling in Python subprocess:

```python
# Python CLI (simplified)
class StreamingState:
    commands_sent: int
    commands_total: int
    current_command: str
# Streaming thread
while commands:
    send_command(commands[i])
    state.commands_sent = i + 1
    state.current_command = commands[i]
# Progress reporter thread (separate)
while streaming:
    emit_json({
        "status": "progress",
        "commandsSent": state.commands_sent,
        "commandsTotal": state.commands_total,
        "command": state.current_command,
    })
    sleep(0.1)  # 100ms update interval
```

**Result:** Progress updates arrive continuously without frontend polling.

## Frontend Integration

The frontend side is a single reactive class, `MachineSession`
(`src/state/machine-session.svelte.ts`), exported as the `machineSession`
singleton. It consolidates what was previously a Zustand stream store plus
several React action hooks and a `useStreamEvents` hook. It reuses the
framework-agnostic `marlin-api` (the Tauri bridge in `src/lib/marlin-api.ts`)
and `streamFeedback` (log/toast message builders) unchanged.

### Reactive state

```typescript
export class MachineSession {
  status = $state<ConnectionStatus>("disconnected"); // disconnected | connecting | connected | paused
  ports = $state<SerialPort[]>([]);
  selectedPort = $state<string | null>(null);
  baudRate = $state<number>(DEFAULT_BAUD_RATE);

  isStreaming = $state(false);
  filePath = $state<string | null>(null);
  progress = $state<StreamProgress | null>(null);

  log = $state<LogEntry[]>([]);

  readonly isConnected = $derived(this.status === "connected" || this.status === "paused");
  readonly isPaused = $derived(this.status === "paused");
  readonly canStartStream = $derived(Boolean(this.filePath) && this.isConnected);
}

export const machineSession = new MachineSession();
```

Components read these fields and call methods (`connect`, `startStream`,
`pause`, `resume`, `cancel`, `stop`); derived flags like `canStartStream` drive
button enablement without manual bookkeeping.

### Event subscription

Stream lifecycle events from Rust are subscribed once via `subscribe()`, which
wires the `marlin-api` listeners into reactive updates and returns a cleanup that
unlistens:

```typescript
async subscribe(): Promise<() => void> {
  const unlisten = await Promise.all([
    marlin.onStreamStarted((s) => {
      this.isStreaming = true;
    }),
    marlin.onStreamProgress((p) => {
      // Stale-event guard (#219): drop progress from a finished/cancelled job.
      if (!this.isStreaming) return;
      this.progress = { sent: p.commandsSent, total: p.commandsTotal, currentCommand: p.command };
    }),
    marlin.onStreamComplete(() => this.#resetAfterCancel()),
    marlin.onStreamError((e) => {
      this.#resetAfterCancel();
    }),
  ]);
  return () => unlisten.forEach((u) => u());
}
```

### Markup

The machine workspace components (`src/components/machine/*.svelte`) bind
straight to the singleton — no local mirror state:

```svelte
<script lang="ts">
  import { machineSession as m } from "../../state/machine-session.svelte";
</script>

{#if m.progress}
  <div class="progress__head">
    <span>Progress</span><span>{m.progress.sent} / {m.progress.total}</span>
  </div>
  <progress value={m.progress.sent} max={Math.max(m.progress.total, 1)}></progress>
{/if}

<button disabled={!m.canStartStream} onclick={() => m.startStream()}>Start</button>
{#if m.isStreaming && !m.isPaused}
  <button onclick={() => m.pause()}>Pause</button>
{:else if m.isPaused}
  <button onclick={() => m.resume()}>Resume</button>
  <button onclick={() => m.cancel()}>Cancel</button>
{/if}
```

## Error Handling

### Connection Errors

```rust
MarlinResponse::Error {
    code: "CONNECTION_FAILED",
    message: "Unable to open serial port: Access denied",
}
```

**Common Causes:**

- Port not found
- Port in use by another application
- Permissions (Linux: not in dialout group)

### Streaming Errors

```rust
MarlinResponse::Error {
    code: "STREAM_FAILED",
    message: "Marlin returned 'error' for command: G1 X1000000",
}
```

**Common Causes:**

- Invalid G-code
- Out-of-bounds movement
- Homing not performed

## v0.5.0 Enhancements

### Cancel Job

**Before (v4.0):** Only "Stop" button (emergency stop, disconnects).

**After (v0.5.0):**

- **Stop:** Emergency stop + disconnect (red button, always visible)
- **Cancel:** Graceful cancel + keep connection (orange button, only when paused)

**Use Cases:**

- **Cancel:** Realize mistake mid-job, stop gracefully, stay connected for manual recovery
- **Stop:** Emergency condition, disconnect immediately

### Application State Machine

**Refined State Handling:**

- Clean state after stop/cancel/reconnect
- Clear selected file anytime (manual file control)
- Prevent double-connections
- Handle disconnect during streaming

**State Machine:**

```text
Disconnected → Connect → Connected
Connected → Stream → Streaming
Streaming → Pause → Paused
Paused → Resume → Streaming
Paused → Cancel → Connected
Any → Stop → Disconnected
Any → Disconnect → Disconnected
```

## Testing

### Manual Testing Checklist

- [ ] Connect to serial port
- [ ] Send manual G-code (G28, G1 X10)
- [ ] Stream small file (<100 commands)
- [ ] Stream large file (1000+ commands)
- [ ] Pause mid-stream
- [ ] Resume after pause
- [ ] Cancel after pause (connection stays alive)
- [ ] Stop during streaming (disconnects)
- [ ] Disconnect and reconnect
- [ ] Handle connection failures gracefully

### Dry Run Mode

```typescript
await invoke("marlin_stream_file", { filePath, dryRun: true });
```

**Behavior:** Simulates streaming without serial connection. Useful for:

- Testing progress updates
- Validating G-code file
- UI testing without hardware

## Performance

### Update Frequency

- **Progress:** 10 Hz (every 100ms)
- **Command logging:** All commands (no throttling)

### Memory

- **Command queue:** Held in Python process memory
- **Log buffer:** Limited to last 1000 commands in frontend

### Latency

- **Command → Response:** ~10-50ms (serial + Marlin processing)
- **Progress → UI:** ~100ms (update interval)

## Troubleshooting

### No progress updates

**Check:** Ensure `stream-progress` listener is attached before starting stream.

### Progress lags behind

**Cause:** A listener attached to the wrong event, or progress mutating a value
nothing reads.

**Fix:** Confirm `subscribe()` ran and that the markup reads `machineSession.progress`.
Svelte's fine-grained reactivity updates only the affected nodes, so frequent
progress events do not re-render the whole panel.

### Commands not executing

**Check:** Marlin firmware homed? (`G28`)

### Connection timeout

**Increase:** Baud rate or check USB cable quality.

## Next Steps

- [CLI Integration](cli-integration.md) - How Rust bridges to Python
- [State Management](state-management.md) - runes state patterns
- [Marlin Streaming Guide](../../guides/marlin-streaming.md) - User documentation

use std::path::PathBuf;
use tauri::{AppHandle, Manager};

/// Resolve the bundled `fiberpath-api` sidecar executable, falling back to the
/// system PATH (for development where the package is pip-installed and exposes
/// the `fiberpath-api` console script). Mirrors `cli_path` for the CLI binary.
pub fn get_api_sidecar_executable(app: &AppHandle) -> Result<PathBuf, String> {
    match get_bundled_api_path(app) {
        Ok(bundled) => {
            if bundled.exists() && bundled.is_file() {
                return Ok(bundled);
            }
        }
        Err(e) => log::warn!("Failed to resolve bundled API sidecar path: {}", e),
    }

    if let Ok(system_path) = which::which("fiberpath-api") {
        return Ok(system_path);
    }

    Err(
        "FiberPath API sidecar not found. Ensure the application was installed correctly, \
         or install the Python package (which provides the `fiberpath-api` command)."
            .to_string(),
    )
}

fn get_bundled_api_path(app: &AppHandle) -> Result<PathBuf, String> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Failed to resolve resource directory: {}", e))?;

    // Resources from the `../bundled-api/*` glob land under a "_up_" subdirectory
    // on *every* platform (Tauri encodes the parent-dir `../`). Prefer that
    // layout; fall back to a flat `bundled-api/` (dev builds). Matches cli_path.
    let exe = if cfg!(target_os = "windows") {
        "fiberpath-api.exe"
    } else {
        "fiberpath-api"
    };
    let up_layout = resource_dir.join("_up_").join("bundled-api").join(exe);
    let path = if up_layout.exists() {
        up_layout
    } else {
        resource_dir.join("bundled-api").join(exe)
    };

    Ok(path)
}

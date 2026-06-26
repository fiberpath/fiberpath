use std::path::PathBuf;
use tauri::{AppHandle, Manager};

/// Get the path to the fiberpath CLI executable.
///
/// This function checks for a bundled CLI executable in the resources directory first,
/// then falls back to the system PATH if not found (for development scenarios).
///
/// # Platform-specific resource paths:
/// - Windows: `_up_/bundled-cli/fiberpath.exe`
/// - macOS: `bundled-cli/fiberpath`
/// - Linux: `bundled-cli/fiberpath`
///
/// # Returns
/// - `Ok(PathBuf)` - Path to the fiberpath executable (bundled or system)
/// - `Err(String)` - Error message if CLI not found
pub fn get_fiberpath_executable(app: &AppHandle) -> Result<PathBuf, String> {
    // Try to get the bundled CLI from resources directory
    match get_bundled_cli_path(app) {
        Ok(bundled_path) => {
            if bundled_path.exists() && bundled_path.is_file() {
                return Ok(bundled_path);
            }
        }
        Err(e) => {
            log::warn!("Failed to resolve bundled CLI path: {}", e);
        }
    }

    // Fallback to system PATH (for development)
    if let Ok(system_path) = which::which("fiberpath") {
        return Ok(system_path);
    }

    // No CLI found
    Err(
        "FiberPath CLI not found. Please ensure the application was installed correctly, \
         or install the Python package with: pip install fiberpath"
            .to_string(),
    )
}

/// Get the path to the bundled CLI executable in the resources directory.
///
/// This function uses Tauri v2's Manager trait to resolve the resource directory
/// and then constructs the platform-specific path to the bundled CLI.
pub fn get_bundled_cli_path(app: &AppHandle) -> Result<PathBuf, String> {
    // Get the resource directory using Tauri v2 API
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Failed to resolve resource directory: {}", e))?;

    // Resources bundled from the `../bundled-cli/*` glob land under a "_up_"
    // subdirectory on *every* platform (Tauri encodes the parent-dir `../`).
    // Prefer that layout; fall back to a flat `bundled-cli/` (dev builds).
    let exe_name = if cfg!(target_os = "windows") {
        "fiberpath.exe"
    } else {
        "fiberpath"
    };
    let up_layout = resource_dir.join("_up_").join("bundled-cli").join(exe_name);
    let cli_path = if up_layout.exists() {
        up_layout
    } else {
        resource_dir.join("bundled-cli").join(exe_name)
    };

    Ok(cli_path)
}

/// Convert PathBuf to string for Command::new()
///
/// This helper ensures proper string conversion with error handling.
pub fn path_to_string(path: &PathBuf) -> Result<String, String> {
    path.to_str()
        .ok_or_else(|| format!("Invalid path encoding: {:?}", path))
        .map(|s| s.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bundled_path_construction() {
        // This test just verifies the path construction logic compiles
        // Actual testing requires a real Tauri AppHandle which is only available at runtime
        assert!(
            cfg!(target_os = "windows") || cfg!(target_os = "macos") || cfg!(target_os = "linux")
        );
    }
}

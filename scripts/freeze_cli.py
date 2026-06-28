"""
PyInstaller build script for freezing the FiberPath CLI into a standalone executable.

This script creates a single-file executable that bundles Python and all dependencies,
eliminating the need for users to install Python or pip packages.

Usage:
    python scripts/freeze_cli.py

Output:
    dist/fiberpath[.exe] - Standalone executable for current platform
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Project root directory
ROOT_DIR = Path(__file__).parent.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"


def get_platform_config() -> dict[str, str | list[str]]:
    """Get platform-specific PyInstaller configuration."""
    system = platform.system()

    if system == "Windows":
        return {
            "name": "fiberpath",
            "console_mode": "--console",  # Must be console for proper stdio when called from Tauri
            "extension": ".exe",
        }
    elif system == "Darwin":  # macOS
        return {
            "name": "fiberpath",
            "console_mode": "--console",  # Keep console for debugging
            "extension": "",
        }
    elif system == "Linux":
        return {
            "name": "fiberpath",
            "console_mode": "--console",  # Keep console for debugging
            "extension": "",
        }
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def get_hidden_imports() -> list[str]:
    """Get list of hidden imports for PyInstaller.

    PyInstaller's static analysis may miss dynamically imported modules.
    We explicitly include all fiberpath subpackages to ensure they're bundled.
    """
    return [
        # Core fiberpath packages
        "fiberpath",
        "fiberpath.config",
        "fiberpath.config.schemas",
        "fiberpath.config.validator",
        "fiberpath.gcode",
        "fiberpath.gcode.dialects",
        "fiberpath.gcode.generator",
        "fiberpath.planning",
        "fiberpath.planning.calculations",
        "fiberpath.planning.exceptions",
        "fiberpath.planning.helpers",
        "fiberpath.planning.layer_strategies",
        "fiberpath.planning.machine",
        "fiberpath.planning.planner",
        "fiberpath.simulation",
        "fiberpath.visualization",
        "fiberpath.math_utils",
        # CLI packages
        "fiberpath_cli",
        "fiberpath_cli.main",
        "fiberpath_cli.plan",
        "fiberpath_cli.plot",
        "fiberpath_cli.simulate",
        "fiberpath_cli.stream",
        "fiberpath_cli.validate",
        "fiberpath_cli.output",
        # Third-party dependencies that may need explicit inclusion
        "pydantic",
        "pydantic_core",
        "typer",
        "rich",
        "numpy",
        "PIL",
        # Marlin streaming: the host library + pyserial's dynamic platform backend.
        "marlin_host",
        "serial",
        "serial.tools.list_ports",
    ]


def build_executable() -> None:
    """Build the frozen executable using PyInstaller."""
    config = get_platform_config()
    hidden_imports = get_hidden_imports()

    # PyInstaller command
    # Entry point is the Typer app object, NOT __main__.py
    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",  # Single executable file
        "--name",
        config["name"],
        config["console_mode"],  # Platform-specific console mode
        "--clean",  # Clean PyInstaller cache
        "--noconfirm",  # Overwrite without asking
        # Add hidden imports
        *[f"--hidden-import={imp}" for imp in hidden_imports],
        # Collect all packages - both fiberpath and dependencies
        "--collect-all",
        "fiberpath",
        "--collect-all",
        "fiberpath_cli",
        "--collect-all",
        "typer",
        "--collect-all",
        "rich",
        "--collect-all",
        "pydantic",
        "--collect-all",
        "pydantic_core",
        "--collect-all",
        "numpy",
        "--collect-all",
        "PIL",
        "--collect-all",
        "marlin_host",
        "--collect-all",
        "serial",
        "--collect-submodules",
        "click",  # Typer dependency
        # Entry point script (will be created temporarily)
        "--path",
        str(ROOT_DIR),
    ]

    # Create temporary entry point script
    entry_script = ROOT_DIR / "_freeze_entry.py"
    entry_script.write_text(
        """
# Temporary entry point for PyInstaller
from fiberpath_cli.main import app

if __name__ == "__main__":
    app()
"""
    )

    pyinstaller_args.append(str(entry_script))

    print("=" * 60)
    print("FiberPath CLI Freezing with PyInstaller")
    print("=" * 60)
    print(f"Platform: {platform.system()} ({platform.machine()})")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Output: {DIST_DIR / config['name']}{config['extension']}")
    print()

    # Clean previous builds
    if BUILD_DIR.exists():
        print("Cleaning build directory...")
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        print("Cleaning dist directory...")
        shutil.rmtree(DIST_DIR)

    print("\nRunning PyInstaller...")
    print(" ".join(pyinstaller_args))
    print()

    try:
        subprocess.run(pyinstaller_args, check=True, cwd=ROOT_DIR)
    finally:
        # Clean up temporary entry script
        if entry_script.exists():
            entry_script.unlink()
        # Clean up PyInstaller spec file
        spec_file = ROOT_DIR / f"{config['name']}.spec"
        if spec_file.exists():
            spec_file.unlink()

    # Verify output
    output_exe = DIST_DIR / f"{config['name']}{config['extension']}"
    if not output_exe.exists():
        raise RuntimeError(f"Build failed: {output_exe} not found")

    # Get file size
    size_mb = output_exe.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("[OK] Build successful!")
    print("=" * 60)
    print(f"Executable: {output_exe}")
    print(f"Size: {size_mb:.1f} MB")

    if size_mb > 80:
        print(f"\n[WARNING] Executable size ({size_mb:.1f} MB) exceeds 80 MB target")

    print("\nTo test the executable:")
    print(f"  {output_exe} --help")
    print(f"  {output_exe} --version")
    print(f"  {output_exe} validate <config.wind>")
    print(f"  {output_exe} plan <config.wind> -o output.gcode")


def check_pyinstaller() -> None:
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller

        print(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("PyInstaller not found, installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("PyInstaller installed successfully")


def main() -> None:
    """Main entry point."""
    try:
        check_pyinstaller()
        build_executable()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

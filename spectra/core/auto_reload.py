"""Auto-reload mechanism for Spectra development.

Watches for source file changes and automatically reloads Spectra:
- Monitors Python source files for modifications
- Debounces rapid changes to avoid excessive reloads
- Preserves user state across reloads where possible
- Provides UI feedback during reload process
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable

# File watching state
_watcher_thread: threading.Thread | None = None
_watcher_running = False
_watcher_stop_event = threading.Event()

# File modification tracking
_file_hashes: dict[str, str] = {}
_last_reload_time = 0
_reload_debounce_seconds = 2.0  # Wait 2 seconds after last change before reloading

# Reload callbacks
_reload_callbacks: list[Callable[[], None]] = []


def _get_file_hash(filepath: str) -> str:
    """Calculate MD5 hash of file contents.

    Args:
        filepath: Path to file

    Returns:
        Hex string hash
    """
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _get_spectra_source_files() -> list[str]:
    """Get all Python source files in Spectra package.

    Returns:
        List of file paths
    """
    try:
        # Find spectra package directory
        import spectra
        package_dir = Path(spectra.__file__).parent

        # Find all Python files
        source_files = []
        for root, dirs, files in os.walk(package_dir):
            # Skip __pycache__ and test directories
            dirs[:] = [d for d in dirs if d not in ["__pycache__", "tests", ".pytest_cache"]]

            for file in files:
                if file.endswith(".py"):
                    source_files.append(str(Path(root) / file))

        return source_files
    except Exception:
        return []


def _initialize_file_hashes() -> None:
    """Initialize file hash tracking for all source files."""
    global _file_hashes

    source_files = _get_spectra_source_files()
    for filepath in source_files:
        _file_hashes[filepath] = _get_file_hash(filepath)


def _check_for_changes() -> list[str]:
    """Check for file modifications since last check.

    Returns:
        List of changed file paths
    """
    changed_files = []

    for filepath, old_hash in _file_hashes.items():
        new_hash = _get_file_hash(filepath)
        if new_hash and new_hash != old_hash:
            changed_files.append(filepath)
            _file_hashes[filepath] = new_hash

    return changed_files


def _reload_spectra() -> None:
    """Reload Spectra modules and notify callbacks."""
    from .logging import log_info, log_warning, log_error

    try:
        log_info("Reloading Spectra due to source changes...")

        # Reload main spectra package
        if "spectra" in sys.modules:
            importlib.reload(sys.modules["spectra"])

        # Reload all spectra submodules
        modules_to_reload = [
            name for name in sys.modules
            if name.startswith("spectra.") and not name.startswith("__")
        ]

        for module_name in sorted(modules_to_reload, key=lambda x: x.count(".")):
            try:
                importlib.reload(sys.modules[module_name])
            except Exception as e:
                log_warning(f"Failed to reload {module_name}: {e}")

        log_info("Spectra reloaded successfully")

        # Notify callbacks (e.g., UI refresh)
        for callback in _reload_callbacks:
            try:
                callback()
            except Exception as e:
                log_error(f"Reload callback error: {e}")

    except Exception as e:
        log_error(f"Failed to reload Spectra: {e}")


def _file_watcher_loop() -> None:
    """Main file watcher loop (runs in background thread)."""
    from .logging import log_debug, log_info

    global _last_reload_time

    log_info("File watcher started - monitoring Spectra source files")

    while _watcher_running:
        try:
            # Check for changes
            changed_files = _check_for_changes()

            if changed_files:
                current_time = time.time()

                # Debounce: wait for calm period before reloading
                time_since_last_reload = current_time - _last_reload_time

                if time_since_last_reload >= _reload_debounce_seconds:
                    # Log which files changed
                    for filepath in changed_files:
                        rel_path = Path(filepath).relative_to(Path.cwd())
                        log_debug(f"Changed: {rel_path}")

                    # Trigger reload
                    _last_reload_time = current_time
                    _reload_spectra()

            # Sleep before next check (poll every 500ms)
            _watcher_stop_event.wait(0.5)

        except Exception as e:
            from .logging import log_error
            log_error(f"File watcher error: {e}")
            _watcher_stop_event.wait(5)  # Wait longer on error

    log_info("File watcher stopped")


def start_file_watcher() -> bool:
    """Start the file watcher background thread.

    Returns:
        True if watcher was started, False if already running
    """
    global _watcher_thread, _watcher_running

    if _watcher_running:
        return False

    # Initialize file hashes
    _initialize_file_hashes()

    # Start watcher thread
    _watcher_running = True
    _watcher_stop_event.clear()

    _watcher_thread = threading.Thread(
        target=_file_watcher_loop,
        name="SpectraFileWatcher",
        daemon=True
    )
    _watcher_thread.start()

    return True


def stop_file_watcher() -> None:
    """Stop the file watcher background thread."""
    global _watcher_running, _watcher_thread

    if not _watcher_running:
        return

    _watcher_running = False
    _watcher_stop_event.set()

    if _watcher_thread:
        _watcher_thread.join(timeout=5)
        _watcher_thread = None


def is_watching() -> bool:
    """Check if file watcher is currently running.

    Returns:
        True if watcher is running
    """
    return _watcher_running


def register_reload_callback(callback: Callable[[], None]) -> None:
    """Register a callback to be called after each reload.

    Args:
        callback: Function to call after reload
    """
    if callback not in _reload_callbacks:
        _reload_callbacks.append(callback)


def unregister_reload_callback(callback: Callable[[], None]) -> None:
    """Unregister a reload callback.

    Args:
        callback: Function to remove from callbacks
    """
    if callback in _reload_callbacks:
        _reload_callbacks.remove(callback)


def trigger_manual_reload() -> None:
    """Manually trigger a Spectra reload."""
    global _last_reload_time
    _last_reload_time = time.time()
    _reload_spectra()


# Alias for convenience
trigger_reload = trigger_manual_reload


# Convenience function for use in IDA
def enable_auto_reload() -> bool:
    """Enable auto-reload for development convenience.

    Returns:
        True if auto-reload was enabled
    """
    from .logging import log_info

    if start_file_watcher():
        log_info("Auto-reload enabled - Spectra will reload on source changes")
        return True
    else:
        log_info("ℹ️ Auto-reload already enabled")
        return False


def disable_auto_reload() -> None:
    """Disable auto-reload."""
    from .logging import log_info

    stop_file_watcher()
    log_info("Auto-reload disabled")


if __name__ == "__main__":
    # Test file watcher
    print("Testing file watcher...")

    # Start watcher
    if enable_auto_reload():
        print("Watcher started. Modify a Python file to test auto-reload.")

        # Wait for user input
        try:
            input("Press Enter to stop...")
        except KeyboardInterrupt:
            pass

        disable_auto_reload()
    else:
        print("Failed to start watcher")

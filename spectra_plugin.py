"""Spectra - Intelligent Reverse-engineering Integrated System.

IDA Pro plugin entry point.
All spectra.* imports are deferred to avoid crashes during plugin enumeration.
"""

import builtins
import importlib
import threading

import idaapi

# ---------------------------------------------------------------------------
# Shiboken __import__ hook re-entrancy guard
# ---------------------------------------------------------------------------
# PySide6/Shiboken6 patches builtins.__import__ with a hook.  When this
# hook is invoked during Qt signal dispatch (e.g. submit_requested.emit()),
# and the connected slot's code triggers an import, the hook re-enters
# itself.  After 3-4 levels of nesting the hook accesses freed memory
# (UAF → SIGSEGV in ___lldb_unnamed_symbol945, address looks like ASCII
# string fragment — type-name pointer corruption).
#
# Fix: wrap the hook so that first-level calls go through Shiboken
# normally (preserving PySide6 module wrapping), but nested calls
# (re-entrant) are redirected to CPython's standard import, avoiding
# the corruption.  Installed once and never removed.

_import_guard = threading.local()
_shiboken_import = builtins.__import__


def _guarded_import(*args, **kwargs):
    if getattr(_import_guard, "active", False):
        # Re-entrant call — bypass Shiboken's hook
        return importlib.__import__(*args, **kwargs)
    _import_guard.active = True
    try:
        return _shiboken_import(*args, **kwargs)
    finally:
        _import_guard.active = False


_guarded_import._spectra_guarded = True  # marker to avoid double-wrapping
if not getattr(builtins.__import__, "_spectra_guarded", False):
    builtins.__import__ = _guarded_import


class SpectraPlugmod(idaapi.plugmod_t):
    """Per-database plugin module."""

    def __init__(self):
        super().__init__()
        self._panel = None

    def run(self, arg: int) -> bool:
        self._toggle_panel()
        return True

    def term(self) -> None:
        _log("SpectraPlugmod.term() called")
        panel = self._panel
        self._panel = None
        if panel is not None:
            try:
                panel.close()
            except Exception as e:
                idaapi.msg(f"[Spectra] Panel close error: {e}\n")
        # Flush deferred widget deletions while Python is still alive.
        # Without this, orphaned PySide6-wrapped QFrames survive until
        # QApplication::~QApplication() where their C++ destructors call
        # disconnectNotify -> PyErr_Occurred on a dead interpreter -> crash.
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
        except Exception:
            pass

    def _toggle_panel(self) -> None:
        try:
            _log("_toggle_panel: entry")
            if self._panel is not None:
                _log("_toggle_panel: panel exists, calling show()")
                self._panel.show()
                return

            # Import only the panel entry module here.  Its dependency chain
            # loads the rest lazily as needed, avoiding a full recursive
            # package walk on first panel open.
            _log("_toggle_panel: importing panel module")

            # Temporarily bypass Shiboken's __import__ hook while the panel
            # module and its direct imports execute. importlib.import_module()
            # itself avoids __import__, but module code can still emit
            # IMPORT_NAME bytecode that reaches builtins.__import__.
            saved_import = builtins.__import__
            builtins.__import__ = importlib.__import__
            try:
                SpectraPanel = importlib.import_module("spectra.ida.ui.panel").SpectraPanel
            finally:
                builtins.__import__ = saved_import

            _log("_toggle_panel: panel module loaded")

            _log("_toggle_panel: creating SpectraPanel()")
            self._panel = SpectraPanel()
            _log("_toggle_panel: calling show()")
            self._panel.show()
            _log("_toggle_panel: done")
        except Exception as e:
            import sys
            import traceback

            tb_str = traceback.format_exc()
            idaapi.msg(f"[Spectra] Failed to open panel: {e}\n{tb_str}\n")
            try:
                importlib.import_module("spectra.core.logging").log_error(f"Failed to open panel: {e}\n{tb_str}")
            except Exception:
                try:
                    import os

                    log_path = os.path.join(os.path.expanduser("~"), ".idapro", "spectra", "spectra_debug.log")
                    with open(log_path, "a") as f:
                        f.write(f"[Spectra CRASH] {e}\n{tb_str}\n")
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    print(f"[Spectra CRASH] {e}\n{tb_str}", file=sys.stderr)


class SpectraPlugin(idaapi.plugin_t):
    flags = idaapi.PLUGIN_MULTI | idaapi.PLUGIN_FIX
    comment = "Intelligent Reverse-engineering Integrated System"
    help = ""
    wanted_name = "Spectra"
    wanted_hotkey = "Ctrl+Shift+I"

    def init(self) -> idaapi.plugmod_t:
        _ver = importlib.import_module("spectra.constants").PLUGIN_VERSION
        idaapi.msg(f"[Spectra] Plugin loaded (v{_ver})\n")

        # Background update check — daemon thread, never blocks IDA startup.
        try:
            _updater_mod = importlib.import_module("spectra.core.updater")

            def _notify_update(info) -> None:
                text = (
                    f"[Spectra] Update available: {info.current_version} → {info.latest_version} "
                    "(Settings → Update)\n"
                )
                try:
                    _kernwin = importlib.import_module("ida_kernwin")

                    class _MsgSync(_kernwin.execute_sync):
                        def __init__(self) -> None:
                            super().__init__()
                            self._text = text

                        def run(self) -> int:
                            idaapi.msg(self._text)
                            return 1

                    _MsgSync()  # marshals msg() onto the main thread
                except Exception:
                    _log(text.strip())

            _updater_mod.check_and_notify(_notify_update)
        except Exception as _e:
            _log(f"startup update check unavailable: {_e}")

        # Add Windows Python site-packages to IDA's Python path
        import os
        import sys

        if sys.platform == "win32":
            import glob

            username = os.environ.get("USERNAME", "user")

            # First, try to add the lib subdirectory next to the spectra package
            # This contains x64-compatible packages for ARM64 systems
            try:
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                lib_dir = os.path.join(plugin_dir, "lib")
                if os.path.isdir(lib_dir) and lib_dir not in sys.path:
                    sys.path.insert(0, lib_dir)
                    idaapi.msg(f"[Spectra] Added lib directory: {lib_dir}\n")
            except Exception:
                pass

            # Windows Python site-packages locations (for fallback)
            # Prefer Program Files (x64 Python) over AppData (may be ARM64)
            possible_paths = [
                "C:\\Program Files\\Python3*\\Lib\\site-packages",  # x64 Python
                "C:\\Program Files (x86)\\Python3*\\Lib\\site-packages",
                f"C:\\Users\\{username}\\AppData\\Local\\Programs\\Python\\Python3*\\Lib\\site-packages",
                f"C:\\Users\\{username}\\AppData\\Roaming\\Python\\Python3*\\site-packages",
            ]

            for pattern in possible_paths:
                try:
                    for match in glob.glob(pattern):
                        if os.path.isdir(match) and match not in sys.path:
                            sys.path.insert(0, match)
                            idaapi.msg(f"[Spectra] Added: {match}\n")
                except Exception:
                    pass

        # ---------------------------------------------------------------
        # Inject site-packages paths into IDA's embedded Python sys.path
        # IDA ships its own Python interpreter, so packages installed via
        # the system pip are not visible unless we explicitly add their
        # directories here.  We do this BEFORE the anthropic import check
        # so that a manual `pip install --user anthropic` by the user is
        # picked up immediately on the next IDA restart.
        # ---------------------------------------------------------------
        if sys.platform != "win32":
            try:
                import site as _site

                major = sys.version_info.major
                minor = sys.version_info.minor
                home = os.path.expanduser("~")

                # Paths to probe (ordered: most specific first)
                extra_paths = [
                    # User site-packages for IDA's exact Python version
                    os.path.join(home, ".local", "lib", f"python{major}.{minor}", "site-packages"),
                    # Broader user local lib (catches minor version drift)
                    os.path.join(home, ".local", "lib", f"python{major}", "site-packages"),
                    # site module's own answer (may differ from above on some distros)
                    _site.getusersitepackages() if hasattr(_site, "getusersitepackages") else None,
                    # System-wide site-packages
                    f"/usr/lib/python{major}/dist-packages",
                    f"/usr/lib/python{major}.{minor}/dist-packages",
                    f"/usr/lib/python{major}.{minor}/site-packages",
                    f"/usr/local/lib/python{major}.{minor}/dist-packages",
                    f"/usr/local/lib/python{major}.{minor}/site-packages",
                ]

                added = []
                for p in extra_paths:
                    if p and os.path.isdir(p) and p not in sys.path:
                        sys.path.insert(0, p)
                        added.append(p)
                if added:
                    idaapi.msg(f"[Spectra] Injected {len(added)} site-packages path(s) into sys.path\n")
            except Exception as _e:
                idaapi.msg(f"[Spectra] site-packages injection warning: {_e}\n")

        # Check for anthropic, and auto-install if missing
        try:
            importlib.import_module("anthropic")
            idaapi.msg("[Spectra] anthropic found\n")
        except ImportError as e:
            idaapi.msg(f"[Spectra] WARNING: anthropic not found: {e}\n")
            idaapi.msg("[Spectra] Attempting auto-install...\n")
            # Call auto-install (defined below)
            self._ensure_anthropic_installed()
            # Re-check after install attempt
            try:
                importlib.import_module("anthropic")
                idaapi.msg("[Spectra] anthropic installed successfully\n")
            except ImportError:
                idaapi.msg("[Spectra] sys.path sample:\n")
                for p in sys.path[:5]:
                    idaapi.msg(f"  {p}\n")

        plugmod_instance = SpectraPlugmod()
        return plugmod_instance

    def _ensure_anthropic_installed(self) -> None:
        """Auto-install anthropic package if missing, using IDA's Python or system Python.

        Cross-platform: Windows, Linux, macOS. Uses sys.executable (current interpreter)
        as primary target, falls back to IDA's bundled Python.
        """
        try:
            importlib.import_module("anthropic")
            return  # Already installed
        except ImportError:
            pass  # Need to install

        try:
            import os
            import subprocess
            import sys

            python_exe = None
            ida_dir = os.path.dirname(os.path.dirname(idaapi.__file__))

            # Primary: Use sys.executable if it's a real Python (not IDA binary)
            # IDA's embedded Python may have sys.executable pointing to ida64/ida
            if sys.executable and os.path.exists(sys.executable):
                # Check if it looks like a Python executable
                exe_name = os.path.basename(sys.executable).lower()
                if "python" in exe_name or (sys.platform == "win32" and exe_name.endswith(".exe")):
                    # Verify it can run pip
                    test_result = subprocess.run(
                        [sys.executable, "-m", "pip", "--version"], capture_output=True, timeout=10
                    )
                    if test_result.returncode == 0:
                        python_exe = sys.executable

            # Fallback: Find IDA's bundled Python executable
            if not python_exe:
                if sys.platform == "win32":
                    exe_names = ["python.exe", "python3.exe"]
                else:
                    exe_names = ["python3", "python"]

                # Try IDA 9.1+ python directory
                for exe in exe_names:
                    test_path = os.path.join(ida_dir, "python", exe)
                    if os.path.exists(test_path):
                        python_exe = test_path
                        break

                # Try versioned directories (older IDA)
                if not python_exe:
                    for py_ver in ["python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3.8"]:
                        for exe in exe_names:
                            test_path = os.path.join(ida_dir, py_ver, exe)
                            if os.path.exists(test_path):
                                python_exe = test_path
                                break
                        if python_exe:
                            break

            # Last resort: system Python (Linux/macOS/Windows)
            if not python_exe:
                if sys.platform == "win32":
                    # Windows system Python
                    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                    username = os.environ.get("USERNAME", "user")
                    for pattern in [
                        f"C:\\Program Files\\Python{py_version}\\python.exe",
                        f"C:\\Program Files\\Python{sys.version_info.major}{sys.version_info.minor}\\python.exe",
                        f"C:\\Users\\{username}\\AppData\\Local\\Programs\\Python\\Python{py_version}\\python.exe",
                    ]:
                        if os.path.exists(pattern):
                            python_exe = pattern
                            break
                else:
                    # Linux/macOS: try shutil.which() first (respects PATH), then
                    # versioned names, then common hardcoded paths.
                    import shutil

                    # Build version-specific names from interpreter version info
                    major = sys.version_info.major
                    minor = sys.version_info.minor
                    versioned_names = [
                        f"python{major}.{minor}",
                        f"python{major}",
                        "python3",
                        "python",
                    ]

                    # Also try to parse version from sys.path entries like
                    # "/home/kali/ida-pro-9.1/python" or "python314"
                    import re

                    for p in sys.path:
                        m = re.search(r"python(\d)(\d+)", os.path.basename(p))
                        if m:
                            extra = f"python{m.group(1)}.{m.group(2)}"
                            if extra not in versioned_names:
                                versioned_names.insert(0, extra)

                    # Try PATH lookup first
                    for name in versioned_names:
                        found = shutil.which(name)
                        if found:
                            python_exe = found
                            break

                    # Hardcoded fallback directories
                    if not python_exe:
                        search_dirs = [
                            "/usr/bin",
                            "/usr/local/bin",
                            "/opt/homebrew/bin",
                            os.path.expanduser("~/.local/bin"),
                            "/opt/conda/bin",
                            "/usr/bin/env",
                        ]
                        for name in versioned_names:
                            for d in search_dirs:
                                candidate = os.path.join(d, name)
                                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                                    python_exe = candidate
                                    break
                            if python_exe:
                                break

            if python_exe and os.path.exists(python_exe):
                idaapi.msg(f"[Spectra] Installing anthropic with Python: {python_exe}\n")

                # Try user installation first (avoids externally-managed-environment on Debian/Kali)
                result = subprocess.run(
                    [python_exe, "-m", "pip", "install", "--user", "anthropic>=0.39.0", "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                # If user install fails, try regular install (for non-externally-managed systems)
                if result.returncode != 0:
                    result = subprocess.run(
                        [python_exe, "-m", "pip", "install", "anthropic>=0.39.0", "--quiet"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                if result.returncode == 0:
                    idaapi.msg("[Spectra] anthropic installed successfully\n")
                    # Add user site-packages to sys.path if not already there
                    try:
                        import site

                        user_site = site.getusersitepackages()
                        if user_site not in sys.path:
                            sys.path.insert(0, user_site)
                            idaapi.msg(f"[Spectra] Added user site-packages: {user_site}\n")
                    except Exception:
                        pass
                else:
                    idaapi.msg(f"[Spectra] Warning: install had issues: {result.stderr[:200]}\n")
            else:
                idaapi.msg("[Spectra] Warning: Could not find Python executable\n")
                idaapi.msg(f"[Spectra] IDA dir: {ida_dir}\n")
                idaapi.msg(f"[Spectra] sys.executable: {sys.executable}\n")
                idaapi.msg("[Spectra] Please install manually:\n")
                idaapi.msg("[Spectra]   python3 -m pip install --user anthropic>=0.39.0\n")
        except subprocess.TimeoutExpired as e:
            idaapi.msg(f"[Spectra] Warning: Install timed out after {e.timeout} seconds\n")
            idaapi.msg("[Spectra] Please install manually: python -m pip install anthropic>=0.39.0\n")
        except Exception as e:
            idaapi.msg(f"[Spectra] Warning: Auto-install failed: {e}\n")
            idaapi.msg("[Spectra] Please install manually: python -m pip install anthropic>=0.39.0\n")


def _log(msg: str) -> None:
    """Best-effort log to IDA output and debug file."""
    idaapi.msg(f"[Spectra] {msg}\n")
    try:
        importlib.import_module("spectra.core.logging").log_trace(msg)
    except Exception as e:
        import sys

        sys.stderr.write(f"[Spectra] log_trace unavailable during bootstrap: {e}\n")


def PLUGIN_ENTRY():
    return SpectraPlugin()

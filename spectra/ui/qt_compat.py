"""Qt compatibility layer for Spectra.

IDA 9.x 64-bit and Binary Ninja ship PySide6 (Qt6).  IDA 9.1 32-bit on
Windows still uses Qt5 — its process has Qt5Core.dll loaded.  Importing
PySide6 in that environment loads Qt6 DLLs alongside Qt5, which triggers a
``FAST_FAIL_FATAL_APP_EXIT`` crash inside ``QWidgetPrivate::QWidgetPrivate``
(Qt6 widget constructor detects it is not running in a Qt6 QApplication).

Detection order:
1. Check ``sys.modules`` for an already-loaded binding (fast, cross-platform).
2. On Windows, check if ``Qt5Core.dll`` is loaded in the process — if so, the
   host is Qt5-based and we must avoid loading PySide6.
3. Default: try PySide6, fall back to PyQt5.
"""

from __future__ import annotations

import sys
from typing import Any, cast


def _detect_binding() -> str:
    """Return ``"PySide6"``, ``"PyQt5"``, or ``"PySide2"`` based on host environment."""

    # Fast path: a binding is already imported by the host.
    has_pyside6 = any(k.startswith("PySide6.") for k in sys.modules)
    has_pyqt5 = any(k.startswith("PyQt5.") for k in sys.modules)
    has_pyside2 = any(k.startswith("PySide2.") for k in sys.modules)

    if has_pyside6 and not has_pyqt5:
        return "PySide6"
    if has_pyqt5 and not has_pyside6:
        return "PyQt5"
    if has_pyside2:
        return "PySide2"

    # On Windows, check whether Qt5 DLLs are already loaded by the host
    # process *before* importing anything that would pull in Qt6.
    # On macOS, check whether Qt5 frameworks are loaded by IDA Pro.
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            if kernel32.GetModuleHandleW("Qt5Core.dll"):
                return "PyQt5"
        except Exception:
            pass
    elif sys.platform == "darwin":
        # On macOS, IDA Pro uses Qt5 frameworks. Check if QtWidgets is already loaded.
        # If Qt5 is present in the process, avoid PySide6 (Qt6) to prevent crashes.
        try:
            import ctypes
            import ctypes.util

            # Try to find if Qt5 is already loaded in the process
            # dyld image cache can tell us what's loaded
            _dyld = ctypes.CDLL(ctypes.util.find_library("dyld"))
            # _dyld_image_count and _dyld_get_image_name are available
            # but simpler: just check if we're running under IDA by checking sys.executable
            # or try to detect Qt5 via module check
            pass
        except Exception:
            pass

        # Simpler check: if we're running under IDA, use PyQt5 by default
        # IDA Pro on macOS uses Qt5, and PySide6 (Qt6) causes crashes
        try:
            # Check if we're running under IDA by examining the executable path
            if "ida" in sys.executable.lower() or "IDA" in sys.executable:
                return "PyQt5"
        except Exception:
            pass

    # Default: try PySide6 -> PyQt5 -> PySide2.
    try:
        import PySide6  # noqa: F401

        return "PySide6"
    except ImportError:
        pass

    try:
        import PyQt5  # noqa: F401

        return "PyQt5"
    except ImportError:
        pass

    try:
        import PySide2  # noqa: F401

        return "PySide2"
    except ImportError:
        pass

    raise ImportError(
        "Spectra requires a Qt binding (PySide6, PyQt5, or PySide2).\nPlease install PySide6 using: pip install PySide6"
    )


QT_BINDING: str = _detect_binding()

# ---------------------------------------------------------------------------
# Import the chosen binding, aliasing PyQt5 names to match PySide6 API.
# ---------------------------------------------------------------------------

if QT_BINDING == "PySide6":
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import (
        QColor,
        QFont,
        QIntValidator,
        QKeySequence,
        QSyntaxHighlighter,
        QTextCharFormat,
    )
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QClipboard,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QShortcut,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QStackedWidget,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
elif QT_BINDING == "PySide2":
    from PySide2.QtCore import (
        QObject,
        Qt,
        QTimer,
        Signal,
    )
    from PySide2.QtGui import (
        QClipboard,
        QColor,
        QFont,
        QIntValidator,
        QKeySequence,
        QSyntaxHighlighter,
        QTextCharFormat,
    )
    from PySide2.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QShortcut,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QStackedWidget,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
else:
    from PyQt5.QtCore import QObject, Qt, QTimer  # noqa: F401
    from PyQt5.QtCore import pyqtSignal as Signal  # noqa: F401
    from PyQt5.QtGui import (  # noqa: F401
        QClipboard,
        QColor,
        QFont,
        QIntValidator,
        QKeySequence,
        QSyntaxHighlighter,
        QTextCharFormat,
    )
    from PyQt5.QtWidgets import (  # noqa: F401
        QAbstractItemView,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QShortcut,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QStackedWidget,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )


def qt_flags(*flags: object) -> object:
    """Combine same-family Qt enum/flag values without relying on PyQt5 shim bitwise behavior."""
    if not flags:
        return 0

    value = 0
    flag_type: type[Any] | None = None
    for flag in flags:
        current_type = type(flag)
        if flag_type is None:
            flag_type = current_type
        elif current_type is not flag_type:
            raise TypeError(f"qt_flags() received mixed flag types: {flag_type.__name__} and {current_type.__name__}")
        flag_value = getattr(flag, "value", flag)
        value |= int(cast(Any, flag_value))

    if flag_type is None:
        return value
    return cast(Any, flag_type)(value)


def qt_run(obj: object, *args, **kwargs) -> object:
    """Call Qt6-style run API with Qt5 fallback where needed."""
    run = getattr(obj, "exec", None)
    if callable(run):
        return run(*args, **kwargs)
    run_legacy = getattr(obj, "exec_", None)
    if callable(run_legacy):
        return run_legacy(*args, **kwargs)
    raise AttributeError(f"{type(obj).__name__} has no exec/exec_ method")


def is_pyside6() -> bool:
    return QT_BINDING == "PySide6"


# ---------------------------------------------------------------------------
# DPI scaling helpers for high-DPI displays
# ---------------------------------------------------------------------------

_dpi_scale_factor: float | None = None


def get_dpi_scale_factor() -> float:
    """Get the current DPI scale factor for the application.

    Returns a value like 1.0 for 96 DPI (100%), 1.5 for 144 DPI (150%),
    2.0 for 192 DPI (200%), etc.

    The result is cached after the first call.

    Environment variable override:
        SPECTRA_DPI_SCALE - Set to override auto-detection (e.g., 1.5, 2.0)
    """
    global _dpi_scale_factor

    # Check for environment variable override first
    try:
        import os

        env_scale = os.environ.get("SPECTRA_DPI_SCALE")
        if env_scale:
            _dpi_scale_factor = float(env_scale)
            if _dpi_scale_factor > 0:
                import sys

                print(f"[Spectra DPI] Using SPECTRA_DPI_SCALE override: {_dpi_scale_factor}", file=sys.stderr)
                return _dpi_scale_factor
    except Exception:
        pass

    if _dpi_scale_factor is not None:
        return _dpi_scale_factor

    try:
        # Try to get the primary screen's DPI scale factor
        if QT_BINDING == "PySide6":
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    # Qt6 uses logical DPI; physical DPI gives actual pixels per inch
                    # Standard DPI is 96, so we divide by that
                    _dpi_scale_factor = screen.logicalDotsPerInch() / 96.0
                    # Debug logging
                    try:
                        import sys

                        print(
                            f"[Spectra DPI] Detected scale factor: {_dpi_scale_factor} (logical DPI: {screen.logicalDotsPerInch()})",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass
                    return _dpi_scale_factor
        else:  # PyQt5
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    _dpi_scale_factor = screen.logicalDotsPerInch() / 96.0
                    try:
                        import sys

                        print(
                            f"[Spectra DPI] Detected scale factor: {_dpi_scale_factor} (logical DPI: {screen.logicalDotsPerInch()})",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass
                    return _dpi_scale_factor
    except Exception:
        pass

    # Fallback: check Windows system DPI via registry
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            # Get the process DPI awareness
            _shcore = ctypes.windll.shcore
            # Try to get the DPI scale factor from Windows
            hdc = ctypes.windll.user32.GetDC(0)
            if hdc:
                logical_dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                ctypes.windll.user32.ReleaseDC(0, hdc)
                if logical_dpi:
                    _dpi_scale_factor = logical_dpi / 96.0
                    try:
                        import sys

                        print(
                            f"[Spectra DPI] Windows fallback scale factor: {_dpi_scale_factor} (DPI: {logical_dpi})",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass
                    return _dpi_scale_factor
        except Exception:
            pass

    # Default to 1.0 if we can't determine the scale factor
    _dpi_scale_factor = 1.0
    try:
        import sys

        print("[Spectra DPI] Using default scale factor: 1.0", file=sys.stderr)
    except Exception:
        pass
    return _dpi_scale_factor


def scale_font_size(size: int) -> int:
    """Scale a font size by the current DPI scale factor.

    Args:
        size: The base font size in points at 96 DPI

    Returns:
        The scaled font size in points
    """
    scale = get_dpi_scale_factor()
    # Round to nearest integer, minimum of 9 to prevent unreadable text
    return max(9, int(size * scale + 0.5))


def scale_value(value: int) -> int:
    """Scale a pixel value by the current DPI scale factor.

    Args:
        value: The base value in pixels at 96 DPI

    Returns:
        The scaled value in pixels
    """
    scale = get_dpi_scale_factor()
    return int(value * scale + 0.5)


def set_dpi_aware() -> None:
    """Enable DPI awareness for better high-DPI display support on Windows.

    Should be called before creating any Qt widgets.
    On Windows, this tells the OS that the application is DPI-aware and
    should handle scaling itself rather than being bitmap-stretched.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes
        import ctypes.wintypes

        # Try to set Per-Monitor DPI Awareness V2 (Windows 10 1703+)
        # This allows each monitor to have its own DPI scale factor
        shcore = ctypes.windll.shcore

        # Check if SetProcessDpiAwarenessContext is available (Windows 10 1703+)
        if hasattr(shcore, "SetProcessDpiAwarenessContext"):
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            result = shcore.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            if result:
                return  # Success

        # Fallback to SetProcessDpiAwareness (Windows 8.1+)
        if hasattr(shcore, "SetProcessDpiAwareness"):
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            PROCESS_PER_MONITOR_DPI_AWARE = 2
            shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
            return

        # Final fallback: user32.dll SetProcessDPIAware (Windows Vista+)
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDPIAware"):
            user32.SetProcessDPIAware()
    except Exception:
        # Silently fail if DPI awareness setup doesn't work
        pass

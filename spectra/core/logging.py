"""Spectra logging bootstrap.

This module is the single public API that all spectra modules import.
Sink implementations live in ``core.log_sinks`` — changes to file
rotation policy, host integration, or telemetry format do not
propagate to importers of this module.

Public API:
    get_logger, log_info, log_warning, log_warn, log_error, log_debug, log_trace
    register_host_sink   (re-exported from log_sinks)
    HostOutputHandler, IDAHandler, _FlushFileHandler  (for tests)
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

from .log_sinks import (  # noqa: F401 — re-exported for tests
    HostOutputHandler,
    IDAHandler,
    _FlushFileHandler,
    _JSONFormatter,
    _log_file_path,
    register_host_sink,
)

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger("Spectra")
    _logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[Spectra %(asctime)s.%(msecs)03d %(levelname)s %(threadName)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Host output handler (WARNING and above to avoid cluttering AI output)
    host_handler = HostOutputHandler()
    host_handler.setLevel(logging.WARNING)

    # Add ANSI codes for bold and color (Magenta for INFO, Red for ERROR, Yellow for WARNING)
    # Format: [Spectra] LEVEL: message with bold/magenta color
    class ColorFormatter(logging.Formatter):
        """Custom formatter with ANSI color codes."""

        def format(self, record: logging.LogRecord) -> str:
            # Base format
            _result = super().format(record)
            # Add color and bold based on level
            if record.levelno == logging.INFO:
                # Bold Magenta for INFO
                return f"\033[1;35m[Spectra] INFO:\033[0m {record.getMessage()}"
            elif record.levelno == logging.WARNING:
                # Bold Yellow for WARNING
                return f"\033[1;33m[Spectra] WARNING:\033[0m {record.getMessage()}"
            elif record.levelno == logging.ERROR:
                # Bold Red for ERROR
                return f"\033[1;31m[Spectra] ERROR:\033[0m {record.getMessage()}"
            else:
                return f"[Spectra] {record.levelname}: {record.getMessage()}"

    host_handler.setFormatter(ColorFormatter("[Spectra] %(levelname)s: %(message)s"))
    _logger.addHandler(host_handler)

    # File handler (DEBUG — everything, flush immediately)
    try:
        path = _log_file_path()
        file_handler = _FlushFileHandler(path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        _logger.addHandler(file_handler)
        _logger.debug(f"=== Spectra debug log started — {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        _logger.debug(f"Log file: {path}")
        _logger.debug(f"Python: {sys.version}")
        _logger.debug(f"Thread: {threading.current_thread().name}")
    except OSError as e:
        _logger.warning(f"Could not open debug log file: {e}")

    # Structured JSON log (JSONL format for machine parsing / analytics)
    try:
        json_path = os.path.join(os.path.dirname(_log_file_path()), "spectra_structured.jsonl")
        json_handler = _FlushFileHandler(json_path, mode="a", encoding="utf-8")
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(_JSONFormatter())
        _logger.addHandler(json_handler)
    except OSError as e:
        sys.stderr.write(f"[Spectra] Could not open structured log file: {e}\n")

    return _logger


def log_info(msg: str) -> None:
    get_logger().info(msg)


def log_warning(msg: str) -> None:
    get_logger().warning(msg)


def log_warn(msg: str) -> None:
    """Alias for log_warning for consistency."""
    log_warning(msg)


def log_error(msg: str) -> None:
    get_logger().error(msg)


def log_debug(msg: str) -> None:
    logger = get_logger()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)


def log_trace(label: str) -> None:
    """Verbose trace-level log (logged at DEBUG level with TRACE prefix)."""
    logger = get_logger()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"TRACE {label}")

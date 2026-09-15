"""Resolve a real Python interpreter for subprocess use.

Inside IDA, ``sys.executable`` points at the *host binary* (ida64.exe on
Windows, ida/ida64 on Linux and macOS) — the embedded interpreter has no
interpreter executable of its own. Running ``[sys.executable, script.py]``
or ``sys.executable -m pip`` there spawns new IDA instances instead of
Python; on Windows each spawned IDA reloaded the plugin, whose dependency
auto-install then spawned yet another IDA — an IDA relaunch loop.

Every subprocess call site that means "run this with Python" must go
through :func:`resolve_python_executable` (or apply the same
``is_python_interpreter`` guard) instead of trusting ``sys.executable``.
"""

from __future__ import annotations

import os
import shutil
import sys


def is_python_interpreter(path: str | None) -> bool:
    """True when *path* names a CPython interpreter, not a host binary.

    CPython executables always carry "python" in their basename
    (python, python3, python3.13, python.exe). IDA's ida64/idat64 never do.
    """
    if not path:
        return False
    return "python" in os.path.basename(path).lower()


def resolve_python_executable() -> str | None:
    """Best-effort real interpreter for subprocesses.

    Prefers ``sys.executable`` when it actually is a Python (the common
    case outside IDA); under IDA falls back to a PATH lookup for the
    embedded interpreter's version, then python3/python.

    Returns None when no standalone Python can be found — callers should
    surface an install hint rather than fall back to the host binary.
    """
    if is_python_interpreter(sys.executable) and os.path.exists(sys.executable):
        return sys.executable

    versioned = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for name in (versioned, "python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return None

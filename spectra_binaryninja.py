"""Binary Ninja plugin entry point for Spectra.

This module is intentionally thin — all runtime orchestration lives in
``spectra.binja.bootstrap``. Binary Ninja loads this via the root
``__init__.py`` when the plugin directory is registered.
"""

from __future__ import annotations

try:
    import binaryninja  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - loaded only in Binary Ninja runtime
    binaryninja = None

if binaryninja is not None:
    from .spectra.binja.bootstrap import register_plugin

    register_plugin()

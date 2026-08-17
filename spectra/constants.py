"""Global constants for Spectra.

This module is data-only — no runtime detection or host probing.
For host capability flags see ``spectra.core.host``.
"""

from __future__ import annotations

import json
from pathlib import Path

# Get the directory of this file (spectra/ package root)
_PACKAGE_DIR = Path(__file__).parent  # .../spectra/

# Walk up from the package to find update.json.
# When installed via symlinks (install_ida.sh), __file__ resolves to the
# real repo path, so update.json is always one level above the package.
_SPECTRA_ROOT = _PACKAGE_DIR.parent

# Read version from update.json
try:
    _update_json_path = _SPECTRA_ROOT / "update.json"
    if not _update_json_path.exists():
        # Fallback: search up to 3 levels
        for _parent in [_PACKAGE_DIR.parent, _PACKAGE_DIR.parent.parent, _PACKAGE_DIR.parent.parent.parent]:
            if (_parent / "update.json").exists():
                _update_json_path = _parent / "update.json"
                break
    with open(_update_json_path) as f:
        _update_info = json.load(f)
        PLUGIN_VERSION = _update_info["version"]
except (FileNotFoundError, KeyError, json.JSONDecodeError):
    PLUGIN_VERSION = "1.3.9"  # Fallback version — keep in sync with update.json

PLUGIN_NAME = "Spectra"
PLUGIN_HOTKEY = "Ctrl+Shift+I"
PLUGIN_COMMENT = "Intelligent Reverse-engineering Integrated System"

CONFIG_DIR_NAME = "spectra"
CONFIG_FILE_NAME = "config.json"
CHECKPOINTS_DIR_NAME = "checkpoints"

DEFAULT_MAX_TOKENS = 16384
DEFAULT_TEMPERATURE = 0.2
DEFAULT_CONTEXT_WINDOW = 200000

TOOL_RESULT_TRUNCATE_LEN = 8000

SYSTEM_PROMPT_VERSION = 1
CONFIG_SCHEMA_VERSION = 2
SESSION_SCHEMA_VERSION = 1

SKILLS_DIR_NAME = "skills"
MCP_CONFIG_FILE = "mcp.json"
MCP_TOOL_PREFIX = "mcp_"
MCP_DEFAULT_TIMEOUT = 30.0

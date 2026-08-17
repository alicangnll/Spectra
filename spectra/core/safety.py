"""Runtime opt-in for unrestricted tool commands (Settings checkbox).

Single source of truth consulted by every tool-level safety gate —
adb_shell's safe-command list, the Python script guard, and the shared
ToolSafety command/network checks — so one Settings toggle controls them
all.
"""

from __future__ import annotations


def unsafe_commands_allowed() -> bool:
    """True when the user opted in (Settings) to running unsafe commands.

    Reads the persisted config so toggling the checkbox takes effect
    immediately, without restarting the plugin. Fails closed (False) when
    the config cannot be read.
    """
    try:
        from .config import SpectraConfig

        val = SpectraConfig.load_or_create().allow_unsafe_commands
        # `is True` fails closed for mock/stub configs and malformed values
        return val is True
    except Exception as e:
        try:
            from .logging import log_debug

            log_debug(f"Could not read allow_unsafe_commands setting: {e}")
        except Exception:
            pass
        return False

"""Qt-based user interface.

Dialog classes are loaded lazily (PEP 562) so that importing
``spectra.ui`` — which the Qt-free CLI path does transitively via
``session_controller_base`` — does not require a Qt binding. The import
only happens when a dialog is actually requested from a Qt host.
"""

__all__ = ["AgentCreatorDialog"]


def __getattr__(name: str):
    if name == "AgentCreatorDialog":
        from .agent_creator_dialog import AgentCreatorDialog

        return AgentCreatorDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Qt-based user interface.

For CLI/non-GUI environments, avoid importing Qt modules by not importing
AgentCreatorDialog directly. Import it only when needed.
"""

__all__ = ["AgentCreatorDialog"]

# Lazy import to avoid loading Qt modules in CLI/non-GUI environments
def __getattr__(name: str):
    if name == "AgentCreatorDialog":
        from .agent_creator_dialog import AgentCreatorDialog
        return AgentCreatorDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

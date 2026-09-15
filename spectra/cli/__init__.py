"""Spectra CLI - Textual TUI interface.

This package provides a Claude-like CLI that exposes all Spectra capabilities
(skills, tools, agents) from a shell environment without disrupting the IDA Pro plugin.

Components:
    CLISessionController - CLI-specific session controller
    commands             - Slash-command registry (replaces command_parser)
    think_filter         - <think> reasoning stream filter
    app                  - Textual application shell
"""

from .shell_controller import CLISessionController, create_cli_tool_registry

__all__ = [
    "CLISessionController",
    "create_cli_tool_registry",
]

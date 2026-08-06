"""Spectra CLI - Shell-based interactive interface.

This package provides a Claude-like CLI that exposes all Spectra capabilities
(skills, tools, agents) from a shell environment without disrupting the IDA Pro plugin.

Components:
    CLISessionController - CLI-specific session controller
    ShellUI - Terminal UI handler with streaming
    ShellREPL - Enhanced REPL with history and completion
    parse_command - Command routing for slash commands
"""

from .shell_controller import CLISessionController, create_cli_tool_registry
from .shell_ui import ShellUI
from .shell_repl import ShellREPL
from .command_parser import Command, CommandType, parse_command

__all__ = [
    "CLISessionController",
    "create_cli_tool_registry",
    "ShellUI",
    "ShellREPL",
    "Command",
    "CommandType",
    "parse_command",
]

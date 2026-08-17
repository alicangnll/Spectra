"""Spectra CLI - Shell-based interactive interface.

This package provides a Claude-like CLI that exposes all Spectra capabilities
(skills, tools, agents) from a shell environment without disrupting the IDA Pro plugin.

Components:
    CLISessionController - CLI-specific session controller
    ShellUI - Terminal UI handler with streaming
    ShellREPL - Enhanced REPL with history and completion
    parse_command - Command routing for slash commands
"""

from .command_parser import Command, CommandType, parse_command
from .shell_controller import CLISessionController, create_cli_tool_registry
from .shell_repl import ShellREPL
from .shell_ui import ShellUI

__all__ = [
    "CLISessionController",
    "Command",
    "CommandType",
    "ShellREPL",
    "ShellUI",
    "create_cli_tool_registry",
    "parse_command",
]

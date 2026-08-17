#!/usr/bin/env python3
"""
Spectra CLI - AI-Powered Security Analysis Shell

Claude-like interactive CLI that exposes all Spectra capabilities:
- 39 built-in security skills
- Agent modes (plan, research, exploration)
- File operations and shell commands
- Session management
- Multi-provider LLM support (Anthropic, OpenAI, Gemini, Ollama)

Usage:
    # Start interactive shell
    python spectra_cli.py dir_loc <directory>

    # With API key
    SPECTRA_API_KEY="sk-xxx" python spectra_cli.py dir_loc <directory>

Commands:
    /skills          - List all available skills
    /skill <name>    - Invoke a specific skill
    /plan <prompt>   - Enter plan mode
    /research        - Enter research mode
    /save <name>     - Save session
    /load <id>       - Load session
    /sessions        - List saved sessions
    /new             - Start new session
    !command         - Execute shell command
    /help            - Show help

Author: Ali Can Gönüllü
License: MIT
Version: see update.json (single source of truth)
"""

__author__ = "Ali Can Gönüllü"

import argparse
import os
import sys
from pathlib import Path

# Add Spectra to path
spectra_path = Path(__file__).parent
sys.path.insert(0, str(spectra_path))

# ============================================================================
# NEW CLI INFRASTRUCTURE IMPORTS
# ============================================================================

from spectra.cli.shell_controller import CLISessionController  # noqa: E402
from spectra.cli.shell_repl import ShellREPL  # noqa: E402
from spectra.cli.shell_ui import ShellUI  # noqa: E402
from spectra.constants import PLUGIN_VERSION  # noqa: E402
from spectra.core.config import SpectraConfig  # noqa: E402
from spectra.core.logging import log_error, log_info  # noqa: E402

# Single source of truth for the version is update.json (read by
# spectra.constants); the CLI must never carry its own diverging copy.
__version__ = PLUGIN_VERSION

# ============================================================================
# CLI ENTRY POINT
# ============================================================================


def check_api_key_from_config(config) -> tuple[bool, str]:
    """Check if API key is configured.

    Args:
        config: SpectraConfig instance

    Returns:
        Tuple of (has_key, provider_name)
    """
    # First check environment variables (highest priority)
    api_key = os.getenv("SPECTRA_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return True, "anthropic"

    if os.getenv("OPENAI_API_KEY"):
        return True, "openai"

    if os.getenv("GEMINI_API_KEY"):
        return True, "gemini"

    # Check for Ollama (no API key needed)
    if os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL"):
        return True, "ollama"

    # Check config file
    if config and config.provider.api_key:
        return True, config.provider.name

    return False, "local"


def cmd_dir_loc(directory: str) -> int:
    """Start CLI in directory context mode.

    Args:
        directory: Working directory for analysis

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    working_dir = Path(directory).expanduser().resolve()

    if not working_dir.exists():
        print(f"❌ Directory not found: {working_dir}")
        return 1

    if not working_dir.is_dir():
        print(f"❌ Not a directory: {working_dir}")
        return 1

    # Change to working directory
    os.chdir(working_dir)
    log_info(f"Working directory: {working_dir}")

    try:
        # Initialize configuration
        config = SpectraConfig.load_or_create()

        # Check for API key (from env or config)
        has_key, _provider = check_api_key_from_config(config)

        # If no API key, prompt user
        if not has_key:
            print()
            print("⚠️  No API key found in environment or config.")
            print()
            print("To use Spectra CLI, you need an API key from one of these providers:")
            print("  • Anthropic Claude (recommended): https://console.anthropic.com/")
            print("  • OpenAI: https://platform.openai.com/api-keys")
            print("  • Google Gemini: https://makersuite.google.com/app/apikey")
            print("  • Ollama (local): https://ollama.com/")
            print()
            print("You can:")
            print("  1. Set environment variable: export ANTHROPIC_API_KEY=sk-xxx")
            print("  2. Use /apikey command in the CLI")
            print("  3. Run with: SPECTRA_API_KEY=sk-xxx python3 spectra_cli.py dir_loc <dir>")
            print()
            response = input("Do you want to enter an API key now? [Y/n]: ").strip().lower()

            if response in ("", "y", "yes"):
                key = input("Enter API key: ").strip()
                if key:
                    # Detect provider from key format
                    if key.startswith("sk-ant-"):
                        provider_name = "anthropic"
                    elif key.startswith("sk-"):
                        provider_name = "anthropic"  # Assume Anthropic for sk-
                    elif key.startswith("gsk_"):
                        provider_name = "openai"
                    elif key.startswith("AIza"):
                        provider_name = "gemini"
                    else:
                        print("Unknown key format. Assuming Anthropic.")
                        provider_name = "anthropic"

                    # Save to config
                    config.provider.name = provider_name
                    config.provider.api_key = key
                    config.save()

                    has_key = True
                    print(f"✓ API key saved for {provider_name}")
                    print()
                else:
                    print("No API key entered. Some features may not work.")
                    print()
            else:
                print("Continuing without API key. Use /apikey to set one later.")
                print()

        # Create session controller
        controller = CLISessionController(config)

        # Set up shell approval callback for interactive approval
        controller.set_shell_approval_callback()

        # Wait for runtime initialization
        import time

        max_wait = 10
        waited = 0
        while not controller._runtime_init_done.is_set() and waited < max_wait:
            time.sleep(0.1)
            waited += 0.1

        if not controller._runtime_init_done.is_set():
            print("Runtime initialization timeout")
            return 1

        # Create UI
        ui = ShellUI(use_colors=True, use_markdown=True)

        # Print header with controller (for disclaimer check)
        ui.print_header(controller=controller)

        # Print welcome with provider info
        ui.print_welcome(
            provider_name=config.provider.name,
            model_name=config.provider.model,
            has_api_key=has_key,
        )

        # Create and start REPL
        repl = ShellREPL(
            controller=controller,
            ui=ui,
        )

        # Start command loop
        repl.cmdloop()

        return 0

    except KeyboardInterrupt:
        print()
        print("👋 Interrupted. Goodbye!")
        print()
        return 0
    except Exception as e:
        import traceback

        log_error(f"Error: {e}")
        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(description="Spectra CLI - AI-Powered Security Analysis Shell")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("command", nargs="?", help="Command (dir_loc)")
    parser.add_argument("directory", nargs="?", help="Directory to analyze")

    args = parser.parse_args()

    if args.version:
        print(f"Spectra CLI v{__version__}")
        print()
        print("AI-Powered Security Analysis Shell")
        print()
        print("Provider Support:")
        print("  - Anthropic Claude (ANTHROPIC_API_KEY)")
        print("  - OpenAI GPT (OPENAI_API_KEY)")
        print("  - Google Gemini (GEMINI_API_KEY)")
        print("  - Ollama (local, OLLAMA_HOST)")
        print()
        print("Usage:")
        print("  python spectra_cli.py dir_loc <directory>")
        print()
        return 0

    if args.command == "dir_loc" and args.directory:
        return cmd_dir_loc(args.directory)

    # Show help if no valid command
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

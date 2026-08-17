"""Shell REPL - Enhanced interactive command loop.

Custom REPL with termios raw mode for Ctrl+O support:
- Tab completion for skills and commands
- Command history (persistent via readline)
- Ctrl+O to toggle tool result collapse/expand
- Slash command parsing
- Shell command execution
- Session commands
"""

from __future__ import annotations

import cmd
import os
import signal
import sys
from pathlib import Path

try:
    import readline

    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

from ..agent.turn import TurnEventType
from ..core.logging import log_debug
from .command_parser import (
    CONFIG_COMMANDS,
    SESSION_COMMANDS,
    SKILL_COMMANDS,
    SYSTEM_COMMANDS,
    CommandType,
    get_help_text,
    parse_command,
)
from .shell_controller import CLISessionController
from .shell_ui import Colors, ShellUI

# Extract command names (without arguments) for autocomplete
SESSION_CMD_NAMES = [cmd.split()[0] for cmd, _ in SESSION_COMMANDS]
CONFIG_CMD_NAMES = [cmd.split()[0] for cmd, _ in CONFIG_COMMANDS]
SYSTEM_CMD_NAMES = [cmd.split()[0] for cmd, _ in SYSTEM_COMMANDS]
SKILL_CMD_NAMES = [cmd.split()[0] for cmd, _ in SKILL_COMMANDS]

# All system/session/config commands (without arguments)
ALL_SLASH_COMMANDS = sorted(set(SESSION_CMD_NAMES + CONFIG_CMD_NAMES + SYSTEM_CMD_NAMES + SKILL_CMD_NAMES))


class ShellREPL(cmd.Cmd):
    """Enhanced REPL for Spectra CLI.

    Commands:
        All slash commands handled via command parser
        !shell_command for shell escape
        Natural language for AI chat

    Built-in commands (do_* methods):
        help, exit, quit, clear
    """

    # Custom prompt (bold)
    prompt = "\033[1mspectra> \033[0m"

    def __init__(
        self,
        controller: CLISessionController,
        ui: ShellUI,
        completekey: str = "tab",
    ):
        """Initialize ShellREPL.

        Args:
            controller: CLISessionController instance
            ui: ShellUI instance for output
            completekey: Key for tab completion
        """
        super().__init__(completekey=completekey)
        self.controller = controller
        self.ui = ui
        self.multiline_buffer = []
        self.in_multiline = False
        self._agent_runner = None  # Track agent runner for cancellation

        # Track active subagents for monitoring
        self._active_subagents: dict[str, dict] = {}

        # Set up signal handler for Ctrl+C
        self._setup_signal_handlers()

        # Initialize readline if available
        if HAS_READLINE:
            hist_file = Path.home() / ".spectra_history"
            try:
                readline.read_history_file(hist_file)
            except FileNotFoundError:
                pass

            # Set up readline completion
            readline.set_completer_delims(" \t\n")  # Only space, tab, newline as delimiters
            readline.set_completer(self.complete)
            readline.parse_and_bind("tab: complete")

    def _flush_input(self) -> None:
        """Flush any pending input from stdin buffer.

        This prevents buffered ENTER keystrokes during AI output from
        being immediately consumed by subsequent input() calls.

        Uses non-blocking I/O with aggressive timeout to prevent hangs.
        """
        try:
            import fcntl

            # Get current flags
            fd = sys.stdin.fileno()
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)

            # Set non-blocking mode
            fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

            # Read and discard any available input
            try:
                while True:
                    try:
                        data = sys.stdin.read(1024)
                        if not data:
                            break  # EOF
                    except (OSError, BlockingIOError):
                        break  # No more data available
            finally:
                # Restore original flags
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)

        except Exception:
            # If any error occurs, silently continue
            # This is a cleanup function, failures should not break the flow
            pass

    def _safe_input(self, prompt: str, default: str = "", timeout: float = 30.0) -> str:
        """Get user input with timeout protection.

        Args:
            prompt: Prompt to display
            default: Default value if timeout or error occurs
            timeout: Maximum seconds to wait for input (0 = no timeout)

        Returns:
            User input or default value
        """
        import threading

        # Use thread-based timeout for better cross-platform compatibility
        result = [default]  # Use list to share between threads
        input_done = threading.Event()

        def input_thread():
            try:
                user_input = input(prompt).strip()
                result[0] = user_input if user_input else default
            except (EOFError, KeyboardInterrupt):
                result[0] = default
            finally:
                input_done.set()

        thread = threading.Thread(target=input_thread, daemon=True)
        thread.start()

        # Wait for input with timeout
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Timeout occurred - thread is still running
            # Print a message and return default
            print()  # Newline
            # Note: We can't actually kill the thread, but input_done is set
            # so the thread will discard its result when it completes
            result[0] = default
            input_done.set()  # Signal that we've given up

        return result[0]

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful interruption."""

        def handle_interrupt(signum, frame):
            """Handle Ctrl+C - stop agent and terminate any running shell commands."""
            # Cancel agent if running
            if self._agent_runner:
                try:
                    self._agent_runner.cancel()
                    self._agent_runner = None
                except Exception:
                    pass

            # Kill any running shell command subprocesses
            try:
                from ..cli.tools.shell_tools import kill_all_subprocesses

                kill_all_subprocesses()
            except Exception:
                pass

            # Print message and show prompt
            print("\n⏹  Agent stopped. Back to input mode.")
            sys.stdout.flush()

            # Raise KeyboardInterrupt to break out of any blocking calls
            raise KeyboardInterrupt

        # Set SIGINT handler
        signal.signal(signal.SIGINT, handle_interrupt)

    # --- Cmd.Cmd overrides ---

    def precmd(self, line: str) -> str:
        """Hook executed before command processing.

        Handle multi-line input and shell escapes.
        """
        # Check for multi-line continuation
        if self.in_multiline:
            if line == "":
                # Empty line ends multi-line input
                self.in_multiline = False
                full_input = "\n".join(self.multiline_buffer)
                self.multiline_buffer = []
                print(f"\033[90m[Processing {len(full_input)} characters of pasted content...]\033[0m")
                return full_input
            else:
                # Add to buffer and continue
                self.multiline_buffer.append(line)
                raise cmd.Continue

        # Check for multi-line start (ends with \)
        if line.endswith("\\"):
            self.in_multiline = True
            self.multiline_buffer = [line[:-1]]  # Remove trailing \
            raise cmd.Continue

        # Detect multi-line paste (error logs, code, etc.)
        # If line contains multiple newlines or looks like paste content
        # and user isn't intentionally executing it, buffer it
        if self._looks_like_paste_content(line):
            # Store in buffer and show continuation prompt
            if not self.in_multiline:
                self.in_multiline = True
                self.multiline_buffer = [line]
                print("\033[90m[Paste mode detected. Press Enter on empty line to submit]\033[0m")
                raise cmd.Continue
            else:
                self.multiline_buffer.append(line)
                raise cmd.Continue

        return line

    def _looks_like_paste_content(self, line: str) -> bool:
        """Detect if line looks like pasted content (error logs, code, etc.).

        Returns True if line:
        - Contains typical error log patterns
        - Has many spaces/tabs (formatted output)
        - Looks like compiler error output
        - Is very long (> 200 chars)
        """
        if not line or len(line) < 30:
            return False

        # Check for error log patterns (more comprehensive)
        error_indicators = [
            "error:",
            "warning:",
            "note:",
            "undefined reference",
            "undeclared",
            "undeclared here",
            "first use in this function",
            "in file included from",
            "from:",
            "at:",
            "line",
            "__check_",
            "__param_",
            "/usr/src/linux",
            "make[",
            "makefile:",
            ".o]",
            "error 1",
            "error 2",
            "entering directory",
            "leaving directory",
            "\\.c:",
            "\\.o:",
            "\\.so:",
            "\\.a:",  # File extensions
            "in function",
            "at top level",
            "from",
            "included by",
            "__builtin_",
            "expected",
            "before",
            "after",
            "each undeclared",
            "reported only once",
            "note: in expansion of",
        ]

        line_lower = line.lower()
        has_error_pattern = any(indicator in line_lower for indicator in error_indicators)

        # Check for typical formatting patterns (multiple spaces/tabs)
        has_formatting = ("  " in line * 3) or ("\t" in line)

        # Check if it's very long (like compiler output)
        is_very_long = len(line) > 200

        # Check for typical compiler output patterns
        has_carrots = ">>" in line and "^" in line and "note:" in line_lower

        return has_error_pattern or has_carrots or (has_formatting and is_very_long)

    def postcmd(self, stop: bool, line: str) -> bool:
        """Hook executed after command processing.

        Save history and check for exit.
        """
        # Save to readline history
        if HAS_READLINE and line.strip():
            readline.add_history(line)

            # Save to file periodically
            if len(readline.get_history_item(readline.get_current_history_length() or 1)) % 10 == 0:
                hist_file = Path.home() / ".spectra_history"
                readline.write_history_file(hist_file)

        return stop

    def onecmd_plus_hooks(self, line: str) -> bool:
        """Process one command with hooks.

        Override to handle all commands via parser.
        """
        # Save history
        if HAS_READLINE and line.strip():
            readline.add_history(line)
            hist_file = Path.home() / ".spectra_history"
            readline.write_history_file(hist_file)

        # Parse command
        cmd = parse_command(line)

        # Route to handler
        if cmd.type == CommandType.HELP:
            self.do_help("")
            return False

        elif cmd.type == CommandType.CONFIG_SHOW:
            self._handle_show_config()
            return False

        elif cmd.type == CommandType.CONFIG_EDIT:
            self._handle_edit_config()
            return False

        elif cmd.type == CommandType.MODEL_SET:
            self._handle_set_model(cmd.value)
            return False

        elif cmd.type == CommandType.PROVIDER_SET:
            self._handle_set_provider(cmd.value)
            return False

        elif cmd.type == CommandType.APIKEY_SET:
            self._handle_set_apikey(cmd.value)
            return False

        elif cmd.type == CommandType.APIURL_SET:
            self._handle_set_api_url(cmd.value)
            return False

        elif cmd.type == CommandType.SHELL_CONFIG:
            self._handle_shell_config(cmd.value)
            return False

        elif cmd.type == CommandType.SESSION_SAVE:
            self._handle_save(cmd.value)
            return False

        elif cmd.type == CommandType.SESSION_LOAD:
            self._handle_load(cmd.value)
            return False

        elif cmd.type == CommandType.SESSION_LIST:
            self._handle_list_sessions()
            return False

        elif cmd.type == CommandType.SESSION_NEW:
            self._handle_new_session()
            return False

        elif cmd.type == CommandType.SESSION_DELETE:
            self._handle_delete_session(cmd.value)
            return False

        elif cmd.type == CommandType.SKILLS_LIST:
            self._handle_list_skills()
            return False

        elif cmd.type == CommandType.TOGGLE:
            self._handle_toggle()
            return False

        elif cmd.type == CommandType.SHELL:
            self._handle_shell(cmd.value)
            return False

        elif cmd.type == CommandType.SKILL:
            return self._handle_skill(cmd.value, cmd.args)

        elif cmd.type == CommandType.PLAN:
            return self._handle_plan(cmd.value)

        elif cmd.type == CommandType.RESEARCH:
            return self._handle_research(cmd.value)

        elif cmd.type == CommandType.NATURAL_LANGUAGE:
            return self._handle_natural_language(cmd.value)

        return False

    def emptyline(self) -> bool:
        """Handle empty line (do nothing)."""
        return False

    def default(self, line: str) -> bool:
        """Handle unhandled commands via parser."""
        return self.onecmd_plus_hooks(line)

    # --- Built-in commands ---

    def do_help(self, arg: str) -> None:
        """Show help message."""
        print(get_help_text())

    def do_exit(self, arg: str) -> bool:
        """Exit the REPL."""
        print()
        self.ui.print_info("Goodbye!")
        print()
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the REPL."""
        return self.do_exit(arg)

    def do_clear(self, arg: str) -> None:
        """Clear the screen."""
        os.system("clear" if os.name == "posix" else "cls")

    # --- Tab completion ---

    def complete(self, text: str, state: int) -> str | None:
        """Override for better TAB completion.

        This is called repeatedly by readline with increasing state
        until we return None.
        """
        if not HAS_READLINE:
            return None

        if state == 0:
            # First call - generate completions
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()

            # Generate context-appropriate completions
            self.completion_matches = self._generate_completions(text, line, begidx, endidx)

            # If there are multiple matches, show categorized display
            if len(self.completion_matches) > 1 and line.strip().startswith("/"):
                self._show_categorized_completions(self.completion_matches)

        try:
            return self.completion_matches[state]
        except (IndexError, AttributeError):
            return None

    def _show_categorized_completions(self, matches: list[str]) -> None:
        """Show completions grouped by category."""
        from .shell_ui import Colors

        # Separate into categories
        system = []
        session = []
        config = []
        skills = []

        for m in matches:
            if m in CONFIG_CMD_NAMES:
                config.append(m)
            elif m in SESSION_CMD_NAMES:
                session.append(m)
            elif m in SYSTEM_CMD_NAMES:
                system.append(m)
            elif m.startswith("/"):
                skills.append(m)

        # Show categorized display
        print()  # New line for clean display

        if skills:
            print(f"{Colors.CYAN}Skills:{Colors.RESET}")
            print("  " + "  ".join(skills[:8]))  # Show first 8
            if len(skills) > 8:
                print(f"  ... and {len(skills) - 8} more skills")
            print()

        if config:
            print(f"{Colors.YELLOW}Config:{Colors.RESET}")
            print("  " + "  ".join(config))
            print()

        if session:
            print(f"{Colors.GREEN}Session:{Colors.RESET}")
            print("  " + "  ".join(session))
            print()

        if system:
            print(f"{Colors.MAGENTA}System:{Colors.RESET}")
            print("  " + "  ".join(system))
            print()

        # Redraw prompt
        print(f"{Colors.CYAN}spectra>{Colors.RESET} {readline.get_line_buffer()}", end="", flush=True)

    def completenames(self, text: str, *ignored: list[str]) -> list[str]:
        """Override cmd.Cmd's completenames for better slash command completion.

        This is called by cmd.Cmd's internal completion system.
        """
        # Use our generation logic
        return self._generate_completions(text, text, 0, len(text))

    def _generate_completions(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Generate completions based on context.

        Args:
            text: The word being completed
            line: Full input line
            begidx: Start index of text in line
            endidx: End index of text in line

        Returns:
            List of possible completions
        """
        # Empty line - suggest all slash commands
        if not line.strip():
            return [f"/{s}" for s in self.controller.skill_slugs[:10]]

        # Parse context
        words = line.split()
        if not words:
            return [f"/{s}" for s in self.controller.skill_slugs[:10]]

        first_word = words[0]

        # Session command: /load - suggest session IDs
        if first_word == "/load" and len(words) >= 1:
            if len(words) == 1 or (len(words) == 2 and not text):
                # Suggest session IDs
                sessions = self.controller.list_sessions()
                return [s["id"] for s in sessions]

        # Shell command: !command - suggest common shell commands
        if line.startswith("!"):
            return self._complete_shell_command(text)

        # Slash command completion
        if line.startswith("/"):
            return self._complete_slash_command(text, line, words)

        return []

    def _complete_slash_command(self, text: str, line: str, words: list[str]) -> list[str]:
        """Complete slash commands and their arguments.

        Args:
            text: Text being completed
            line: Full line
            words: Split words

        Returns:
            List of completions
        """
        # Check if we're completing the first word (the command itself)
        if len(words) == 1 or (len(words) == 2 and not text):
            # System/Session/Config commands from command_parser
            built_in_cmds = ALL_SLASH_COMMANDS

            # Skill commands
            skill_cmds = [f"/{s}" for s in self.controller.skill_slugs]

            all_cmds = built_in_cmds + skill_cmds

            # Filter by prefix
            if text:
                return [c for c in all_cmds if c.startswith(text)]
            return all_cmds

        # Check if we're completing after a specific command
        cmd = words[0]

        # After /skill - suggest nothing (let user type skill name)
        if cmd.startswith("/") and cmd not in ["/plan", "/research"]:
            # Might be completing a skill argument
            return []

        return []

    def _complete_shell_command(self, text: str) -> list[str]:
        """Complete shell commands after !.

        Args:
            text: Text being completed (without !)

        Returns:
            List of shell command completions
        """
        # Common shell commands
        common_cmds = [
            "ls",
            "cd",
            "pwd",
            "cat",
            "grep",
            "find",
            "mkdir",
            "rm",
            "cp",
            "mv",
            "chmod",
            "ps",
            "kill",
            "top",
            "htop",
            "git",
            "npm",
            "pip",
            "python",
            "curl",
            "wget",
            "ssh",
            "scp",
        ]

        # Complete by subcommand
        parts = text.split()
        if len(parts) == 1:
            # Completing the command itself
            prefix = parts[0] if parts[0] else ""
            return [c for c in common_cmds if c.startswith(prefix)]

        # Check for file path completion in shell commands
        # Commands that take file paths
        file_cmds = ["cat", "grep", "find", "ls", "cd", "rm", "cp", "mv"]
        if parts[0] in file_cmds and len(parts) >= 2:
            return self._complete_file_paths(text)

        # Could add subcommand completion here (e.g., git commit, git push)
        return []

    def _complete_file_paths(self, text: str) -> list[str]:
        """Complete file paths.

        Args:
            text: Partial file path

        Returns:
            List of matching files/directories
        """
        try:
            import glob

            # Expand user home directory
            if text.startswith("~"):
                text = os.path.expanduser(text)

            # Get directory part and file prefix
            if "/" in text:
                dir_part = os.path.dirname(text) or "."
                file_prefix = os.path.basename(text)
            else:
                dir_part = "."
                file_prefix = text

            # Find matches
            pattern = os.path.join(dir_part, f"{file_prefix}*")
            matches = glob.glob(pattern)

            # Format results
            results = []
            for match in matches:
                # Add trailing slash for directories
                if os.path.isdir(match):
                    match = match + "/"
                results.append(match)

            return results
        except Exception:
            return []

    def completedefault(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Default completion handler (fallback for readline).

        This is called by cmd.Cmd when complete() is not overridden.
        We override complete() above, so this is just a fallback.
        """
        return self._generate_completions(text, line, begidx, endidx)

    # --- Command handlers ---

    def _handle_save(self, name: str) -> bool:
        """Handle /save command."""
        if not name:
            import datetime

            name = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        try:
            session_id = self.controller.session.id
            _path = self.controller.save_session(name)
            self.ui.print_success(f"Session saved: {name} (ID: {session_id[:8]})")
            self.ui.print_info(f"Use '/load {name}' or '/load {session_id[:8]}' to reload")
            return False
        except Exception as e:
            self.ui.print_error(f"Failed to save: {e}")
            return False

    def _handle_load(self, session_id: str) -> bool:
        """Handle /load command."""
        if not session_id:
            self.ui.print_error("Usage: /load <id_or_description>")
            self.ui.print_info("Use /sessions to list saved sessions")
            return False

        session = self.controller.load_session(session_id)
        if session:
            desc = session.metadata.get("description", session.id[:8])
            msg_count = len(session.messages)

            self.ui.print_success(f"Session loaded: {desc} ({session.id[:8]})")

            # Display loaded messages
            if msg_count > 0:
                self.ui.print_info(f"Loaded {msg_count} messages from session history:")
                print()

                for msg in session.messages:
                    if msg.role == "user":
                        print(f"{self.ui._color('spectra> ', Colors.CYAN)}{msg.content}")
                    elif msg.role == "assistant":
                        print(f"{self.ui._color('🤖 Spectra:', Colors.GREEN)} {msg.content}")
                    elif msg.role == "system":
                        print(f"{self.ui._color('System:', Colors.DIM)} {msg.content}")

                    # Handle tool calls
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            print(f"  {self.ui._color('Tool Call:', Colors.YELLOW)} {tc.name}")

                    # Handle tool results
                    if msg.tool_results:
                        for tr in msg.tool_results:
                            if tr.is_error:
                                print(f"  {self.ui._color(f'Error: {tr.name}', Colors.RED)}")
                            else:
                                result_preview = (tr.content or "")[:200]
                                if len(tr.content or "") > 200:
                                    result_preview += "... (truncated)"
                                print(f"  {self.ui._color(f'Result: {tr.name}', Colors.BLUE)}: {result_preview}")

                print()
            else:
                self.ui.print_info("Session has no saved messages (empty session)")
        else:
            self.ui.print_error(f"Session not found: {session_id}")
            self.ui.print_info("Use /sessions to list available sessions")
        return False

    def _handle_list_sessions(self) -> bool:
        """Handle /sessions command."""
        sessions = self.controller.list_sessions()

        if not sessions:
            self.ui.print_info("No saved sessions")
            return False

        print()
        print(self.ui._bold("Saved Sessions:"))
        print("  Usage: /load <id> or /load <description>")
        print("         /delete <id> or /delete <description>")
        print()
        for s in sessions:
            print(
                f"  {self.ui._color(s['id'][:8], Colors.CYAN)}: {self.ui._color(s['description'], Colors.YELLOW)} ({s['message_count']} messages)"
            )
        print()

        return False

    def _handle_delete_session(self, session_id: str) -> bool:
        """Handle /delete command."""
        if not session_id:
            self.ui.print_error("Usage: /delete <id_or_description>")
            self.ui.print_info("Use /sessions to list saved sessions")
            return False

        # Show what will be deleted
        sessions = self.controller.list_sessions()
        target_desc = None
        target_id = None

        for s in sessions:
            sid = s.get("id", "")
            desc = s.get("description", "")
            if session_id.lower() in desc.lower() or session_id == sid[: len(session_id)]:
                target_desc = desc
                target_id = sid
                break

        if target_id:
            self.ui.print_warning(f"Deleting session: {target_desc} ({target_id[:8]})")

            # Confirm deletion
            try:
                response = input("Are you sure? (y/N): ").strip().lower()
                if response not in ["y", "yes"]:
                    self.ui.print_info("Deletion cancelled")
                    return False
            except (EOFError, KeyboardInterrupt):
                self.ui.print_info("Deletion cancelled")
                return False

            if self.controller.delete_session(session_id):
                self.ui.print_success(f"Session deleted: {target_desc} ({target_id[:8]})")
            else:
                self.ui.print_error(f"Failed to delete session: {session_id}")
        else:
            self.ui.print_error(f"Session not found: {session_id}")
            self.ui.print_info("Use /sessions to list available sessions")

        return False

    def _handle_new_session(self) -> bool:
        """Handle /new command."""
        self.controller.new_session()
        self.ui.print_success("New session started")
        return False

    def _handle_list_skills(self) -> bool:
        """Handle /skills command."""
        skills = self.controller.list_skills()

        print()
        print(self.ui._bold("Available Skills:"))
        for skill in skills:
            slug = skill["slug"]
            _name = skill["name"]
            desc = skill["description"]

            # Show full description
            print(f"  {self.ui._color(f'/{slug}', Colors.CYAN)}: {desc}")
        print()

        return False

    def _handle_shell(self, command: str) -> bool:
        """Handle !shell command."""
        if not command:
            self.ui.print_error("Usage: !<command>")
            return False

        result = self.controller.execute_shell_command(command)
        if result:
            print(result)

        return False

    def _handle_toggle(self) -> bool:
        """Handle /toggle command - collapse/expand last tool result."""
        self.ui.toggle_collapse()
        return False

    def _handle_skill(self, slug: str, args: str) -> bool:
        """Handle /skill command."""
        # Get skill to build prompt
        if not self.controller._runtime_init_done.is_set():
            self.controller._runtime_init_done.wait(timeout=10.0)

        skill = self.controller._skill_registry.get(slug)
        if not skill:
            available = ", ".join(self.controller._skill_registry.list_slugs()[:10])
            self.ui.print_error(f"Unknown skill: /{slug}. Available: {available}...")
            return False

        # Build prompt from skill body + args
        prompt = skill.body or skill.description or ""
        if args:
            prompt = f"{args}\n\n{prompt}"

        # Start agent with prompt
        error = self.controller.start_agent(prompt)
        if error:
            self.ui.print_error(error)
            return False

        # Stream agent output via polling (like IDA Pro)
        self._stream_agent_output()

        return False

    def _handle_plan(self, prompt: str) -> bool:
        """Handle /plan command."""
        error = self.controller.start_plan_mode(prompt)
        if error:
            self.ui.print_error(error)
            return False

        # Stream agent output via polling
        self._stream_agent_output()

        return False

    def _handle_research(self, prompt: str) -> bool:
        """Handle /research command."""
        error = self.controller.start_research_mode(prompt)
        if error:
            self.ui.print_error(error)
            return False

        # Stream agent output via polling
        self._stream_agent_output()

        return False

    def _handle_natural_language(self, text: str) -> bool:
        """Handle natural language input."""
        if not text:
            return False

        # Start agent with prompt
        error = self.controller.start_agent(text)
        if error:
            self.ui.print_error(error)
            return False

        # Stream agent output via polling
        self._stream_agent_output()

        return False

    def _stream_agent_output(self) -> None:
        """Stream agent output by polling events (like IDA Pro)."""
        import time

        runner = self.controller.get_runner()
        if not runner:
            self.ui.print_error("Failed to get agent runner")
            return

        # Store runner for cancellation via Ctrl+C
        self._agent_runner = runner

        try:
            # Poll events until agent finishes completely (sentinel None received)
            pending_approvals = []  # Queue for approval requests waiting to be shown
            showing_approval = False  # Track if we're currently showing an approval prompt
            output_buffer = []  # Buffer output during shell approval

            while True:
                event = self.controller.get_event(timeout=0.1)
                if event:
                    # Check if we're in shell command approval - buffer output
                    from .tools.shell_tools import is_in_shell_approval

                    in_shell_approval = is_in_shell_approval()

                    # Always show subagent events (never buffer them)
                    if event.type in (
                        TurnEventType.SUBAGENT_SPAWNED,
                        TurnEventType.SUBAGENT_PROGRESS,
                        TurnEventType.SUBAGENT_COMPLETED,
                        TurnEventType.SUBAGENT_FAILED,
                    ):
                        # Don't buffer subagent events
                        pass
                    elif in_shell_approval and event.type not in (
                        TurnEventType.TOOL_APPROVAL_REQUEST,
                        TurnEventType.USER_QUESTION,
                        TurnEventType.ERROR,
                    ):
                        # Buffer non-approval events during shell approval
                        output_buffer.append(event)
                        log_debug(f"Buffered event during shell approval: {event.type}")
                        continue

                    # Flush any buffered output
                    if output_buffer and not in_shell_approval:
                        log_debug(f"Flushing {len(output_buffer)} buffered events")
                        for buffered_event in output_buffer:
                            for _ in self.ui._handle_event(buffered_event, None):
                                pass
                        output_buffer.clear()

                    # Subagent event tracking - MUST BE BEFORE ui._handle_event to avoid duplicates
                    if event.type == TurnEventType.SUBAGENT_SPAWNED:
                        # Extract detailed subagent information from metadata
                        agent_id = event.metadata.get("agent_id", event.text or "unknown")
                        agent_name = event.text or "Unnamed Agent"
                        agent_type = event.metadata.get("agent_type", "general")
                        task = event.metadata.get("task", "Unknown task")

                        # Store in active subagents tracking
                        self._active_subagents[agent_id] = {
                            "name": agent_name,
                            "type": agent_type,
                            "task": task,
                            "start_time": __import__("time").time(),
                            "turn_count": 0,
                        }

                        # Display detailed spawn information for EVERY subagent
                        print()
                        print(self.ui._color(f"🔄 Subagent spawned [{agent_id}]", Colors.CYAN))
                        print(f"  Name: {self.ui._bold(agent_name)}")
                        print(f"  Type: {self.ui._color(agent_type, Colors.DIM)}")
                        print(f"  Task: {task[:120]}{'...' if len(task) > 120 else ''}")
                        print()

                        # Show active subagent count
                        active_count = len(self._active_subagents)
                        if active_count > 1:
                            print(self.ui._color(f"  [Active subagents: {active_count}]", Colors.DIM))
                            print()

                        # IMPORTANT: Skip shell_ui handler to avoid duplicate messages
                        continue

                    elif event.type == TurnEventType.SUBAGENT_PROGRESS:
                        # Extract progress information
                        agent_id = event.metadata.get("agent_id", "unknown")
                        turn_count = event.metadata.get("turn_count", 0)
                        progress_text = event.text or ""

                        # Update turn count in tracking
                        if agent_id in self._active_subagents:
                            self._active_subagents[agent_id]["turn_count"] = turn_count

                            # Show periodic progress updates
                            if turn_count > 0 and turn_count % 5 == 0:
                                subagent = self._active_subagents[agent_id]
                                elapsed = __import__("time").time() - subagent["start_time"]
                                print(
                                    self.ui._color(
                                        f"  [{agent_id[:8]}] Progress: {turn_count} turns ({elapsed:.1f}s)", Colors.DIM
                                    )
                                )

                        # Show progress text if provided
                        if progress_text:
                            print(self.ui._color(f"  [{agent_id[:8]}] {progress_text[:60]}...", Colors.DIM))

                        # Skip shell_ui handler for progress events
                        continue

                    elif event.type == TurnEventType.SUBAGENT_COMPLETED:
                        # Extract completion details
                        agent_id = event.metadata.get("agent_id", "unknown")
                        agent_name = event.metadata.get("name", event.text or "Unknown")
                        summary = event.text or "Completed"
                        turn_count = event.metadata.get("turn_count", 0)
                        elapsed = event.metadata.get("elapsed", 0.0)

                        # Remove from active tracking
                        if agent_id in self._active_subagents:
                            del self._active_subagents[agent_id]

                        # Display detailed completion information
                        print()
                        print(self.ui._color(f"✓ Subagent completed [{agent_id}]", Colors.GREEN))
                        print(f"  Name: {self.ui._bold(agent_name)}")
                        print(f"  Turns: {turn_count}")
                        if elapsed > 0:
                            print(f"  Time: {elapsed:.1f}s")
                        print(f"  Result: {summary[:100]}{'...' if len(summary) > 100 else ''}")
                        print()

                        # Skip shell_ui handler for completed events
                        continue

                    elif event.type == TurnEventType.SUBAGENT_FAILED:
                        # Extract failure details
                        agent_id = event.metadata.get("agent_id", "unknown")
                        agent_name = event.metadata.get("name", "Unknown Agent")
                        error = event.error or "Unknown error"

                        # Remove from active tracking
                        if agent_id in self._active_subagents:
                            del self._active_subagents[agent_id]

                        # Display detailed failure information
                        print()
                        print(self.ui._color(f"✗ Subagent failed [{agent_id}]", Colors.RED))
                        print(f"  Name: {self.ui._bold(agent_name)}")
                        print(f"  Error: {error[:100]}{'...' if len(error) > 100 else ''}")
                        print()

                        # Skip shell_ui handler for failed events
                        continue

                    # Handle the event
                    for _ in self.ui._handle_event(event, None):
                        pass

                    if event.type == TurnEventType.SUBAGENT_PROGRESS:
                        # Extract progress information
                        agent_id = event.metadata.get("agent_id", "unknown")
                        turn_count = event.metadata.get("turn_count", 0)
                        progress_text = event.text or ""

                        # Update turn count in tracking
                        if agent_id in self._active_subagents:
                            self._active_subagents[agent_id]["turn_count"] = turn_count

                            # Show periodic progress updates
                            if turn_count > 0 and turn_count % 5 == 0:
                                subagent = self._active_subagents[agent_id]
                                elapsed = __import__("time").time() - subagent["start_time"]
                                print(
                                    self.ui._color(
                                        f"  [{agent_id[:8]}] Progress: {turn_count} turns ({elapsed:.1f}s)", Colors.DIM
                                    )
                                )

                        # Show progress text if provided
                        if progress_text:
                            print(self.ui._color(f"  [{agent_id[:8]}] {progress_text[:60]}...", Colors.DIM))

                    elif event.type == TurnEventType.SUBAGENT_COMPLETED:
                        # Extract completion details
                        agent_id = event.metadata.get("agent_id", "unknown")
                        agent_name = event.metadata.get("name", event.text or "Unknown")
                        summary = event.text or "Completed"
                        turn_count = event.metadata.get("turn_count", 0)
                        elapsed = event.metadata.get("elapsed", 0.0)

                        # Remove from active tracking
                        if agent_id in self._active_subagents:
                            del self._active_subagents[agent_id]

                        # Display detailed completion information
                        print()
                        print(self.ui._color(f"✓ Subagent completed [{agent_id}]", Colors.GREEN))
                        print(f"  Name: {self.ui._bold(agent_name)}")
                        print(f"  Turns: {turn_count}")
                        if elapsed > 0:
                            print(f"  Time: {elapsed:.1f}s")
                        print(f"  Result: {summary[:100]}{'...' if len(summary) > 100 else ''}")
                        print()

                    elif event.type == TurnEventType.SUBAGENT_FAILED:
                        # Extract failure details
                        agent_id = event.metadata.get("agent_id", "unknown")
                        agent_name = event.metadata.get("name", "Unknown Agent")
                        error = event.error or "Unknown error"

                        # Remove from active tracking
                        if agent_id in self._active_subagents:
                            del self._active_subagents[agent_id]

                        # Display detailed failure information
                        print()
                        print(self.ui._color(f"✗ Subagent failed [{agent_id}]", Colors.RED))
                        print(f"  Name: {self.ui._bold(agent_name)}")
                        print(f"  Error: {error[:100]}{'...' if len(error) > 100 else ''}")
                        print()

                    # Check for tool approval
                    if event.type == TurnEventType.TOOL_APPROVAL_REQUEST:
                        # If we're already showing an approval prompt, queue this one
                        if showing_approval:
                            pending_approvals.append(event)
                            print()  # Add spacing
                            print(
                                self.ui._color(
                                    f"[Queued: {len(pending_approvals)} more approval(s) waiting...]", Colors.DIM
                                )
                            )
                            continue  # Don't show prompt yet, process next event

                        # Parse tool info
                        tool_name = event.tool_name
                        tool_args = event.tool_args

                        # Show approval prompt
                        print()
                        print(self.ui._color("⚠️  Tool approval required", Colors.YELLOW))
                        print()
                        print(self.ui._bold("Tool Call:"))
                        print(f"  {self.ui._color('Tool:', Colors.CYAN)} {tool_name}")

                        # Show arguments
                        try:
                            import json

                            args = json.loads(tool_args) if tool_args else {}
                            if args:
                                print(f"  {self.ui._color('Arguments:', Colors.CYAN)}")
                                for key, value in args.items():
                                    print(f"    {key}: {value}")
                        except Exception:
                            pass

                        # Mark as showing approval and get user decision
                        showing_approval = True
                        print()
                        decision = ""
                        max_attempts = 3
                        attempt = 0
                        while decision not in ("y", "n", "a") and attempt < max_attempts:
                            self._flush_input()  # Clear any buffered ENTER keystrokes
                            user_input = self._safe_input(
                                self.ui._color("Approve? (y/n/a=always): ", Colors.YELLOW),
                                default="n",
                                timeout=60.0,  # 60 second timeout
                            ).lower()
                            if user_input:
                                decision = user_input[0]  # Take first character
                            else:
                                attempt += 1
                                if attempt >= max_attempts:
                                    decision = "n"  # Default to no

                        # Submit decision
                        runner.agent_loop.submit_tool_approval(decision)

                        if decision == "n":
                            print()
                            print(self.ui._color("❌ Tool execution denied by user", Colors.RED))

                        # Clear showing approval flag
                        showing_approval = False

                        # If there are queued approvals, show a message
                        if pending_approvals:
                            print()
                            print(
                                self.ui._color(
                                    f"ℹ️  {len(pending_approvals)} more approval(s) in queue - will be shown next",
                                    Colors.CYAN,
                                )
                            )

                    # Check for user question
                    if event.type == TurnEventType.USER_QUESTION:
                        question = event.text or ""
                        options = event.metadata.get("options", []) if event.metadata else []
                        allow_text = event.metadata.get("allow_text", False) if event.metadata else False

                        print()
                        print(self.ui._bold("❓ Question:"), question)

                        if options:
                            print(self.ui._color("Options:", Colors.CYAN))
                            for i, opt in enumerate(options, 1):
                                print(f"  {i}. {opt}")
                            if allow_text:
                                print(f"  {len(options) + 1}. Other (custom input)")

                        # Get user answer
                        answer = ""
                        max_attempts = 3
                        attempt = 0
                        while attempt < max_attempts:
                            self._flush_input()  # Clear any buffered ENTER keystrokes
                            user_input = self._safe_input(
                                self.ui._color("Your choice: ", Colors.YELLOW),
                                default="",
                                timeout=60.0,  # 60 second timeout
                            )

                            if not user_input:
                                attempt += 1
                                if attempt >= max_attempts:
                                    answer = ""
                                    break
                                continue

                            # Check if it's a number selection
                            if options and user_input.isdigit():
                                idx = int(user_input) - 1
                                if 0 <= idx < len(options):
                                    answer = options[idx]
                                    break
                            elif allow_text:
                                # Allow custom text input
                                answer = user_input
                                break
                            elif not options:
                                # No options, just return the text
                                answer = user_input
                                break
                            else:
                                attempt += 1

                        # Submit answer to agent loop
                        runner.agent_loop.submit_user_answer(answer)
                        print(f"  Answered: {answer}")

                    # Check for error - still consume remaining events before stopping
                    if event.type == TurnEventType.ERROR:
                        # Error shown, wait for sentinel
                        pass
                else:
                    # No event or sentinel (None) - check if agent is still running
                    # If not running and no event, this is the sentinel signaling completion
                    if not self.controller.is_agent_running:
                        break

                # Small sleep to prevent busy-waiting
                time.sleep(0.01)

        except KeyboardInterrupt:
            # User pressed Ctrl+C - agent already cancelled by signal handler
            print()  # Add newline after the interrupt message
        finally:
            # Clear runner reference when done
            self._agent_runner = None

    def _handle_edit_config(self) -> bool:
        """Handle /config_edit command - open config in text editor."""
        import subprocess

        # Get config path from controller
        config_path = self.controller.config.config_path

        # Try common editors in order of preference
        editors = []
        # Check for common editors
        for editor in ["code", "vim", "vi", "nano"]:
            try:
                subprocess.run(["which", editor], capture_output=True, check=True)
                editors.append(editor)
                break
            except subprocess.CalledProcessError:
                continue

        if not editors:
            self.ui.print_error("No text editor found. Please install vim, nano, or VS Code.")
            return False

        editor = editors[0]

        try:
            print(f"\nOpening config in {editor}...")
            print(f"Config path: {config_path}")
            print("Save and exit the editor when done.\n")

            # Open editor
            subprocess.run([editor, config_path])

            # Reload config after editing
            print("\nReloading configuration...")
            from ..core.config import SpectraConfig

            self.controller.config = SpectraConfig.load()

            print("Configuration reloaded successfully.")
            return False
        except Exception as e:
            self.ui.print_error(f"Failed to open editor: {e}")
            return False

    def _handle_set_api_url(self, api_url: str) -> bool:
        """Handle /apiurl command - set API base URL."""
        if not api_url:
            # Show current API URL
            config = self.controller.get_config()
            print()
            print(self.ui._bold(f"Current API URL: {config['api_base'] or 'Default'}"))
            print()
            return False

        # Update API URL
        self.controller.config.provider.api_base = api_url
        self.controller.config.save()

        print()
        print(f"API URL updated to: {api_url}")
        print()
        return False

    def _handle_show_config(self) -> bool:
        """Handle /config command."""
        config = self.controller.get_config()

        print()
        print(self.ui._bold("Current Configuration:"))
        print(f"  Provider: {self.ui._color(config['provider'], Colors.CYAN)}")
        print(f"  Model:    {self.ui._color(config['model'], Colors.CYAN)}")
        print(f"  API Base: {config['api_base']}")
        print(
            f"  API Key:  {self.ui._color(config['api_key_preview'], Colors.GREEN if config['has_api_key'] else Colors.YELLOW)}"
        )
        print(
            f"  Shell Auto-Approve Limit: {self.ui._color(str(getattr(self.controller.config, 'shell_auto_approve_limit', 10)), Colors.CYAN)}"
        )
        print()

        return False

    def _handle_shell_config(self, value: str) -> bool:
        """Handle /autoapprove_limit command."""
        if not value:
            # Show current limit
            current_limit = getattr(self.controller.config, "shell_auto_approve_limit", 10)
            print()
            print(self.ui._bold("Shell Auto-Approve Limit:"))
            print(f"  Current: {self.ui._color(str(current_limit), Colors.CYAN)}")
            print()
            print(self.ui._color("Usage: /autolimit <N> (0 = disable auto-approve)", Colors.DIM))
            print()
            return False

        try:
            new_limit = int(value)
            if new_limit < 0:
                self.ui.print_error("Limit must be >= 0")
                return False

            # Update config
            self.controller.config.shell_auto_approve_limit = new_limit
            self.controller.config.save()

            print()
            if new_limit == 0:
                self.ui.print_success("Auto-approve disabled (limit set to 0)")
            else:
                self.ui.print_success(f"Auto-approve limit set to {new_limit} commands")
            print()

            # Note: This won't affect the current session's approval state immediately
            # It will take effect when the CLI is restarted or approval callback is re-initialized
            print(self.ui._color("Note: Restart CLI for changes to take full effect.", Colors.YELLOW))
            print()

        except ValueError:
            self.ui.print_error(f"Invalid limit: {value}. Must be a number.")
        return False

    def _handle_set_model(self, model_name: str) -> bool:
        """Handle /model command.

        If no model name provided, show available models.
        """
        if not model_name:
            # Show available models
            models = self.controller.list_available_models()
            config = self.controller.get_config()

            print()
            print(self.ui._bold(f"Available Models for {config['provider'].upper()}:"))
            print()

            if not models:
                print(f"  {self.ui._color('No models found', Colors.YELLOW)}")
                print()
                return False

            for i, model in enumerate(models, 1):
                model_id = model["id"]
                model_name_display = model["name"]
                current = " (current)" if model_id == config["model"] else ""
                print(f"  {i}. {self.ui._color(model_id, Colors.CYAN)}: {model_name_display}{current}")

            print()
            print(self.ui._color("Usage: /model <model_id>", Colors.DIM))
            print()
            return False

        # Set the model
        error = self.controller.set_model(model_name)
        if error:
            self.ui.print_error(error)
        else:
            self.ui.print_success(f"Model changed to: {model_name}")

        return False

    def _handle_set_provider(self, provider_name: str) -> bool:
        """Handle /provider command."""
        if not provider_name:
            self.ui.print_error("Usage: /provider <provider_name>")
            self.ui.print_info("Valid providers: anthropic, openai, gemini, ollama")
            return False

        error = self.controller.set_provider(provider_name)
        if error:
            self.ui.print_error(error)
        else:
            config = self.controller.get_config()
            self.ui.print_success(f"Provider changed to: {provider_name}")
            self.ui.print_info(f"Default model: {config['model']}")

        return False

    def _handle_set_apikey(self, api_key: str) -> bool:
        """Handle /apikey command."""
        if not api_key:
            self.ui.print_error("Usage: /apikey <your_api_key>")
            return False

        error = self.controller.set_api_key(api_key)
        if error:
            self.ui.print_error(error)
        else:
            self.ui.print_success("API key updated")

        return False

"""CLI session controller - Shell-specific session management.

Extends SessionControllerBase for CLI environment without disrupting IDA Pro plugin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

from ..core.config import SpectraConfig
from ..core.logging import log_debug, log_info
from ..state.history import SessionHistory
from ..state.session import SessionState
from ..tools.registry import ToolRegistry
from ..ui.session_controller_base import SessionControllerBase


# CLI-specific database instance ID (separate from IDA/BNDB)
_CLI_DB_INSTANCE_ID = "spectra-cli"


def _flush_input() -> None:
    """Flush any pending input from stdin buffer.

    This prevents buffered ENTER keystrokes during AI output from
    being immediately consumed by subsequent input() calls.
    """
    try:
        import select
        # Check if there's pending input
        while select.select([sys.stdin], [], [], 0.0)[0]:
            # Read and discard pending input
            sys.stdin.readline()
    except:
        # If flushing fails, just continue
        pass


def create_cli_tool_registry() -> ToolRegistry:
    """Create tool registry for CLI.

    CLI has different capabilities than IDA/Binary Ninja:
    - No decompiler
    - No database access
    - File system access
    - Shell command execution
    """
    registry = ToolRegistry()

    # Declare CLI capabilities (no IDA-specific features)
    registry.set_capabilities({
        "hexrays": False,
        "idb_struct": False,
        "database": False,
        "ida_pro": False,
        "binary_ninja": False,
        "cli_mode": True,
        "filesystem": True,
        "shell": True,
        "source_code_analysis": True,
    })

    return registry


class CLISessionController(SessionControllerBase):
    """CLI-specific session controller.

    Extends SessionControllerBase for shell environment:
    - No IDB/BNDB path (standalone mode)
    - CLI-specific tool registry (file ops, shell commands)
    - Separate session storage (~/.spectra/sessions/cli/)
    - No UI dependencies (pure shell)

    The controller manages:
    - Session lifecycle (create, save, load, list)
    - Agent lifecycle (start, cancel, events)
    - Tool registry (CLI-specific tools)
    - Skill registry (all 39 built-in skills)
    """

    def __init__(self, config: SpectraConfig | None = None):
        """Initialize CLI session controller.

        Args:
            config: SpectraConfig instance (uses default if None)
        """
        if config is None:
            config = SpectraConfig.load_or_create()

        # Initialize base class with CLI-specific parameters
        super().__init__(
            config=config,
            tool_registry_factory=create_cli_tool_registry,
            database_path_getter=lambda: "",  # No IDB path for CLI
            host_name="cli",
        )

        log_info("CLI session controller initialized")

    def _ensure_db_instance_id(self) -> str:
        """Override to return fixed CLI instance ID.

        For CLI, we use a fixed ID instead of per-database IDs.
        """
        return _CLI_DB_INSTANCE_ID

    def _initialize_runtime(self) -> None:
        """Override to load CLI-specific tools."""
        super()._initialize_runtime()

        # Load CLI tools after base initialization
        try:
            from ..cli.tools import file_tools, shell_tools
            self._tool_registry.register_module(file_tools)
            self._tool_registry.register_module(shell_tools)
            log_info("CLI tools registered")
        except ImportError as e:
            log_debug(f"CLI tools not available: {e}")

        # Set up shell approval callback for user confirmation
        try:
            self.set_shell_approval_callback()
            log_info("Shell approval callback configured")
        except Exception as e:
            log_debug(f"Failed to set shell approval callback: {e}")

    # --- Session Management ---

    def save_session(self, name: str) -> str:
        """Save current session with a name.

        Args:
            name: Session name/description

        Returns:
            Path where session was saved
        """
        session = self.session

        # Add description to metadata
        session.metadata["description"] = name

        history = SessionHistory(self.config)
        path = history.save_session(session, description=name)

        log_info(f"Session saved: {path}")
        return path

    def load_session(self, session_id: str) -> SessionState | None:
        """Load session by ID or description.

        Args:
            session_id: Session ID or description to load

        Returns:
            Loaded SessionState or None if not found
        """
        history = SessionHistory(self.config)
        try:
            # Try loading by ID first
            session = history.load_session(session_id)
            if session:
                self._sessions[self._active_tab_id] = session
                log_info(f"Session loaded: {session_id}")
                return session

            # If not found by ID, search by description
            sessions = history.list_sessions(
                idb_path="",  # No IDB for CLI
                db_instance_id=_CLI_DB_INSTANCE_ID,
            )

            # Find session by description (partial match allowed)
            for s in sessions:
                desc = s.get("description", "")
                sid = s.get("id", "")

                # Match by description (case-insensitive, partial match)
                if session_id.lower() in desc.lower() or session_id == sid[:len(session_id)]:
                    session = history.load_session(sid)
                    if session:
                        self._sessions[self._active_tab_id] = session
                        log_info(f"Session loaded by description: {desc} ({sid[:8]})")
                        return session

            log_debug(f"Session not found: {session_id}")
        except Exception as e:
            log_debug(f"Failed to load session {session_id}: {e}")

        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete session by ID or description.

        Args:
            session_id: Session ID or description to delete

        Returns:
            True if deleted, False if not found
        """
        history = SessionHistory(self.config)

        # Try to find the session ID first
        sessions = history.list_sessions(
            idb_path="",  # No IDB for CLI
            db_instance_id=_CLI_DB_INSTANCE_ID,
        )

        # Find session by ID or description
        target_session_id = None
        for s in sessions:
            sid = s.get("id", "")
            desc = s.get("description", "")

            # Match by exact ID, partial ID, or description
            if session_id == sid or session_id == sid[:len(session_id)] or session_id.lower() in desc.lower():
                target_session_id = sid
                break

        if target_session_id:
            return history.delete_session(target_session_id)

        log_debug(f"Session not found for deletion: {session_id}")
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all CLI sessions.

        Returns:
            List of session info dicts with keys: id, description, timestamp, message_count
        """
        history = SessionHistory(self.config)
        sessions = history.list_sessions(
            idb_path="",  # No IDB for CLI
            db_instance_id=_CLI_DB_INSTANCE_ID,
        )

        # Format session info (entries are already dicts from JSON)
        result = []
        for s in sessions:
            result.append({
                "id": s.get("id", ""),
                "description": s.get("description", "Unnamed"),
                "timestamp": s.get("created_at", 0),
                "message_count": s.get("message_count", 0),
            })

        return result

    def new_session(self) -> None:
        """Start a new session (clear current)."""
        # Save current session if it has messages
        session = self.session
        if session and session.messages:
            try:
                self.save_session("auto-saved")
            except Exception:
                pass

        # Create new session
        self._sessions[self._active_tab_id] = SessionState(
            provider_name=self.config.provider.name,
            model_name=self.config.provider.model,
            idb_path="",
            db_instance_id=_CLI_DB_INSTANCE_ID,
        )

        log_info("New session started")

    # --- Skill Invocation ---

    def start_agent(self, user_message: str) -> str | None:
        """Override to add CLI-specific context to all agent conversations.

        Args:
            user_message: User's message

        Returns:
            Error message if failed, None otherwise
        """
        # Add CLI context to every message
        cli_context = """Environment: Spectra CLI (command-line interface)
Available tools: read_file, write_file, edit_file, search_files, shell_command, which, get_env, set_env
NOT available: IDA Pro tools, Binary Ninja tools, decompiler, database access
Working directory: file system path"""

        full_message = f"{cli_context}\n\nUser: {user_message}"

        # Call parent implementation with augmented message
        return super().start_agent(full_message)

    def invoke_skill(self, slug: str, args: str) -> str | None:
        """Invoke a skill by slug.

        Args:
            slug: Skill slug (e.g., "vuln-audit")
            args: Additional arguments for the skill

        Returns:
            Error message if skill not found, None otherwise
        """
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        skill = self._skill_registry.get(slug)
        if not skill:
            available = ", ".join(self._skill_registry.list_slugs()[:10])
            return f"Unknown skill: /{slug}. Available: {available}..."

        # Build CLI-specific system context
        cli_context = """You are running in Spectra CLI mode (NOT in IDA Pro or Binary Ninja).

Key differences:
- NO IDA Pro database available
- NO Binary Ninja database available
- You have access to: read_file, write_file, edit_file, search_files, shell_command
- Working directory: file system path
- For binary analysis: use shell_command with objdump, nm, strings, grep, etc.

Adapt your analysis accordingly:
- For source code: use read_file and search_files
- For binaries: use shell_command with objdump/nm/strings
- For kernel drivers: use shell_command with grep/modinfo
- NO IDA-specific tools: list_functions, get_binary_info, xrefs, etc. are NOT available

Always check available tools before assuming IDA features exist."""

        # Build prompt with CLI context
        prompt = skill.body or skill.description or ""
        full_prompt = f"{cli_context}\n\n{prompt}"
        if args:
            full_prompt = f"{args}\n\n{full_prompt}"

        # Start agent with skill context
        error = self.start_agent(full_prompt)
        if error:
            return error

        return None

    def list_skills(self) -> list[dict[str, str]]:
        """List all available skills.

        Returns:
            List of skill info dicts with keys: slug, name, description
        """
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        skills = []
        for skill in self._skill_registry.list_skills():
            skills.append({
                "slug": skill.slug,
                "name": skill.name,
                "description": skill.description or "",
            })

        return skills

    # --- Agent Mode Control ---

    def start_plan_mode(self, prompt: str) -> str | None:
        """Start agent in plan mode.

        Args:
            prompt: User prompt for planning

        Returns:
            Error message if failed, None otherwise
        """
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        # Prepend plan mode marker
        full_prompt = f"/plan {prompt}"
        error = self.start_agent(full_prompt)
        return error

    def start_research_mode(self, prompt: str) -> str | None:
        """Start agent in research mode.

        Args:
            prompt: User prompt for research

        Returns:
            Error message if failed, None otherwise
        """
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        # Prepend research mode marker
        full_prompt = f"/research {prompt}"
        error = self.start_agent(full_prompt)
        return error

    # --- Shell Command Execution ---

    def execute_shell_command(self, command: str) -> str:
        """Execute shell command (with safety checks and user approval).

        Args:
            command: Shell command to execute

        Returns:
            Command output
        """
        from ..tools.shell_tools import shell_command

        # Use the shell_command tool which has approval checks
        return shell_command(command)

    def set_shell_approval_callback(self) -> None:
        """Set up the approval callback for shell commands.

        This should be called when the CLI starts to ensure shell commands
        require user approval with dangerous command warnings.
        """
        from .tools.shell_tools import set_approval_callback
        from .shell_ui import Colors

        # Approval state management with command limit from config
        class ApprovalState:
            """Track approval mode with automatic reset after N commands."""
            def __init__(self, auto_approve_limit: int = 10):
                self.safe_auto_approve = False
                self.reject_all = False
                self.command_count = 0  # Track commands in auto-approve mode
                self.auto_approve_limit = auto_approve_limit  # Auto-reset after N commands

            def reset(self):
                """Reset all modes."""
                self.safe_auto_approve = False
                self.reject_all = False
                self.command_count = 0

            def increment_command_count(self):
                """Increment command count and check limit.

                Returns:
                    True if auto-approve was reset, False otherwise
                """
                self.command_count += 1
                # Only check limit if limit > 0 (0 means unlimited)
                if (self.safe_auto_approve and
                    self.auto_approve_limit > 0 and
                    self.command_count >= self.auto_approve_limit):
                    self.safe_auto_approve = False
                    self.command_count = 0
                    return True  # Signal that auto-approve was reset
                return False

            def get_status(self) -> str:
                """Get current status string for display."""
                if self.reject_all:
                    return "Reject all ON"
                if self.safe_auto_approve:
                    if self.auto_approve_limit == 0:
                        return f"Safe auto-approve ON (unlimited)"
                    return f"Safe auto-approve ON ({self.command_count}/{self.auto_approve_limit})"
                return "Manual approval"

        # Get auto-approve limit from config (default to 10 if not set)
        auto_approve_limit = getattr(self.config, 'shell_auto_approve_limit', 10)
        approval_state = ApprovalState(auto_approve_limit=auto_approve_limit)

        def approval_callback(command: str, is_dangerous: bool, danger_reason: str) -> bool:
            """Callback to request user approval for shell command execution.

            Args:
                command: The shell command to execute
                is_dangerous: Whether the command is dangerous
                danger_reason: Reason why the command is dangerous

            Returns:
                True if user approves, False otherwise
            """
            from ..core.logging import log_debug
            from .tools.shell_tools import set_shell_approval_state

            log_debug(f"Shell command approval requested: {command}")

            # Signal that we're entering shell approval (for output sync)
            set_shell_approval_state(True)

            # ANSI color codes - define BEFORE using
            BOLD = "\033[1m"
            CYAN = "\033[36m"
            YELLOW = "\033[33m"
            RED = "\033[31m"
            BRIGHT_RED = "\033[91m"
            GREEN = "\033[32m"
            RESET = "\033[0m"

            # Check session-wide approval state
            if approval_state.reject_all:
                log_debug(f"Shell command auto-rejected (reject all mode): {command}")
                print(f"{RED}✗ Rejected: {command}{RESET}")
                set_shell_approval_state(False)  # Signal approval complete
                return False

            # Handle safe auto-approve with command count limit
            if approval_state.safe_auto_approve and not is_dangerous:
                # Increment count and check if we should reset
                was_reset = approval_state.increment_command_count()
                if was_reset:
                    log_debug(f"Safe auto-approve mode reset after {approval_state.auto_approve_limit} commands")
                    print(f"{YELLOW}⚠️  Safe auto-approve expired after {approval_state.auto_approve_limit} commands{RESET}")
                    print(f"{YELLOW}    Reverting to manual approval for safety.{RESET}")
                    print()
                    # Fall through to manual approval
                else:
                    log_debug(f"Shell command auto-approved (safe mode, #{approval_state.command_count}): {command}")
                    count_text = f"{approval_state.command_count}/{approval_state.auto_approve_limit}" if approval_state.auto_approve_limit > 0 else "unlimited"
                    print(f"{GREEN}✓ Auto-approved ({count_text}): {command}{RESET}")
                    set_shell_approval_state(False)  # Signal approval complete
                    return True

            print()
            print(f"{BOLD}Shell Command Execution Requested{RESET}")
            print()

            # Show the command
            print(f"  {CYAN}Command:{RESET} {command}")
            print()

            # Show danger warning if applicable
            if is_dangerous:
                print(f"{BRIGHT_RED}⚠️  DANGEROUS COMMAND WARNING!{RESET}")
                print(f"{YELLOW}Reason: {danger_reason}{RESET}")
                print()

            # Show current approval mode status
            mode_status = approval_state.get_status()
            if mode_status != "Manual approval":
                print(f"{YELLOW}  Current mode: {mode_status}{RESET}")
                print()

            # Build prompt based on danger level
            if is_dangerous:
                # No "approve all" for dangerous commands!
                prompt = (
                    f"{BRIGHT_RED}⚠️  This command is DANGEROUS. Really approve? {RESET}" +
                    "[Y]es/[N]o/[R]eject all: "
                )
            else:
                limit_text = f"{approval_state.auto_approve_limit} cmds" if approval_state.auto_approve_limit > 0 else "unlimited"
                prompt = (
                    f"{YELLOW}Approve execution? {RESET}" +
                    f"[Y]es/[N]o/[S]afe auto-approve ({limit_text})/[R]eject all: "
                )

            # Flush stdout to ensure clean output before waiting for input
            import sys
            sys.stdout.flush()
            sys.stderr.flush()

            # Prompt for approval
            while True:
                try:
                    _flush_input()  # Clear any buffered ENTER keystrokes from AI output
                    response = input(prompt).strip().lower()
                except EOFError:
                    # Handle EOF (ctrl+d)
                    print()  # Add newline
                    log_debug(f"Shell command rejected (EOF): {command}")
                    set_shell_approval_state(False)  # Signal approval complete
                    return False
                except KeyboardInterrupt:
                    # Handle ctrl+c during input - abort and return to prompt
                    print()  # Add newline
                    print(f"{YELLOW}⏹  Approval cancelled by user (Ctrl+C). Returning to input.{RESET}")
                    log_debug(f"Shell command approval cancelled (interrupt): {command}")
                    set_shell_approval_state(False)  # Signal approval complete
                    return False

                # Single choice responses
                if response in ("y", "yes", ""):
                    log_debug(f"Shell command approved: {command}")
                    print(f"{CYAN}⏳ Executing command...{RESET}")
                    sys.stdout.flush()
                    set_shell_approval_state(False)  # Signal approval complete
                    return True
                elif response in ("n", "no"):
                    log_debug(f"Shell command rejected: {command}")
                    set_shell_approval_state(False)  # Signal approval complete
                    return False

                # Session-wide modes
                elif response in ("s", "safe", "safe auto-approve"):
                    approval_state.safe_auto_approve = True
                    approval_state.reject_all = False
                    approval_state.command_count = 0  # Reset count on new enable
                    log_debug(f"Enabled safe auto-approve mode")
                    limit_text = f"max {approval_state.auto_approve_limit} commands" if approval_state.auto_approve_limit > 0 else "unlimited"
                    print(f"{GREEN}✓ Safe auto-approve mode enabled ({limit_text}){RESET}")
                    print(f"{GREEN}  Dangerous commands still require manual approval{RESET}")
                    if not is_dangerous:
                        # Auto-approve this command and return
                        set_shell_approval_state(False)  # Signal approval complete
                        count_text = f"1/{approval_state.auto_approve_limit}" if approval_state.auto_approve_limit > 0 else "unlimited"
                        print(f"{GREEN}  Auto-approved ({count_text}): {command}{RESET}")
                        print(f"{CYAN}⏳ Executing command...{RESET}")
                        sys.stdout.flush()
                        return True  # Approve this safe command
                    # If dangerous, continue to ask - dangerous commands always need manual approval

                elif response in ("r", "reject all", "reset", "d", "deny"):
                    # Reset or reject-all mode
                    if response in ("r", "reset"):
                        # Reset all modes
                        approval_state.reset()
                        log_debug(f"Reset approval modes")
                        print(f"{YELLOW}✓ Approval modes reset to manual{RESET}")
                        # Ask again for this command
                        continue
                    else:
                        # Enable reject-all mode
                        approval_state.reject_all = True
                        approval_state.safe_auto_approve = False
                        log_debug(f"Enabled reject-all mode")
                        print(f"{RED}✓ Reject-ALL mode enabled (use 'R' to reset){RESET}")
                        set_shell_approval_state(False)  # Signal approval complete
                        return False

                else:
                    print(f"{RED}Invalid response. Please enter Y, N, S, or R.{RESET}")

        set_approval_callback(approval_callback)
        log_info("Shell approval callback registered")

    # --- Configuration Management ---

    def get_config(self) -> dict[str, Any]:
        """Get current configuration.

        Returns:
            Dict with current config values
        """
        return {
            "provider": self.config.provider.name,
            "model": self.config.provider.model,
            "api_base": self.config.provider.api_base,
            "has_api_key": bool(self.config.provider.api_key),
            "api_key_preview": f"{self.config.provider.api_key[:8]}..." if self.config.provider.api_key else "Not set",
        }

    def set_model(self, model_name: str) -> str | None:
        """Set the model for the current provider.

        Args:
            model_name: Model name to set

        Returns:
            Error message if failed, None otherwise
        """
        if not model_name:
            return "Model name cannot be empty"

        # Update config
        self.config.provider.model = model_name

        # Save config
        self.config.save()

        log_info(f"Model changed to: {model_name}")
        return None

    def set_provider(self, provider_name: str) -> str | None:
        """Set the LLM provider.

        Args:
            provider_name: Provider name (anthropic, openai, gemini, ollama)

        Returns:
            Error message if failed, None otherwise
        """
        if not provider_name:
            return "Provider name cannot be empty"

        valid_providers = ["anthropic", "openai", "gemini", "ollama", "glm", "lmstudio"]
        if provider_name not in valid_providers:
            return f"Invalid provider. Valid: {', '.join(valid_providers)}"

        # Update config
        self.config.provider.name = provider_name

        # Set default model and API base for provider
        default_configs = {
            "anthropic": {
                "model": "claude-3-5-sonnet-20241022",
                "api_base": "",
            },
            "openai": {
                "model": "gpt-4",
                "api_base": "",
            },
            "gemini": {
                "model": "gemini-pro",
                "api_base": "",
            },
            "ollama": {
                "model": "llama2",
                "api_base": "",
            },
            "glm": {
                "model": "glm-4",
                "api_base": "https://open.bigmodel.cn/api/paas/v4/",
            },
            "lmstudio": {
                "model": "local-model",
                "api_base": "http://localhost:1234/v1",
            },
        }

        config = default_configs.get(provider_name, {"model": "default", "api_base": ""})
        self.config.provider.model = config["model"]
        if config["api_base"]:
            self.config.provider.api_base = config["api_base"]

        # Save config
        self.config.save()

        log_info(f"Provider changed to: {provider_name}")
        return None

    def set_api_key(self, api_key: str) -> str | None:
        """Set the API key for the current provider.

        Args:
            api_key: API key to set

        Returns:
            Error message if failed, None otherwise
        """
        if not api_key:
            return "API key cannot be empty"

        # Update config
        self.config.provider.api_key = api_key

        # Save config
        self.config.save()

        log_info("API key updated")
        return None

    def list_available_models(self) -> list[dict[str, str]]:
        """List available models for the current provider.

        Fetches models from the provider API. Falls back to builtin list on error.

        Returns:
            List of model info dicts with keys: id, name
        """
        # Wait for runtime initialization
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        try:
            # Create provider instance with current config
            provider = self._provider_registry.create(
                self.config.provider.name,
                api_key=self.config.provider.api_key,
                api_base=self.config.provider.api_base,
            )

            # Ensure provider is ready (may need to import modules)
            provider.ensure_ready()

            # Fetch models from API (with fallback to builtins)
            models = provider.list_models()

            # Convert ModelInfo to dict format
            result = []
            for model in models:
                result.append({
                    "id": model.id,
                    "name": model.name,
                })

            log_info(f"Fetched {len(result)} models from {self.config.provider.name}")
            return result
        except Exception as e:
            import traceback
            log_debug(f"Failed to fetch models from API: {e}")
            traceback.print_exc()
            return []

    # --- Properties ---

    @property
    def has_active_session(self) -> bool:
        """Check if there's an active session with messages."""
        try:
            session = self.session
            return bool(session and session.messages)
        except KeyError:
            return False

    @property
    def session_count(self) -> int:
        """Get number of messages in current session."""
        try:
            return len(self.session.messages)
        except KeyError:
            return 0

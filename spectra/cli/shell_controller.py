"""CLI session controller - Shell-specific session management.

Extends SessionControllerBase for CLI environment without disrupting IDA Pro plugin.
"""

from __future__ import annotations

import os
from typing import Any

from ..core.config import SpectraConfig
from ..core.logging import log_debug, log_info
from ..state.history import SessionHistory
from ..state.session import SessionState
from ..tools.registry import ToolRegistry
from ..ui.session_controller_base import SessionControllerBase

# CLI-specific database instance ID (separate from IDA/BNDB)
_CLI_DB_INSTANCE_ID = "spectra-cli"


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
    registry.set_capabilities(
        {
            "hexrays": False,
            "idb_struct": False,
            "database": False,
            "ida_pro": False,
            "binary_ninja": False,
            "cli_mode": True,
            "filesystem": True,
            "shell": True,
            "source_code_analysis": True,
        }
    )

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

        # NOTE: shell approval callback is NOT wired here — the host UI
        # installs it via install_shell_approval() once its presenter
        # exists (the TUI does this after mount; no-UI callers simply
        # never install one and every shell command stays denied).

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
                if session_id.lower() in desc.lower() or session_id == sid[: len(session_id)]:
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
            if session_id == sid or session_id == sid[: len(session_id)] or session_id.lower() in desc.lower():
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
            result.append(
                {
                    "id": s.get("id", ""),
                    "description": s.get("description", "Unnamed"),
                    "timestamp": s.get("created_at", 0),
                    "message_count": s.get("message_count", 0),
                }
            )

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

    def resume_latest(self) -> SessionState | None:
        """Load the newest saved CLI session into the active tab.

        Unlike the base ``restore_session`` (which requires an idb_path),
        CLI sessions live under the fixed "spectra-cli" instance id. Used
        on startup to pick up the previous conversation.
        """
        history = SessionHistory(self.config)
        try:
            session = history.get_latest_session(
                idb_path="",
                db_instance_id=_CLI_DB_INSTANCE_ID,
            )
        except (OSError, ValueError, KeyError) as e:
            log_debug(f"Failed to find latest CLI session: {e}")
            return None
        if session and session.messages:
            self._sessions[self._active_tab_id] = session
            log_info(f"Resumed latest CLI session {session.id} ({len(session.messages)} messages)")
            return session
        return None

    # --- Skill Invocation ---

    def start_agent(self, user_message: str) -> str | None:
        """Override to prepend the working directory to every message.

        The CLI environment itself (available tools, no-IDA constraints)
        comes from the ``cli`` host prompt in the system prompt builder —
        only the live working directory is per-run context.

        Args:
            user_message: User's message

        Returns:
            Error message if failed, None otherwise
        """
        cli_context = f"[Working directory: {os.getcwd()}]"
        full_message = f"{cli_context}\n\n{user_message}"
        return super().start_agent(full_message)

    def list_skills(self) -> list[dict[str, str]]:
        """List all available skills.

        Returns:
            List of skill info dicts with keys: slug, name, description
        """
        if not self._runtime_init_done.is_set():
            self._runtime_init_done.wait(timeout=10.0)

        skills = []
        for skill in self._skill_registry.list_skills():
            skills.append(
                {
                    "slug": skill.slug,
                    "name": skill.name,
                    "description": skill.description or "",
                }
            )

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

    # --- Shell Approval (host-UI wiring) ---

    def install_shell_approval(
        self,
        presenter: Any,
        call_from_thread: Any,
    ) -> tuple[Any, Any]:
        """Wire shell-command approval to a live UI presenter.

        Creates the approval state (auto-approve limit from config) and a
        bridge carrying each request from the agent thread to the UI. The
        caller must ``unbind()`` the bridge when the UI goes away — that
        denies any waiter so the agent thread never hangs.

        Args:
            presenter: object providing
                ``push_shell_approval(command, is_dangerous, danger_reason, bridge)``
            call_from_thread: app.call_from_thread

        Returns:
            ``(state, bridge)`` tuple
        """
        from .approval import ShellApprovalBridge, ShellApprovalState
        from .tools.shell_tools import set_approval_callback

        auto_approve_limit = getattr(self.config, "shell_auto_approve_limit", 10)
        state: ShellApprovalState = ShellApprovalState(auto_approve_limit=auto_approve_limit)
        bridge = ShellApprovalBridge()
        bridge.bind(presenter, call_from_thread)

        def approval_callback(command: str, is_dangerous: bool, danger_reason: str) -> bool:
            if state.reject_all:
                return False
            approved, _expired = state.should_auto_approve(is_dangerous)
            if approved:
                return True
            return bridge.request(command, is_dangerous, danger_reason)

        set_approval_callback(approval_callback)
        log_info("Shell approval bridge installed")
        return state, bridge

    def resume_latest(self) -> SessionState | None:
        """Load the most recent CLI session into the active tab.

        Returns:
            Restored SessionState, or None when no saved session exists
        """
        history = SessionHistory(self.config)
        session = history.get_latest_session(idb_path="", db_instance_id=_CLI_DB_INSTANCE_ID)
        if session:
            self._sessions[self._active_tab_id] = session
            log_info("Latest session resumed")
        return session

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

        valid_providers = ["anthropic", "openai", "gemini", "ollama", "minimax", "glm", "lmstudio"]
        if provider_name not in valid_providers:
            return f"Invalid provider. Valid: {', '.join(valid_providers)}"

        # Update config
        self.config.provider.name = provider_name

        # Default API base per provider. ALWAYS reset api_base — including
        # to "" — so switching away from a local endpoint (lmstudio) does
        # not leave the next provider pointing at localhost.
        api_bases = {
            "glm": "https://open.bigmodel.cn/api/paas/v4/",
            "lmstudio": "http://localhost:1234/v1",
        }
        self.config.provider.api_base = api_bases.get(provider_name, "")

        # Default model: derived from the provider's builtin list so this
        # code never carries a stale duplicate of the model catalog.
        self.config.provider.model = self._default_model_for(provider_name)

        # Save config
        self.config.save()

        log_info(f"Provider changed to: {provider_name}")
        return None

    @staticmethod
    def _default_model_for(provider_name: str) -> str:
        """Pick the default model for a provider from its builtin catalog.

        Falls back to a per-provider literal when the catalog cannot be
        consulted (unknown/custom provider, import failure, empty list).
        """
        fallbacks = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4o",
            "gemini": "gemini-2.5-pro",
            "ollama": "llama3.1",
            "minimax": "MiniMax-M2.5",
            "glm": "glm-5",
            "lmstudio": "local-model",
        }
        try:
            from ..providers import (
                anthropic_provider,
                gemini_provider,
                minimax_provider,
                ollama_provider,
                openai_provider,
            )

            classes = {
                "anthropic": anthropic_provider.AnthropicProvider,
                "openai": openai_provider.OpenAIProvider,
                "gemini": gemini_provider.GeminiProvider,
                "ollama": ollama_provider.OllamaProvider,
                "minimax": minimax_provider.MiniMaxProvider,
            }
            cls = classes.get(provider_name)
            if cls is not None:
                models = cls._builtin_models()
                if models:
                    model_id = getattr(models[0], "id", None)
                    # Guard against stubbed/mock provider modules (tests) —
                    # only trust a real non-empty string.
                    if isinstance(model_id, str) and model_id:
                        return model_id
        except Exception:
            pass
        return fallbacks.get(provider_name, "local-model")

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
                result.append(
                    {
                        "id": model.id,
                        "name": model.name,
                    }
                )

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

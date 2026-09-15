"""SpectraApp — the full-screen Textual application.

Wiring: the entry point (``spectra_cli.py``) builds a
:class:`~spectra.cli.shell_controller.CLISessionController`, then calls
:func:`run_app`. The app owns:

- the **event pump** — a 20 Hz ``set_interval`` that drains up to 50
  ``TurnEvent``\\s per tick through :class:`~spectra.cli.events.EventMapper`
  into the chat view (main-thread polling; zero cross-thread widget access)
- **submission & queueing** — natural language starts a run or queues
  while one is active; the queue drains one message per finished run
- **modals** — tool approval, questions, save prompts, shell approval
  (via the bridge the controller installs), destructive confirms
- **slash commands** — dispatched through ``spectra.cli.commands``
- **``!command`` escapes** — async subprocess, streamed to a RichLog
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from ..core.logging import log_debug
from .approval import ShellApprovalBridge, ShellApprovalState
from .chat import (
    ChatLog,
    QuestionRequested,
    SaveApprovalRequested,
    ToolApprovalRequested,
)
from .commands import CommandKind, get_help_text, parse_command
from .events import EventMapper
from .history import InputHistory, default_history_paths
from .input_area import PromptInput
from .modals import (
    ConfirmModal,
    QuestionModal,
    SaveApprovalModal,
    ShellApprovalModal,
    ToolApprovalModal,
)
from .screens import DisclaimerScreen, ModelPickerScreen, SessionPickerScreen
from .think_filter import ThinkFilter

PUMP_HZ = 20
MAX_EVENTS_PER_TICK = 50
SHELL_ESCAPE_TIMEOUT = 120.0


class SpectraApp(App):
    """Full-screen Spectra CLI."""

    CSS_PATH = "spectra.tcss"
    TITLE = "Spectra"

    BINDINGS = [
        ("ctrl+q", "quit_spectra", "Quit"),
        ("ctrl+c", "interrupt", "Interrupt"),
        ("ctrl+o", "toggle_thinking", "Thinking"),
        ("ctrl+t", "toggle_tool", "Tool details"),
    ]

    def __init__(self, controller: Any) -> None:
        super().__init__()
        self._controller = controller
        self._chat = ChatLog()
        self._think_filter = ThinkFilter(on_thinking=self._chat.on_thinking)
        self._mapper = EventMapper(self._chat, self._think_filter)
        jsonl, legacy = default_history_paths(controller.config._config_dir)
        self._history = InputHistory(jsonl, legacy)
        self._prompt = PromptInput(self._history)
        self._agent_active = False
        self._run_started = 0.0
        self._shell_state: ShellApprovalState | None = None
        self._shell_bridge: ShellApprovalBridge | None = None
        self._models: list[str] = []
        self._sessions: list[dict] = []
        self._last_status = ""

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="status-bar"):
            yield Static("", id="status-left")
            yield Static("", id="status-right")
        yield self._chat
        yield Static("", id="completion-popup")
        with Vertical(id="prompt-zone"):
            with Horizontal(id="prompt-row"):
                yield Static("❯", id="prompt-label")
                yield self._prompt
        yield Footer()

    def on_mount(self) -> None:
        self._shell_state, self._shell_bridge = self._controller.install_shell_approval(self, self.call_from_thread)
        self.set_interval(1 / PUMP_HZ, self._pump)
        self._prompt.focus()
        if not getattr(self._controller.config, "disclaimer_accepted", False):
            self.push_screen(DisclaimerScreen(), self._on_disclaimer)
        self.run_worker(self._init_context, thread=True, exclusive=False, group="init-context")

    def on_unmount(self) -> None:
        if self._shell_bridge is not None:
            self._shell_bridge.unbind()

    def _on_disclaimer(self, accepted: bool | None) -> None:
        if not accepted:
            self.exit()
            return
        self._controller.config.disclaimer_accepted = True
        try:
            self._controller.config.save()
        except OSError as e:
            log_debug(f"Could not persist disclaimer acceptance: {e}")
        self._chat.add_system("Disclaimer accepted. Authorized security testing only — see /help.")
        self._prompt.focus()

    # ------------------------------------------------------------------
    # Background context (skills / models / sessions for completion)
    # ------------------------------------------------------------------

    def _init_context(self) -> None:
        """Worker thread: wait for the runtime, then prime completion data."""
        try:
            if not self._controller.wait_for_runtime(timeout=20.0):
                return
            skills = [s["slug"] for s in self._controller.list_skills()]
            models = [m["id"] for m in self._controller.list_available_models()]
            sessions = [(s.get("id", ""), str(s.get("description", ""))) for s in self._controller.list_sessions()]
        except Exception as e:  # network down etc. — completion just stays empty
            log_debug(f"context init failed: {e}")
            return
        self.call_from_thread(self._apply_context, skills, models, sessions)

    def _apply_context(
        self,
        skills: list[str],
        models: list[str],
        sessions: list[tuple[str, str]],
    ) -> None:
        self._models = models
        self._prompt.set_completion_context(skills=skills, models=models, sessions=sessions)
        self._refresh_status(force=True)

    def _refresh_sessions(self) -> None:
        """Worker thread: re-read the session list after save/delete."""
        try:
            sessions = [(s.get("id", ""), str(s.get("description", ""))) for s in self._controller.list_sessions()]
        except Exception:
            return
        self.call_from_thread(self._apply_sessions, sessions)

    def _apply_sessions(self, sessions: list[tuple[str, str]]) -> None:
        self._prompt.set_completion_context(sessions=sessions)

    # ------------------------------------------------------------------
    # Event pump
    # ------------------------------------------------------------------

    async def _pump(self) -> None:
        """Drain agent events, flush streaming markdown, detect finish."""
        controller = self._controller
        for _ in range(MAX_EVENTS_PER_TICK):
            event = controller.get_event(timeout=0)
            if event is None:
                break
            try:
                self._mapper.handle(event)
            except Exception as e:  # a render bug must never kill the pump
                log_debug(f"pump: mapper error: {e}")
        if self._chat._current_assistant is not None:
            self._chat.ensure_stream()
            await self._chat.flush_streaming()
        await self._chat.finalize_pending()
        if self._agent_active and not controller.is_agent_running():
            self._on_agent_finished()
        self._refresh_status()

    def _on_agent_finished(self) -> None:
        """Agent run ended (normal, error, or cancel): drain the queue."""
        self._agent_active = False
        self._mapper.finish_run()
        self._chat.clear_running_tool()
        queued = self._controller.on_agent_finished()  # also auto-saves checkpoint
        self._chat.remove_all_queued()
        if queued:
            # Oldest pending message continues the conversation; the rest
            # stay queued (controller + UI) and drain one per finish.
            self._start_run(queued[0], show_user=True)
            for text in queued[1:]:
                self._controller.queue_message(text)
                self._chat.add_queued(text)
        self._refresh_status(force=True)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _refresh_status(self, force: bool = False) -> None:
        try:
            left = self.query_one("#status-left", Static)
            right = self.query_one("#status-right", Static)
        except Exception:
            return
        provider = getattr(self._controller.config.provider, "name", "?")
        model = getattr(self._controller.config.provider, "model", "?")
        cwd = os.path.basename(os.getcwd()) or "/"
        left_text = f" ◆ Spectra · {provider}/{model} · {cwd}"
        usage = self._chat.last_usage
        tokens = f" · {usage.total_tokens:,} tok" if usage is not None else ""
        if self._agent_active:
            elapsed = max(0, int(time.monotonic() - self._run_started))
            tool = self._chat.running_tool
            activity = f"⚙ {tool}" if tool else "✦ thinking"
            nq = len(self._chat._queued)
            queue = f" · queued {nq}" if nq else ""
            turn = f" · turn {self._chat.last_turn}" if self._chat.last_turn else ""
            right_text = f"{activity} ({elapsed}s){queue}{turn}{tokens}"
        else:
            right_text = f"idle{tokens}"
        if force or left_text != self._last_status:
            left.update(left_text)
        right.update(right_text)
        self._last_status = left_text

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        self._handle_input(event.text)

    def _handle_input(self, text: str) -> None:
        parsed = parse_command(text)
        if parsed.kind is CommandKind.SHELL_ESCAPE:
            self._run_shell_escape(parsed.arg)
            return
        if parsed.kind is CommandKind.NATURAL_LANGUAGE:
            self._send_message(parsed.arg or text)
            return
        self._run_command(parsed)

    def _send_message(self, text: str) -> None:
        if not text.strip():
            return
        self._chat.add_user(text)
        if self._controller.is_agent_running() or self._agent_active:
            self._controller.queue_message(text)
            self._chat.add_queued(text)
            self._refresh_status(force=True)
            return
        self._start_run(text)

    def _start_run(self, text: str, show_user: bool = False) -> None:
        if show_user:
            self._chat.add_user(text)
        self._mapper.begin_run()
        self._agent_active = True
        self._run_started = time.monotonic()
        error = self._controller.start_agent(text)
        if error:
            self._agent_active = False
            self._chat.add_error(error)
        self._refresh_status(force=True)

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    async def action_quit_spectra(self) -> None:
        if self._agent_active or self._controller.is_agent_running():
            self._controller.cancel()
        if self._shell_bridge is not None:
            self._shell_bridge.unbind()
        self.exit()

    def action_interrupt(self) -> None:
        """Ctrl+C: cancel the run; queued messages return to the input."""
        if not (self._agent_active or self._controller.is_agent_running()):
            return
        returned = self._controller.cancel()
        self._chat.remove_all_queued()
        if returned:
            self._prompt.restore_text("\n".join(returned))
        self._refresh_status(force=True)
        # The pump sees CANCELLED + not-running and runs _on_agent_finished,
        # which removes the runner and auto-saves the checkpoint.

    def action_toggle_thinking(self) -> None:
        self._toggle_thinking()

    def action_toggle_tool(self) -> None:
        if not self._chat.toggle_last_tool():
            self._chat.add_system("No tool block yet.")

    # ------------------------------------------------------------------
    # Chat-routed interactions (modals)
    # ------------------------------------------------------------------

    def on_tool_approval_requested(self, event: ToolApprovalRequested) -> None:
        self.push_screen(
            ToolApprovalModal(event.name, event.args_json, event.description),
            self._tool_approval_done,
        )

    def _tool_approval_done(self, result: str | None) -> None:
        runner = self._controller.get_runner()
        if runner is not None:
            runner.agent_loop.submit_tool_approval(result or "deny")
        self._prompt.focus()

    def on_question_requested(self, event: QuestionRequested) -> None:
        self.push_screen(
            QuestionModal(event.question, event.options, event.allow_text),
            self._question_done,
        )

    def _question_done(self, answer: str | None) -> None:
        runner = self._controller.get_runner()
        if runner is not None:
            runner.agent_loop.submit_user_answer(answer or "")
        self._prompt.focus()

    def on_save_approval_requested(self, event: SaveApprovalRequested) -> None:
        self.push_screen(SaveApprovalModal(event.summary), self._save_done)

    def _save_done(self, result: str | None) -> None:
        runner = self._controller.get_runner()
        if runner is not None:
            runner.agent_loop.submit_user_answer(result or "discard")
        self._prompt.focus()

    # ------------------------------------------------------------------
    # Shell approval presenter (called on the UI thread by the bridge)
    # ------------------------------------------------------------------

    def push_shell_approval(self, command: str, is_dangerous: bool, danger_reason: str, bridge: Any) -> None:
        def done(approved: bool | None) -> None:
            bridge.resolve(bool(approved))
            self._prompt.focus()

        self.push_screen(ShellApprovalModal(command, is_dangerous, danger_reason), done)

    # ------------------------------------------------------------------
    # Completion popup (rendered from PromptInput messages)
    # ------------------------------------------------------------------

    def on_prompt_input_completions_changed(self, event: PromptInput.CompletionsChanged) -> None:
        try:
            popup = self.query_one("#completion-popup", Static)
        except Exception:
            return
        if not event.items:
            popup.remove_class("visible")
            popup.update("")
            return
        lines = []
        for i, item in enumerate(event.items):
            marker = "›" if i == event.index else " "
            hint = f"  — {item.hint}" if item.hint else ""
            lines.append(f"[black on default]{marker}[/] {item.label}[dim]{hint}[/]")
        popup.update("\n".join(lines))
        popup.add_class("visible")

    # ------------------------------------------------------------------
    # !command escapes
    # ------------------------------------------------------------------

    def _run_shell_escape(self, command: str) -> None:
        if not command.strip():
            return
        output = self._chat.add_shell_escape(command)

        async def runner() -> None:
            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=os.getcwd(),
                )
                assert proc.stdout is not None

                async def consume() -> None:
                    while True:
                        line = await proc.stdout.readline()
                        if not line:
                            break
                        output.write(line.decode("utf-8", errors="replace").rstrip("\n"))
                    await proc.wait()

                try:
                    # asyncio.timeout is 3.11+; wait_for has identical
                    # cancel-on-timeout semantics and runs everywhere.
                    await asyncio.wait_for(consume(), SHELL_ESCAPE_TIMEOUT)
                except asyncio.TimeoutError:  # noqa: UP041 — must stay asyncio.* for 3.10
                    proc.kill()
                    output.write(f"⏱ timed out after {SHELL_ESCAPE_TIMEOUT:.0f}s")
                    return
                if proc.returncode not in (0, None):
                    output.write(f"[exit {proc.returncode}]")
            except FileNotFoundError as e:
                output.write(str(e))
            except Exception as e:
                output.write(f"error: {e}")

        self.run_worker(runner, group="shell-escape", exclusive=False)

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    def _run_command(self, parsed) -> None:
        kind = parsed.kind
        arg = parsed.arg.strip()

        if kind is CommandKind.HELP:
            self._chat.add_system(get_help_text())

        elif kind is CommandKind.SKILLS:
            self._cmd_skills()

        elif kind is CommandKind.SESSION_SAVE:
            self._cmd_save(arg)

        elif kind is CommandKind.SESSION_LOAD:
            self._cmd_load(arg)

        elif kind is CommandKind.SESSION_LIST:
            self._cmd_sessions()

        elif kind is CommandKind.SESSION_DELETE:
            self._cmd_delete(arg)

        elif kind is CommandKind.SESSION_NEW:
            self._cmd_new()

        elif kind is CommandKind.MODEL:
            self._cmd_model(arg)

        elif kind is CommandKind.PROVIDER:
            self._cmd_provider(arg)

        elif kind is CommandKind.APIKEY:
            self._cmd_apikey(arg)

        elif kind is CommandKind.APIURL:
            self._cmd_apiurl(arg)

        elif kind is CommandKind.CONFIG_SHOW:
            self._cmd_config_show()

        elif kind is CommandKind.CONFIG_EDIT:
            self._cmd_config_edit()

        elif kind is CommandKind.AUTOLIMIT:
            self._cmd_autolimit(arg)

        elif kind is CommandKind.TOGGLE:
            self.action_toggle_tool()

        elif kind is CommandKind.THINKING:
            self._toggle_thinking()

        elif kind is CommandKind.PLAN:
            self._cmd_mode(arg, "plan")

        elif kind is CommandKind.RESEARCH:
            self._cmd_mode(arg, "research")

        elif kind is CommandKind.SKILL:
            self._start_run(f"/{parsed.slug} {parsed.arg}".strip())

        else:  # pragma: no cover — registry kinds all handled above
            self._chat.add_system("Unknown command.")

    def _toggle_thinking(self) -> None:
        live = self._think_filter.toggle()
        if live:
            self._chat.add_system("Live thinking display: ON")
        else:
            captured = self._think_filter.last_thinking
            if captured.strip():
                self._chat.reveal_last_thinking(captured)
            self._chat.add_system("Live thinking display: OFF (last reasoning shown above)")

    def _cmd_skills(self) -> None:
        try:
            skills = self._controller.list_skills()
        except Exception as e:
            self._chat.add_error(f"Could not list skills: {e}")
            return
        if not skills:
            self._chat.add_system("No skills installed.")
            return
        lines = ["Skills:"]
        for s in skills:
            desc = s.get("description", "")
            suffix = f" — {desc}" if desc else ""
            lines.append(f"  /{s['slug']}{suffix}")
        self._chat.add_system("\n".join(lines))

    def _cmd_save(self, name: str) -> None:
        if not name:
            name = time.strftime("Session %Y-%m-%d %H:%M")
        try:
            path = self._controller.save_session(name)
            self._chat.add_system(f"✔ Session saved: {path}")
        except Exception as e:
            self._chat.add_error(f"Save failed: {e}")
            return
        self.run_worker(self._refresh_sessions, thread=True, group="refresh-sessions")

    def _cmd_load(self, arg: str) -> None:
        if not arg:
            sessions = self._safe_sessions()
            if not sessions:
                self._chat.add_system("No saved sessions.")
                return
            self.push_screen(SessionPickerScreen(sessions), self._load_picked)
            return
        self._load_session(arg)

    def _load_picked(self, session_id: str | None) -> None:
        self._prompt.focus()
        if session_id:
            self._load_session(session_id)

    def _load_session(self, session_id: str) -> None:
        if self._agent_active or self._controller.is_agent_running():
            self._controller.cancel()
        session = self._controller.load_session(session_id)
        if session is None:
            self._chat.add_error(f"Session not found: {session_id}")
            return
        self._chat.clear()
        self._chat.add_system(f"Loaded session {session_id[:8]} — {len(session.messages)} messages")
        from ..core.types import Role

        for message in session.messages:
            if message.role is Role.USER and message.content:
                self._chat.add_user(message.content)
            elif message.role is Role.ASSISTANT and message.content:
                self._chat.add_markdown(message.content)
        self._chat.add_system("Session restored. Continue the conversation.")

    def _safe_sessions(self) -> list[dict]:
        try:
            return self._controller.list_sessions()
        except Exception:
            return []

    def _cmd_sessions(self) -> None:
        sessions = self._safe_sessions()
        if not sessions:
            self._chat.add_system("No saved sessions.")
            return
        import datetime as dt

        lines = ["Saved sessions:"]
        for s in sessions[-20:]:  # newest last
            when = s.get("timestamp", 0)
            stamp = dt.datetime.fromtimestamp(when).strftime("%m-%d %H:%M") if when else "?"
            lines.append(
                f"  {s.get('id', '')[:8]}  {stamp}  {s.get('message_count', 0):>3} msg  {str(s.get('description', 'Unnamed'))[:40]}"
            )
        lines.append("Use /load <id> or /load to pick interactively.")
        self._chat.add_system("\n".join(lines))

    def _cmd_delete(self, arg: str) -> None:
        if not arg:
            self._chat.add_system("Usage: /delete <session-id> (see /sessions)")
            return

        def done(confirmed: bool | None) -> None:
            self._prompt.focus()
            if not confirmed:
                return
            if self._controller.delete_session(arg):
                self._chat.add_system(f"✔ Deleted session {arg[:8]}")
                self.run_worker(self._refresh_sessions, thread=True, group="refresh-sessions")
            else:
                self._chat.add_error(f"Session not found: {arg}")

        self.push_screen(
            ConfirmModal("Delete session", f"Delete saved session {arg[:8]} permanently?", "Delete"),
            done,
        )

    def _cmd_new(self) -> None:
        if self._agent_active or self._controller.is_agent_running():
            self._controller.cancel()
        try:
            self._controller.new_session()
        except Exception as e:
            self._chat.add_error(f"New session failed: {e}")
            return
        self._chat.clear()
        self._chat.add_system("New session started.")

    def _cmd_model(self, arg: str) -> None:
        if not arg:
            if self._models:
                current = getattr(self._controller.config.provider, "model", "")
                self.push_screen(ModelPickerScreen(self._models, current), self._model_picked)
            else:
                self._chat.add_system(
                    f"Current model: {getattr(self._controller.config.provider, 'model', '?')}\n"
                    "Model list unavailable (provider unreachable?) — use /model <name>."
                )
            return
        self._set_model(arg)

    def _model_picked(self, model: str | None) -> None:
        self._prompt.focus()
        if model:
            self._set_model(model)

    def _set_model(self, model: str) -> None:
        error = self._controller.set_model(model)
        if error:
            self._chat.add_error(error)
        else:
            self._chat.add_system(f"Model set to {model}")
        self._refresh_status(force=True)

    def _cmd_provider(self, arg: str) -> None:
        if not arg:
            current = getattr(self._controller.config.provider, "name", "?")
            self._chat.add_system(f"Current provider: {current}\nUse /provider <name> to switch.")
            return
        error = self._controller.set_provider(arg)
        if error:
            self._chat.add_error(error)
        else:
            self._chat.add_system(f"Provider set to {arg}")
            self.run_worker(self._init_context, thread=True, group="init-context")
        self._refresh_status(force=True)

    def _cmd_apikey(self, arg: str) -> None:
        if arg:
            self._set_apikey(arg)
            return

        def done(answer: str | None) -> None:
            self._prompt.focus()
            if answer:
                self._set_apikey(answer)

        self.push_screen(QuestionModal("API key for the current provider", allow_text=True), done)

    def _set_apikey(self, key: str) -> None:
        error = self._controller.set_api_key(key)
        if error:
            self._chat.add_error(error)
        else:
            self._chat.add_system("API key updated.")

    def _cmd_apiurl(self, arg: str) -> None:
        if not arg:
            current = getattr(self._controller.config.provider, "api_base", "") or "(default)"
            self._chat.add_system(f"Current API base URL: {current}\nUse /apiurl <url> to change.")
            return
        try:
            self._controller.config.provider.api_base = arg
            self._controller.config.save()
            self._chat.add_system(f"API base URL set to {arg}")
        except Exception as e:
            self._chat.add_error(f"Could not save API URL: {e}")

    def _cmd_config_show(self) -> None:
        path = self._controller.config.config_path
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            self._chat.add_error(f"Could not read config: {e}")
            return
        shown = content if len(content) <= 6000 else content[:6000] + "\n… (truncated)"
        self._chat.add_system(f"Config ({path}):\n{shown}")

    def _cmd_config_edit(self) -> None:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
        path = self._controller.config.config_path

        async def run() -> None:
            try:
                with self.suspend():
                    subprocess.call([editor, path])
            except Exception as e:
                self._chat.add_error(f"Editor failed: {e}")
                return
            self._chat.add_system("Config edited — restart Spectra to apply provider changes.")

        self.run_worker(run, group="config-edit")

    def _cmd_autolimit(self, arg: str) -> None:
        config = self._controller.config
        if not arg:
            current = getattr(config, "shell_auto_approve_limit", 10)
            self._chat.add_system(
                f"Safe-command auto-approve limit: {current} (0 = unlimited)\n"
                "Use /autolimit <n> to change. Dangerous commands always require approval."
            )
            return
        try:
            value = int(arg)
            if value < 0:
                raise ValueError
        except ValueError:
            self._chat.add_system("Usage: /autolimit <n>  (0 = unlimited)")
            return
        config.shell_auto_approve_limit = value
        try:
            config.save()
        except OSError as e:
            self._chat.add_error(f"Could not save config: {e}")
            return
        if self._shell_state is not None:
            self._shell_state.auto_approve_limit = value
        label = "unlimited" if value == 0 else str(value)
        self._chat.add_system(f"Auto-approve limit set to {label}.")

    def _cmd_mode(self, arg: str, mode: str) -> None:
        if not arg:
            usage = f"/{mode} <goal>"
            self._chat.add_system(f"Usage: {usage}")
            return
        if self._agent_active or self._controller.is_agent_running():
            self._chat.add_system("Agent is busy — interrupt (Ctrl+C) first.")
            return
        self._chat.add_user(f"/{mode} {arg}")
        self._mapper.begin_run()
        self._agent_active = True
        self._run_started = time.monotonic()
        starter = self._controller.start_plan_mode if mode == "plan" else self._controller.start_research_mode
        error = starter(arg)
        if error:
            self._agent_active = False
            self._chat.add_error(error)
        self._refresh_status(force=True)


def run_app(controller: Any) -> None:
    """Entry point from ``spectra_cli.py`` (textual import stays deferred)."""
    SpectraApp(controller).run()

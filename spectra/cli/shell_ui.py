"""Shell UI - Terminal output handler with streaming.

Handles AgentLoop events and formats output for terminal display.
Features:
- Live text streaming
- Markdown rendering (code blocks, headers)
- Progress indicators
- Tool call display
- Color output for different event types
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from collections.abc import Generator

from ..agent.loop import AgentLoop
from ..agent.turn import TurnEvent, TurnEventType


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def strip_ansi(text: str) -> str:
    """Remove ANSI color codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def strip_xml_tags(text: str) -> str:
    """Remove XML-like tags from tool results."""
    # Remove <tool_result> tags
    text = re.sub(r"<tool_result[^>]*>", "", text)
    text = re.sub(r"</tool_result>", "", text)
    # Remove other common XML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _render_markdown_table(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """Render a markdown table and return (rendered_lines, next_idx)."""
    table_lines = []
    idx = start_idx

    # Collect all table lines
    while idx < len(lines):
        line = lines[idx].strip()
        if not line or not line.startswith("|"):
            break
        table_lines.append(lines[idx])
        idx += 1

    if len(table_lines) < 2:
        return [], start_idx  # Not a valid table

    # Parse table rows
    rows = []
    for line in table_lines:
        # Remove leading/trailing pipes and split
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)

    if len(rows) < 2:
        return [], start_idx

    # Calculate column widths
    num_cols = len(rows[0])
    col_widths = [0] * num_cols

    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))

    # Render table
    result = []
    _total_width = sum(col_widths) + (num_cols - 1) * 3 + 2  # 3 for " | ", 2 for borders

    # Header row
    header = rows[0]
    header_cells = []
    for i, cell in enumerate(header):
        header_cells.append(f"{Colors.BOLD}{cell.ljust(col_widths[i])}{Colors.RESET}")
    result.append(f"┌─{'─┬─'.join('─' * w for w in col_widths)}─┐")
    result.append(f"│ {' │ '.join(header_cells)} │")
    result.append(f"├─{'─┼─'.join('─' * w for w in col_widths)}─┤")

    # Data rows
    for row in rows[2:]:  # Skip separator row (index 1)
        cells = []
        for i, cell in enumerate(row):
            if i < num_cols:
                cells.append(cell.ljust(col_widths[i]))
        result.append(f"│ {' │ '.join(cells)} │")

    result.append(f"└─{'─┴─'.join('─' * w for w in col_widths)}─┘")
    return result, idx


def simple_markdown_render(text: str) -> str:
    """Simple markdown rendering for terminal.

    Handles:
    - Code blocks (```lang ... ```) → plain text with indentation
    - Tables (| ... |) → formatted with box drawing characters
    - Inline code (`...`) → quoted text
    - Headers (# ...) → bold underlined
    - Bold (**...**) → bold text
    - Lists (- ...) → bulleted
    """
    lines = text.split("\n")
    result = []

    in_code_block = False
    code_lang = ""
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for code block start/end
        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                result.append(f"{Colors.DIM}─── {code_lang or 'code'} ───{Colors.RESET}")
            else:
                in_code_block = False
                result.append(f"{Colors.DIM}─── end ───{Colors.RESET}")
            i += 1
            continue

        # Inside code block - just output with dim color
        if in_code_block:
            result.append(f"{Colors.DIM}{line}{Colors.RESET}")
            i += 1
            continue

        # Check for table
        stripped = line.strip()
        if stripped.startswith("|") and "|" in stripped:
            table_rendered, next_idx = _render_markdown_table(lines, i)
            if table_rendered:
                result.extend(table_rendered)
                i = next_idx
                continue

        # Inline code
        line = re.sub(r"`([^`]+)`", f"{Colors.CYAN}\\1{Colors.RESET}", line)

        # Headers
        if line.startswith("# "):
            line = f"{Colors.BOLD}{Colors.GREEN}{line[2:]}{Colors.RESET}"
        elif line.startswith("## "):
            line = f"{Colors.BOLD}{line[3:]}{Colors.RESET}"
        elif line.startswith("### "):
            line = f"{Colors.BOLD}{line[4:]}{Colors.RESET}"

        # Bold
        line = re.sub(r"\*\*([^*]+)\*\*", f"{Colors.BOLD}\\1{Colors.RESET}", line)

        # Lists
        if line.startswith("- ") or line.startswith("* "):
            line = f"  {Colors.BLUE}•{Colors.RESET} {line[2:]}"

        result.append(line)
        i += 1

    return "\n".join(result)


class ToolResultState:
    """Tracks display state for a single tool result."""

    def __init__(self, tool_name: str, result: str, tool_args: str = ""):
        self.tool_name = tool_name
        self.result = result
        self.tool_args = tool_args  # Store raw tool args for display
        self.collapsed = False  # Default to expanded
        self.lines_shown = 0

    def toggle(self) -> bool:
        """Toggle collapse state. Returns new state (True=collapsed)."""
        self.collapsed = not self.collapsed
        return self.collapsed


class ShellUI:
    """Terminal UI handler for AgentLoop events.

    Streams agent output to terminal with formatting and colors.
    Supports collapse/expand of tool results via Ctrl+O.
    """

    def __init__(self, use_colors: bool = True, use_markdown: bool = True):
        """Initialize ShellUI.

        Args:
            use_colors: Enable ANSI colors (disable for non-terminal)
            use_markdown: Enable markdown rendering
        """
        self.use_colors = use_colors
        self.use_markdown = use_markdown

        # Check if we're in a terminal
        self.is_tty = sys.stdout.isatty()

        # Track tool results for collapse/expand
        self._tool_results: list[ToolResultState] = []
        self._result_index = 0  # Current result index for toggling

        # Track pending tool call args (maps tool_call_id -> raw args string)
        self._pending_tool_args: dict[str, str] = {}

        # Track current turn text for markdown rendering
        self._current_text_buffer = ""

        # Track inline markdown state during streaming
        self._in_bold = False
        self._in_code = False

        # Track if we need to re-render text (for tables)
        self._pending_render = False

    def _color(self, text: str, color: str) -> str:
        """Apply color if enabled."""
        if self.use_colors and self.is_tty:
            return f"{color}{text}{Colors.RESET}"
        return text

    def _bold(self, text: str) -> str:
        """Bold text if enabled."""
        if self.use_colors and self.is_tty:
            return f"{Colors.BOLD}{text}{Colors.RESET}"
        return text

    def toggle_collapse(self) -> None:
        """Toggle collapse state for the most recent tool result.

        This is called when Ctrl+O is pressed.
        """
        if self._tool_results:
            # Toggle the most recent result
            result_state = self._tool_results[-1]
            _is_now_collapsed = result_state.toggle()

            # Redraw the result
            self._redraw_result(result_state)

    def _redraw_result(self, result_state: ToolResultState) -> None:
        """Redraw a tool result with current collapse state.

        Note: In a standard terminal, we can't truly "undraw" lines,
        so this prints a fresh copy below the original.
        """
        result = result_state.result
        lines = result.split("\n")
        line_count = len(lines)

        # Format tool args for display
        args_display = ""
        if result_state.tool_args:
            try:
                args_dict = (
                    json.loads(result_state.tool_args)
                    if isinstance(result_state.tool_args, str)
                    else result_state.tool_args
                )
                args_display = self._format_tool_args(result_state.tool_name, args_dict)
            except Exception:
                args_display = ""

        # Print separator
        print()
        collapse_status = "collapsed" if result_state.collapsed else "expanded"
        print(
            f"    {self._color(f'[{result_state.tool_name}]', Colors.CYAN)} {self._color(args_display, Colors.DIM)} {self._color(':', Colors.CYAN)} ({collapse_status})"
        )

        if not result_state.collapsed:
            # Expanded view
            for line in lines:
                if line.strip():
                    print(f"      {self._color(line, Colors.DIM)}")
        else:
            # Collapsed view - show preview
            preview_lines = min(3, line_count)
            for i in range(preview_lines):
                if lines[i].strip():
                    print(f"      {self._color(lines[i], Colors.DIM)}")
            if line_count > preview_lines:
                remaining = line_count - preview_lines
                print(f"      {self._color(f'... ({remaining} more lines)', Colors.DIM)}")

        print()
        print(f"    {self._color('Press Ctrl+O again to toggle', Colors.DIM)}")

    def stream_agent_loop(
        self,
        agent_loop: AgentLoop,
        approve_tools: bool = False,
    ) -> Generator[None, None, None]:
        """Stream agent events to terminal.

        This generator yields control back to the caller after each event
        is processed, allowing for interactive feedback.

        Args:
            agent_loop: The AgentLoop to stream events from
            approve_tools: Whether to prompt for tool approval

        Yields:
            None after each event is processed
        """
        # Track state for tool approval
        pending_approval: str | None = None

        try:
            for event in agent_loop.run(""):  # Prompt already set in loop
                yield from self._handle_event(event, pending_approval)

                # Handle tool approval requests
                if event.type == TurnEventType.TOOL_APPROVAL_REQUEST:
                    print(
                        f"[SHELL DEBUG] TOOL_APPROVAL_REQUEST received: {event.tool_name}", file=sys.stderr, flush=True
                    )
                    tool_name = event.tool_name
                    tool_args = event.tool_args

                    # Show approval prompt
                    print()

                    # Add warning based on tool type
                    if tool_name == "shell_command":
                        print()
                        print(self._color("⚠️  Shell command requires approval", Colors.YELLOW))
                        print()

                    print("[SHELL DEBUG] Calling _prompt_approval...", file=sys.stderr, flush=True)
                    decision = self._prompt_approval(
                        tool_name,
                        tool_args,
                        event.parameter_descriptions,
                    )
                    print(f"[SHELL DEBUG] Got decision: {decision}", file=sys.stderr, flush=True)

                    # Submit decision
                    agent_loop.submit_tool_approval(decision)

                    if decision.lower() != "y":
                        pending_approval = tool_name

                elif event.type == TurnEventType.TOOL_CALL_DONE:
                    pending_approval = None

        except KeyboardInterrupt:
            print()
            print(self._color("Interrupted by user", Colors.YELLOW))
            agent_loop.cancel()

    def _format_tool_args(self, tool_name: str, args: dict) -> str:
        """Format tool arguments for display.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments as dict

        Returns:
            Formatted argument summary in parentheses (value only)
        """
        if not args:
            return ""

        # Map each tool to its primary display value
        tool_value_map = {
            "read_file": "path",
            "write_file": "path",
            "edit_file": "path",
            "list_directory": "directory",
            "search_files": "pattern",
            "shell_command": "command",
            "spawn_subagent": "task",
        }

        # Get the key to display for this tool
        key = tool_value_map.get(tool_name)
        value = None

        if key and key in args:
            value = args[key]
        elif args:
            # Fallback: use first value
            value = next(iter(args.values()), None)

        if not value:
            return ""

        # For file paths, show basename with directory hint
        # For other values, truncate long values
        if tool_name in ("read_file", "write_file", "edit_file") and isinstance(value, str):
            # Show filename with directory prefix
            if "/" in value or "\\" in value:
                import os

                basename = os.path.basename(value)
                dirname = os.path.dirname(value)
                if len(dirname) > 30:
                    dirname = "..." + dirname[-27:]
                return f"({dirname}/{basename})"
            return f"({value})"
        elif isinstance(value, str) and len(value) > 40:
            value = value[:37] + "..."

        return f"({value})"

    def _handle_event(self, event: TurnEvent, pending_approval: str | None = None) -> Generator[None, None, None]:
        """Handle a single event and output to terminal.

        Args:
            event: The TurnEvent to handle
            pending_approval: Name of tool awaiting approval

        Yields:
            None after output is complete
        """
        if event.type == TurnEventType.TEXT_DELTA:
            # Stream text with inline markdown parsing
            text = event.text

            # Buffer for potential table rendering
            self._current_text_buffer += text

            # Check if this text contains table markers
            if "|" in text and self.use_markdown:
                self._pending_render = True

            # Simple inline markdown parser for streaming
            # Handle **bold** pattern
            i = 0
            while i < len(text):
                # Check for **
                if text[i : i + 2] == "**":
                    if self._in_bold:
                        # End bold
                        sys.stdout.write(Colors.RESET)
                        self._in_bold = False
                    else:
                        # Start bold
                        sys.stdout.write(Colors.BOLD)
                        self._in_bold = True
                    i += 2
                # Check for `code`
                elif text[i] == "`":
                    if self._in_code:
                        # End code
                        sys.stdout.write(Colors.RESET)
                        self._in_code = False
                    else:
                        # Start code
                        sys.stdout.write(Colors.CYAN)
                        self._in_code = True
                    i += 1
                else:
                    # Regular character
                    sys.stdout.write(text[i])
                    i += 1

            sys.stdout.flush()
            yield

        elif event.type == TurnEventType.TEXT_DONE:
            # Text complete - reset markdown state
            if self._in_bold or self._in_code:
                sys.stdout.write(Colors.RESET)
                self._in_bold = False
                self._in_code = False

            # If tables were detected, re-render the full text
            if self._pending_render and self.use_markdown:
                # Clear the line and re-render
                sys.stdout.write("\r\033[K")  # Clear to end of line
                # Move up to clear previous lines (rough estimation)
                lines = self._current_text_buffer.count("\n")
                for _ in range(lines + 1):
                    sys.stdout.write("\033[1A\033[K")  # Move up and clear

                # Render with proper table formatting
                rendered = simple_markdown_render(self._current_text_buffer)
                print(rendered)

                self._pending_render = False
            else:
                print()  # End the line

            # Reset buffer
            self._current_text_buffer = ""
            yield

        elif event.type == TurnEventType.TURN_START:
            # Reset markdown state
            self._in_bold = False
            self._in_code = False
            print()

            # Metasploit-style thinking animation with progress bar
            stages = [
                ("Analyzing context...", "🔍"),
                ("Processing query...", "🧠"),
                ("Generating response...", "✨"),
                ("Preparing output...", "📝"),
            ]

            for stage, icon in stages:
                # Stage animation
                for progress in range(11):
                    bar_length = progress
                    bar = "█" * bar_length + "░" * (10 - bar_length)
                    sys.stdout.write(
                        f"\r{self._color(icon, Colors.CYAN)} {self._bold(stage)} [{self._color(bar, Colors.GREEN)}]"
                    )
                    sys.stdout.flush()
                    time.sleep(0.03)

                time.sleep(0.1)

            # Clear line and show ready message with flash effect
            for flash in range(3):
                sys.stdout.write(
                    f"\r{self._color('🤖', Colors.GREEN if flash % 2 == 0 else Colors.YELLOW)} {self._bold('Spectra:')}      "
                )
                sys.stdout.flush()
                time.sleep(0.1)

            # Final state
            sys.stdout.write("\r" + " " * 50 + "\r")
            print(self._bold("🤖 Spectra:"), end=" ")
            sys.stdout.flush()
            yield

        elif event.type == TurnEventType.TURN_END:
            print()
            yield

        elif event.type == TurnEventType.TOOL_CALL_START:
            # Show tool name with arguments
            tool_name = event.tool_name
            colored_tool_name = self._color(tool_name, Colors.CYAN)

            # Special handling for spawn_subagent to show detailed info
            if tool_name == "spawn_subagent":
                # Parse spawn_subagent arguments
                if event.tool_args:
                    try:
                        args = json.loads(event.tool_args) if isinstance(event.tool_args, str) else event.tool_args
                        prompt = args.get("prompt", args.get("task", ""))
                        agent_type = args.get("subagent_type", args.get("agentType", "general"))

                        # Show detailed spawn_subagent info
                        print()
                        print(f"  {self._color('→', Colors.BLUE)} {colored_tool_name}")
                        print(f"    {self._color('Type:', Colors.CYAN)} {self._color(agent_type, Colors.DIM)}")
                        if prompt:
                            # Show prompt preview
                            preview = prompt[:120] + "..." if len(prompt) > 120 else prompt
                            print(f"    {self._color('Task:', Colors.CYAN)} {preview}")
                        print()
                    except Exception:
                        # Fallback for parsing errors
                        print(f"\n  {self._color('→', Colors.BLUE)} {colored_tool_name}", end="")
                else:
                    print(f"\n  {self._color('→', Colors.BLUE)} {colored_tool_name}", end="")
            else:
                # Regular tool call handling
                print(f"\n  {self._color('→', Colors.BLUE)} {colored_tool_name}", end="")

                # Store arg summary for re-display after spinner
                arg_summary = ""
                # Show arguments in a user-friendly format
                if event.tool_args:
                    try:
                        args = json.loads(event.tool_args) if isinstance(event.tool_args, str) else event.tool_args

                        # Format common args for display
                        arg_summary = self._format_tool_args(tool_name, args)
                        if arg_summary:
                            print(f" {self._color('→', Colors.BLUE)} {self._color(arg_summary, Colors.DIM)}", end="")
                    except Exception:
                        pass  # If parsing fails, just show tool name

                sys.stdout.flush()

                # Quick loading animation for tool execution
                spinner_frames = ["⠋", "⠙", "⠹", "⠸"]
                for _ in range(3):  # Brief animation
                    frame = spinner_frames[_ % len(spinner_frames)]
                    sys.stdout.write(f"  {self._color(frame, Colors.CYAN)}")
                    sys.stdout.flush()
                    time.sleep(0.05)
                # Clear the spinner and redraw the tool info
                sys.stdout.write("\r\033[K")  # Clear to end of line
                sys.stdout.flush()
                # Redraw tool name and args on a fresh line
                print(f"  {self._color('→', Colors.BLUE)} {colored_tool_name}", end="")
                if arg_summary:
                    print(f" {self._color('→', Colors.BLUE)} {self._color(arg_summary, Colors.DIM)}", end="")
                sys.stdout.flush()

            yield

        elif event.type == TurnEventType.TOOL_CALL_DONE:
            # Special handling for spawn_subagent completion
            if event.tool_name == "spawn_subagent":
                print(self._color("✓ Subagent launched", Colors.GREEN))
            else:
                # Store tool args for later display in result
                if event.tool_call_id and event.tool_args:
                    self._pending_tool_args[event.tool_call_id] = event.tool_args
                # Tool call complete, waiting for result
                if not pending_approval:
                    print(self._color("✓", Colors.GREEN))
            sys.stdout.flush()
            yield

        elif event.type == TurnEventType.TOOL_RESULT:
            # Show tool result - strip XML tags and apply markdown
            result = event.tool_result
            tool_name = event.tool_name

            if result:
                # Strip XML tags first
                result = strip_xml_tags(result)
                result = result.strip()
                line_count = result.count("\n") + 1

                # Get tool args for display
                tool_args = self._pending_tool_args.get(event.tool_call_id, "")

                # Store result state for toggle
                result_state = ToolResultState(tool_name, result, tool_args)
                self._tool_results.append(result_state)
                self._result_index = len(self._tool_results) - 1

                # Format the tool args for display in header
                args_display = ""
                if tool_args:
                    try:
                        args_dict = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                        args_display = self._format_tool_args(tool_name, args_dict)
                    except Exception:
                        args_display = ""

                # Simple header with collapse hint
                collapse_icon = (
                    self._color("▼", Colors.GREEN) if not result_state.collapsed else self._color("▶", Colors.YELLOW)
                )
                collapse_text = "/toggle to collapse" if not result_state.collapsed else "/toggle to expand"
                # Show: [tool_name args]: (line_count) lines [toggle]
                print(
                    f"    {self._color(f'[{tool_name}]', Colors.CYAN)} {self._color(args_display, Colors.DIM)} {self._color(':', Colors.CYAN)} ({line_count} lines) [{collapse_icon} {collapse_text}]"
                )

                # Show content (collapsed or expanded) with markdown rendering
                if not result_state.collapsed:
                    # Expanded view - render markdown and show all
                    rendered = simple_markdown_render(result) if self.use_markdown else result
                    lines = rendered.split("\n")
                    for line in lines:
                        if line.strip():
                            print(f"      {self._color(line, Colors.DIM)}")
                    result_state.lines_shown = len(lines)
                else:
                    # Collapsed view - show summary only (with markdown)
                    rendered = simple_markdown_render(result) if self.use_markdown else result
                    lines = rendered.split("\n")
                    preview_lines = min(3, len(lines))
                    for i in range(preview_lines):
                        if lines[i].strip():
                            print(f"      {self._color(lines[i], Colors.DIM)}")
                    if line_count > preview_lines:
                        remaining = line_count - preview_lines
                        print(
                            f"      {self._color(f'... ({remaining} more lines, press Ctrl+O to expand)', Colors.DIM)}"
                        )
                    result_state.lines_shown = preview_lines
            else:
                # Empty result - also show args if available
                args_display = ""
                tool_args = self._pending_tool_args.get(event.tool_call_id, "")
                if tool_args:
                    try:
                        args_dict = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                        args_display = self._format_tool_args(tool_name, args_dict)
                    except Exception:
                        args_display = ""
                print(
                    f"    {self._color(f'[{tool_name}]', Colors.CYAN)} {self._color(args_display, Colors.DIM)} {self._color(':', Colors.CYAN)} {self._color('(no output)', Colors.DIM)}"
                )
            yield

        elif event.type == TurnEventType.ERROR:
            # Show error
            error = event.error or "Unknown error"
            print()
            print(self._color(f"❌ Error: {error}", Colors.RED))
            yield

        elif event.type == TurnEventType.CANCELLED:
            print()
            print(self._color("⚠️  Operation cancelled", Colors.YELLOW))
            yield

        elif event.type == TurnEventType.USAGE_UPDATE:
            # Could show token usage here
            yield

        elif event.type == TurnEventType.PLAN_GENERATED:
            # Show plan was generated
            if event.plan_steps:
                print()
                print(self._bold("📋 Plan:"))
                for i, step in enumerate(event.plan_steps, 1):
                    print(f"  {i}. {step}")
            yield

        elif event.type == TurnEventType.PLAN_STEP_START:
            # Show plan step starting
            if event.plan_step_index is not None:
                print()
                print(self._color(f"▶ Step {event.plan_step_index + 1}", Colors.GREEN))
            yield

        elif event.type == TurnEventType.PLAN_STEP_DONE:
            # Plan step complete
            print(self._color(" ✓", Colors.GREEN))
            yield

        elif event.type == TurnEventType.RESEARCH_NOTE_SAVED:
            # Research note saved
            print()
            print(self._color("📝 Research note saved", Colors.BLUE))
            yield

        elif event.type == TurnEventType.SUBAGENT_SPAWNED:
            # Subagent started - show elaborate animation
            print()
            print(self._color("  🧪", Colors.MAGENTA), end=" ")
            print(self._bold("Initializing subagent..."), end=" ")

            # Matrix-style initialization animation
            matrix_chars = "01─|/\\*"
            for _ in range(12):
                chars = "".join(random.choice(matrix_chars) for _ in range(8))
                sys.stdout.write(f"\r{self._color('  🧪', Colors.MAGENTA)} {self._color(chars, Colors.GREEN)}")
                sys.stdout.flush()
                time.sleep(0.04)

            sys.stdout.write("\r" + " " * 40 + "\r")
            # Show what the subagent is doing and the prompt
            task = event.metadata.get("task", "working")
            prompt = event.metadata.get("prompt", event.text or "")
            print(self._color(f"🔄 Subagent active ({task} | {prompt})", Colors.MAGENTA))
            yield

        elif event.type == TurnEventType.SUBAGENT_COMPLETED:
            # Subagent finished - show completion animation
            print(self._color("  ✓", Colors.GREEN), end=" ")
            print(self._color("Subagent analysis complete", Colors.GREEN))

            # Success flash animation
            for _ in range(2):
                sys.stdout.write(
                    f"\r{self._color('  ⚡', Colors.YELLOW)} {self._color('Analysis complete!', Colors.GREEN)}"
                )
                sys.stdout.flush()
                time.sleep(0.08)

            sys.stdout.write("\r" + " " * 40 + "\r")
            print(self._color("  ✓", Colors.GREEN), end=" ")
            print(self._color("Results integrated", Colors.GREEN))
            yield

        elif event.type == TurnEventType.EXPLORATION_PHASE_CHANGE:
            # Exploration phase transition
            old_phase = event.metadata.get("from_phase", "")
            new_phase = event.metadata.get("to_phase", "")
            reason = event.text or event.metadata.get("reason", "")

            # Phase icons
            phase_icons = {"explore": "🔍", "plan": "📋", "execute": "⚡", "save": "💾"}

            old_icon = phase_icons.get(old_phase, "🔄")
            new_icon = phase_icons.get(new_phase, "🔄")

            print()
            print(self._color(f"{old_icon} Phase: {old_phase.upper()} → {new_phase.upper()} {new_icon}", Colors.CYAN))
            if reason:
                print(self._color(f"   {reason}", Colors.DIM))
            print()
            yield

        # Default: ignore other event types
        yield

    def _prompt_approval(
        self,
        tool_name: str,
        tool_args: str,
        parameter_descriptions: dict[str, str] | None = None,
    ) -> str:
        """Prompt user for tool approval.

        Args:
            tool_name: Name of tool being called
            tool_args: JSON string of tool arguments
            parameter_descriptions: Optional parameter descriptions

        Returns:
            User decision ("y", "n", or "a" for all)
        """
        # Parse args for display
        try:
            import json

            args = json.loads(tool_args) if tool_args else {}
        except Exception:
            args = {}

        # Show tool call details
        print()
        print(self._bold("Tool Call:"))
        print(f"  {self._color('Tool:', Colors.CYAN)} {tool_name}")

        # Check for dangerous shell command
        is_dangerous = False
        danger_warning = ""
        if tool_name == "shell_command":
            command = args.get("command", "")
            if command:
                from ..tools.shell_tools import check_dangerous_command

                is_dangerous, danger_reason, detected_patterns = check_dangerous_command(command)
                if is_dangerous:
                    danger_warning = danger_reason
                    print()
                    print(self._color("⚠️  DANGEROUS COMMAND WARNING!", Colors.BRIGHT_RED))
                    print(self._color(f"Reason: {danger_warning}", Colors.YELLOW))
                    if detected_patterns:
                        print(f"{self._color('Detected patterns:', Colors.DIM)} {', '.join(detected_patterns)}")

        # Show arguments
        if args:
            print()
            print(f"  {self._color('Arguments:', Colors.CYAN)}")
            for key, value in args.items():
                desc = parameter_descriptions.get(key, "") if parameter_descriptions else ""
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                print(f"    {key}: {value_str}")
                if desc:
                    print(f"      ({self._color(desc, Colors.DIM)})")

        # Prompt for decision
        while True:
            print()
            if is_dangerous:
                response = (
                    input(
                        self._color("⚠️  This command is DANGEROUS. Really approve? ", Colors.BRIGHT_RED)
                        + "[Y]es/[N]o: "
                    )
                    .strip()
                    .lower()
                )
            else:
                response = input(self._color("Approve? ", Colors.YELLOW) + "[Y]es/[N]o/[A]ll: ").strip().lower()

            if response in ("y", "yes", ""):
                return "y"
            elif response in ("n", "no"):
                return "n"
            elif response in ("a", "all") and not is_dangerous:
                # Dangerous commands don't allow "all" approval
                return "a"
            else:
                if is_dangerous and response in ("a", "all"):
                    print(self._color("Cannot auto-approve dangerous commands. Please enter Y or N.", Colors.RED))
                else:
                    print(self._color("Invalid response. Please enter Y, N, or A.", Colors.RED))

    def print_header(self, controller=None) -> None:
        """Print Spectra CLI header with ASCII art and disclaimer.

        Args:
            controller: Optional CLISessionController for config access
        """
        # SPECTRA ASCII Art Logo
        ascii_art = f"""
{Colors.CYAN}    ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
   █{Colors.RESET}  ██╗    ██╗███████╗██████╗ ███╗   ███╗ ██████╗ ███████╗ {Colors.CYAN}█
   █{Colors.RESET}  ██║    ██║██╔════╝██╔══██╗████╗ ████║██╔═══██╗██╔════╝ {Colors.CYAN}█
   █{Colors.RESET}  ██║    ██║███████╗██████╔╝██╔████╔██║██║   ██║███████╗ {Colors.CYAN}█
   █{Colors.RESET}  ██║    ██║╚════██║██╔══██╗██║╚██╔╝██║██║   ██║╚════██║ {Colors.CYAN}█
   █{Colors.RESET}  ███████╗███████║██████╔╝██║ ╚═╝ ██║╚██████╔╝███████║ {Colors.CYAN}█
   █{Colors.RESET}  ╚══════╝╚══════╝╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚══════╝ {Colors.CYAN}█
{Colors.CYAN}    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀{Colors.RESET}

{Colors.BOLD}{Colors.CYAN}  ████████╗██╗  ██╗███████╗██╗     ██╗███╗   ██╗ ██████╗ ███████╗
  ██╔════╝██║  ██║██╔════╝██║     ██║████╗  ██║██╔═══██╗██╔════╝
  █████╗  ███████║███████╗██║     ██║██╔██╗ ██║██║   ██║███████╗
  ██╔══╝  ██╔══██║╚════██║██║     ██║██║╚██╗██║██║   ██║╚════██║
  ██║    ██║  ██║███████║███████╗██║██║ ╚████║╚██████╔╝███████║
  ╚═╝    ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝{Colors.RESET}
"""
        print(ascii_art)

        # Header box
        print(self._color("╔══════════════════════════════════════════════════════════════╗", Colors.CYAN))
        print(
            self._color("║", Colors.CYAN)
            + self._color("  Spectra CLI - AI-Powered Security Analysis Shell    ", Colors.BOLD)
            + self._color(" ║", Colors.CYAN)
        )
        print(self._color("╚══════════════════════════════════════════════════════════════╝", Colors.CYAN))
        print()

        # Check if disclaimer was already accepted
        disclaimer_accepted = False
        if controller:
            disclaimer_accepted = controller.config.disclaimer_accepted

        if disclaimer_accepted:
            # Skip disclaimer if already accepted
            return

        # Comprehensive Disclaimer
        disclaimer = f"""
{Colors.YELLOW}⚠️  DISCLAIMER - LEGAL WARNING AND TERMS OF USE{Colors.RESET}
{Colors.DIM}═══════════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}1. EDUCATIONAL AND RESEARCH PURPOSES ONLY{Colors.RESET}
   Spectra is designed EXCLUSIVELY for:
   • Authorized security testing and penetration testing
   • Educational research and academic study
   • Vulnerability disclosure programs (bug bounties)
   • CTF (Capture The Flag) competitions
   • Analysis of systems you OWN or have EXPLICIT PERMISSION to test

{Colors.BOLD}2. PROHIBITED USES{Colors.RESET}
   Using Spectra for any of the following is STRICTLY PROHIBITED:
   • Unauthorized access to computer systems (hacking without permission)
   • Cyberattacks on systems you do not own or lack authorization
   • Any illegal activity under applicable local, state, federal, or international law
   • Violating terms of service of any platform or service
   • Harassment, stalking, or any malicious activity

{Colors.BOLD}3. USER RESPONSIBILITY{Colors.RESET}
   By using Spectra, you agree that:
   • YOU are solely responsible for your actions
   • YOU must verify you have authorization before analyzing any system
   • YOU must comply with all applicable laws and regulations
   • The authors, contributors, and maintainers of Spectra are NOT liable
     for ANY misuse, damage, legal consequences, or illegal activities
     committed with this tool

{Colors.BOLD}4. JURISDICTION AND COMPLIANCE{Colors.RESET}
   Laws vary by jurisdiction. It is YOUR responsibility to:
   • Understand and comply with laws in your location
   • Obtain necessary permissions before security testing
   • Follow responsible disclosure practices for vulnerabilities found

   Relevant laws may include (but are not limited to):
   • Computer Fraud and Abuse Act (USA) / CFAA
   • Computer Misuse Act (UK)
   • GDPR, CCPA, and data protection laws
   • Local cybersecurity and hacking laws
   • International treaties and conventions

{Colors.BOLD}5. NO WARRANTY{Colors.RESET}
   Spectra is provided "AS IS" without warranty of any kind. The authors
   and contributors disclaim all warranties, express or implied, including
   warranties of merchantability, fitness for a particular purpose, and
   non-infringement.

{Colors.BOLD}6. INDEMNIFICATION{Colors.RESET}
   By using Spectra, you agree to indemnify and hold harmless the authors,
   contributors, and maintainers from any claims, damages, losses, liabilities,
   legal fees, and expenses arising from your use or misuse of this software.

{Colors.BOLD}7. AGE AND CONSENT{Colors.RESET}
   You must be of legal age in your jurisdiction to use this software. By
   using Spectra, you represent that you have the legal authority to agree
   to these terms.

{Colors.DIM}═══════════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.DIM}If you do not agree to these terms, DO NOT use this software.{Colors.RESET}
{Colors.DIM}Press Ctrl+C now to exit, or press Enter to continue...{Colors.RESET}
"""
        print(disclaimer, end="", flush=True)

        # Wait for user acknowledgment
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting Spectra CLI.")
            sys.exit(0)

        # Mark disclaimer as accepted and save
        if controller:
            controller.config.disclaimer_accepted = True
            controller.config.save()

        print()  # Empty line after disclaimer
        print()

    def print_welcome(self, provider_name: str, model_name: str, has_api_key: bool) -> None:
        """Print welcome message with provider info.

        Args:
            provider_name: LLM provider name
            model_name: Model name
            has_api_key: Whether API key is configured
        """
        key_status = self._color("✓ Set", Colors.GREEN) if has_api_key else self._color("✗ Not set", Colors.YELLOW)

        print(f"Provider: {self._color(provider_name, Colors.CYAN)}")
        print(f"Model:    {self._color(model_name, Colors.CYAN)}")
        print(f"API Key:  {key_status}")
        print()
        print(self._color("Type /help for commands, or just start chatting!", Colors.DIM))
        print()

    def print_error(self, message: str) -> None:
        """Print error message.

        Args:
            message: Error message to display
        """
        print(self._color(f"❌ {message}", Colors.RED))

    def print_success(self, message: str) -> None:
        """Print success message.

        Args:
            message: Success message to display
        """
        print(self._color(f"✓ {message}", Colors.GREEN))

    def print_info(self, message: str) -> None:
        """Print info message.

        Args:
            message: Info message to display
        """
        print(self._color(f"ℹ {message}", Colors.BLUE))

    def print_warning(self, message: str) -> None:
        """Print warning message.

        Args:
            message: Warning message to display
        """
        print(self._color(f"⚠ {message}", Colors.YELLOW))

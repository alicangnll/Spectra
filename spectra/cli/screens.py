"""Full-screen overlays: disclaimer, session picker, model picker.

Each screen dismisses with a plain value (bool / session-id str / model
name str); the app reacts. The disclaimer text is the same seven-section
legal notice the legacy shell printed at startup.
"""

from __future__ import annotations

from textual import events
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

DISCLAIMER_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "1. EDUCATIONAL AND RESEARCH PURPOSES ONLY",
        [
            "Spectra is designed EXCLUSIVELY for:",
            "• Authorized security testing and penetration testing",
            "• Educational research and academic study",
            "• Vulnerability disclosure programs (bug bounties)",
            "• CTF (Capture the Flag) competitions",
            "• Analysis of systems you OWN or have EXPLICIT PERMISSION to test",
        ],
    ),
    (
        "2. PROHIBITED USES",
        [
            "Using Spectra for any of the following is STRICTLY PROHIBITED:",
            "• Unauthorized access to computer systems (hacking without permission)",
            "• Cyberattacks on systems you do not own or lack authorization",
            "• Any illegal activity under applicable local, state, federal, or international law",
            "• Violating terms of service of any platform or service",
            "• Harassment, stalking, or any malicious activity",
        ],
    ),
    (
        "3. USER RESPONSIBILITY",
        [
            "By using Spectra, you agree that:",
            "• YOU are solely responsible for your actions",
            "• YOU must verify you have authorization before analyzing any system",
            "• YOU must comply with all applicable laws and regulations",
            "• The authors, contributors, and maintainers of Spectra are NOT liable",
            "  for ANY misuse, damage, legal consequences, or illegal activities",
            "  committed with this tool",
        ],
    ),
    (
        "4. JURISDICTION AND COMPLIANCE",
        [
            "Laws vary by jurisdiction. It is YOUR responsibility to:",
            "• Understand and comply with laws in your location",
            "• Obtain necessary permissions before security testing",
            "• Follow responsible disclosure practices for vulnerabilities found",
            "",
            "Relevant laws may include (but are not limited to):",
            "• Computer Fraud and Abuse Act (USA) / CFAA",
            "• Computer Misuse Act (UK)",
            "• GDPR, CCPA, and data protection laws",
            "• Local cybersecurity and hacking laws",
            "• International treaties and conventions",
        ],
    ),
    (
        "5. NO WARRANTY",
        [
            'Spectra is provided "AS IS" without warranty of any kind. The authors',
            "and contributors disclaim all warranties, express or implied, including",
            "warranties of merchantability, fitness for a particular purpose, and",
            "non-infringement.",
        ],
    ),
    (
        "6. INDEMNIFICATION",
        [
            "By using Spectra, you agree to indemnify and hold harmless the authors,",
            "contributors, and maintainers from any claims, damages, losses,",
            "liabilities, legal fees, and expenses arising from your use or misuse",
            "of this software.",
        ],
    ),
    (
        "7. AGE AND CONSENT",
        [
            "You must be of legal age in your jurisdiction to use this software. By",
            "using Spectra, you represent that you have the legal authority to",
            "agree to these terms.",
        ],
    ),
]


def disclaimer_markdown() -> str:
    lines = ["# DISCLAIMER — LEGAL WARNING AND TERMS OF USE", ""]
    for title, bullets in DISCLAIMER_SECTIONS:
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(bullets)
        lines.append("")
    lines.append("If you do not agree to these terms, DO NOT use this software.")
    return "\n".join(lines)


class DisclaimerScreen(ModalScreen[bool]):
    """First-run legal disclaimer; Accept persists, Decline exits."""

    BINDINGS = [
        ("a,enter", "accept", "Accept"),
        ("escape,q", "decline", "Decline"),
    ]

    def compose(self):
        with Vertical(classes="disclaimer"):
            yield Static("⚠️  DISCLAIMER — LEGAL WARNING AND TERMS OF USE", classes="modal-title")
            with VerticalScroll(classes="disclaimer-scroll"):
                yield Static(disclaimer_markdown(), markup=False)
            with Vertical(classes="modal-buttons"):
                yield Button("Accept", variant="success", id="accept")
                yield Button("Decline", variant="error", id="decline")
            yield Static("[a] accept   [esc] decline and exit", classes="modal-hint", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "accept")

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_decline(self) -> None:
        self.dismiss(False)


class SessionPickerScreen(ModalScreen[str]):
    """Pick a saved CLI session; dismisses with its id ('' = cancel)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, sessions: list[dict]) -> None:
        super().__init__()
        self.sessions = sessions

    def compose(self):
        import datetime as _dt

        with Vertical(classes="picker"):
            yield Static("Saved sessions", classes="modal-title")
            table = DataTable(id="session-table")
            table.add_columns("ID", "Description", "Created", "Msgs")
            table.cursor_type = "row"
            for s in self.sessions:
                created = s.get("timestamp", 0)
                when = (
                    _dt.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
                    if created
                    else "?"
                )
                sid = s.get("id", "")
                table.add_row(
                    sid[:8],
                    str(s.get("description", "Unnamed"))[:60],
                    when,
                    str(s.get("message_count", 0)),
                    key=sid,
                )
            yield table
            yield Static("[enter] load   [esc] cancel", classes="modal-hint", markup=False)

    def on_mount(self) -> None:
        table = self.query_one("#session-table", DataTable)
        table.focus()
        if table.row_count:
            table.cursor_row = 0

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(event.row_key.value or "")

    def action_cancel(self) -> None:
        self.dismiss("")


class ModelPickerScreen(ModalScreen[str]):
    """Pick an available model; dismisses with its name ('' = cancel)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, models: list[str], current: str = "") -> None:
        super().__init__()
        self.models = models
        self.current = current

    def compose(self):
        with Vertical(classes="picker"):
            yield Static("Select model", classes="modal-title")
            table = DataTable(id="model-table")
            table.add_columns("Model", "")
            table.cursor_type = "row"
            for name in self.models:
                marker = "● current" if name == self.current else ""
                table.add_row(name, marker, key=name)
            yield table
            yield Static("[enter] select   [esc] cancel", classes="modal-hint", markup=False)

    def on_mount(self) -> None:
        table = self.query_one("#model-table", DataTable)
        table.focus()
        for i, name in enumerate(self.models):
            if name == self.current:
                table.cursor_row = i
                break

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(event.row_key.value or "")

    def action_cancel(self) -> None:
        self.dismiss("")

"""Agent creation dialog for adding new skills/agents from the UI."""

from pathlib import Path
from typing import Any

from ..core.logging import log_debug, log_error, log_info
from ..core.auto_reload import trigger_reload
from .qt_compat import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    qt_run,
)


class AgentCreatorDialog(QDialog):
    """Dialog for creating new agents/skills from the UI."""

    def __init__(self, skills_dir: Path, parent=None):
        super().__init__(parent)
        self._skills_dir = skills_dir
        self._agent_name = ""
        self._agent_description = ""
        self._agent_tags = []
        self._agent_mode = "plan"
        self._task_content = ""
        self._created_skill_path = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Create New Agent")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QLabel { color: #d4d4d4; font-size: 12px; }"
            "QLineEdit, QPlainTextEdit, QComboBox { "
            "background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
            "border-radius: 4px; padding: 6px; font-size: 12px; }"
            "QPlainTextEdit { font-family: 'Consolas', 'Monaco', monospace; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox::down-arrow { width: 12px; height: 12px; }"
            "QTabWidget::pane { border: 1px solid #3c3c3c; background: #1e1e1e; }"
            "QTabBar::tab { background: #2d2d2d; color: #808080; padding: 6px 16px; "
            "border: 1px solid #3c3c3c; border-bottom: none; font-size: 11px; }"
            "QTabBar::tab:selected { color: #d4d4d4; background: #1e1e1e; }"
            "QTabBar::tab:hover:!selected { color: #d4d4d4; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Instructions
        info_label = QLabel(
            "Create a new agent by defining a skill. The agent will be available "
            "via the /<agent-name> command after creation."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #808080; font-size: 11px; padding: 4px;")
        layout.addWidget(info_label)

        # Tab widget for Basic and Advanced sections
        tabs = QTabWidget()
        tabs.setObjectName("agent_creator_tabs")

        # Basic tab
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        basic_layout.setContentsMargins(12, 12, 12, 12)
        basic_layout.setSpacing(8)

        # Agent name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-custom-agent")
        self._name_edit.textChanged.connect(self._validate_inputs)
        basic_layout.addRow("Agent Name:", self._name_edit)

        # Description
        self._description_edit = QLineEdit()
        self._description_edit.setPlaceholderText("Custom analysis agent for specific tasks")
        basic_layout.addRow("Description:", self._description_edit)

        # Tags
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("custom, analysis, specialized")
        basic_layout.addRow("Tags (comma-separated):", self._tags_edit)

        # Mode
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["plan", "auto", "explore"])
        self._mode_combo.setCurrentText("plan")
        basic_layout.addRow("Mode:", self._mode_combo)

        tabs.addTab(basic_tab, "Basic")

        # Advanced tab
        advanced_tab = QWidget()
        advanced_layout = QFormLayout(advanced_tab)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_layout.setSpacing(8)

        # Task definition
        self._task_edit = QPlainTextEdit()
        self._task_edit.setPlaceholderText(
            "Task: This agent performs specific analysis.\n"
            "\n"
            "## Approach\n"
            "- Step 1: ...\n"
            "- Step 2: ...\n"
            "\n"
            "## Tools Used\n"
            "- tool_name_1\n"
            "- tool_name_2\n"
            "\n"
            "## Expected Output\n"
            "- ..."
        )
        self._task_edit.setMinimumHeight(300)
        advanced_layout.addRow("Task Definition (markdown):", self._task_edit)

        tabs.addTab(advanced_tab, "Advanced")

        layout.addWidget(tabs)

        # Template selection
        template_layout = QVBoxLayout()
        template_label = QLabel("Start from template:")
        template_label.setStyleSheet("font-weight: bold; color: #d4d4d4;")
        template_layout.addWidget(template_label)

        template_buttons_layout = QVBoxLayout()
        template_buttons_layout.setSpacing(4)

        self._template_generic = QPushButton("Generic Analysis Agent")
        self._template_generic.clicked.connect(lambda: self._load_template("generic"))
        template_buttons_layout.addWidget(self._template_generic)

        self._template_vuln = QPushButton("Vulnerability Audit Agent")
        self._template_vuln.clicked.connect(lambda: self._load_template("vuln"))
        template_buttons_layout.addWidget(self._template_vuln)

        self._template_crypto = QPushButton("Crypto Analysis Agent")
        self._template_crypto.clicked.connect(lambda: self._load_template("crypto"))
        template_buttons_layout.addWidget(self._template_crypto)

        self._template_custom = QPushButton("Custom/Empty Agent")
        self._template_custom.clicked.connect(lambda: self._load_template("custom"))
        template_buttons_layout.addWidget(self._template_custom)

        template_layout.addLayout(template_buttons_layout)
        layout.addLayout(template_layout)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #808080; font-size: 11px; padding: 4px;")
        layout.addWidget(self._status_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(
            "QPushButton { background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
            "border-radius: 4px; padding: 6px 16px; font-size: 11px; min-width: 80px; }"
            "QPushButton:hover { background: #3c3c3c; }"
            "QPushButton:disabled { color: #505050; }"
        )
        buttons.accepted.connect(self._on_create)
        buttons.rejected.connect(self.reject)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)
        layout.addWidget(buttons)

    def _validate_inputs(self) -> None:
        """Enable OK button only when required fields are filled."""
        name = self._name_edit.text().strip()
        valid = bool(name and name.replace("-", "").replace("_", "").isalnum())
        self._ok_button.setEnabled(valid)

        if valid:
            self._status_label.setText(f"Agent will be created as: /{name}")
        else:
            self._status_label.setText("")

    def _load_template(self, template_type: str) -> None:
        """Load a predefined template into the form."""
        if template_type == "generic":
            self._name_edit.setText("my-analysis-agent")
            self._description_edit.setText("Custom binary analysis agent")
            self._tags_edit.setText("custom, analysis, binary")
            self._mode_combo.setCurrentText("plan")
            self._task_edit.setPlainText(
                """Task: This agent performs custom binary analysis tasks.

## Approach
- Analyze the binary structure and functions
- Identify key patterns and behaviors
- Provide detailed findings and recommendations

## Tools Used
- decompile_function
- search_functions
- get_disassembly
- list_imports
- list_exports

## Workflow
1. Understand the user's analysis goal
2. Search for relevant functions and patterns
3. Decompile and analyze key functions
4. Cross-reference findings
5. Provide comprehensive report

## Expected Output
- Detailed analysis of target functions
- Identification of suspicious patterns
- Recommendations for further investigation"""
            )

        elif template_type == "vuln":
            self._name_edit.setText("my-vuln-audit")
            self._description_edit.setText("Custom vulnerability audit agent")
            self._tags_edit.setText("security, vuln-audit, vulnerability")
            self._mode_combo.setCurrentText("plan")
            self._task_edit.setPlainText(
                """Task: This agent performs security vulnerability assessment.

## Approach
- Search for dangerous API usage patterns
- Check for common vulnerability classes
- Analyze input validation and sanitization
- Identify potential security weaknesses

## Tools Used
- search_functions
- decompile_function
- get_disassembly
- list_imports
- xref_search

## Workflow
1. Scan for dangerous API calls (CreateRemoteThread, WriteProcessMemory, etc.)
2. Check for buffer overflow patterns
3. Analyze string handling and memory operations
4. Review input validation mechanisms
5. Generate vulnerability report with severity ratings

## Expected Output
- List of found vulnerabilities with severity
- Code locations for each finding
- Explanation of risk and impact
- Recommendations for remediation"""
            )

        elif template_type == "crypto":
            self._name_edit.setText("my-crypto-analyzer")
            self._description_edit.setText("Cryptographic algorithm analyzer")
            self._tags_edit.setText("crypto, encryption, analysis")
            self._mode_combo.setCurrentText("plan")
            self._task_edit.setPlainText(
                """Task: This agent analyzes cryptographic usage in the binary.

## Approach
- Identify crypto API usage patterns
- Detect constants and key materials
- Analyze algorithm implementations
- Evaluate cryptographic security

## Tools Used
- search_functions
- decompile_function
- search_bytes
- list_imports
- get_disassembly

## Workflow
1. Search for cryptographic API calls (CryptEncrypt, etc.)
2. Scan for constant values that may be keys/IVs
3. Analyze crypto algorithm implementations
4. Check for weak algorithms or improper usage
5. Report findings with security assessment

## Expected Output
- List of cryptographic algorithms found
- Key material locations (if any)
- Security assessment of crypto usage
- Recommendations for improvements"""
            )

        elif template_type == "custom":
            self._name_edit.setText("")
            self._description_edit.setText("")
            self._tags_edit.setText("")
            self._mode_combo.setCurrentText("plan")
            self._task_edit.setPlainText(
                """Task: This agent performs [describe what this agent does].

## Approach
- [Step 1 description]
- [Step 2 description]
- [Step 3 description]

## Tools Used
- tool_name_1
- tool_name_2

## Workflow
1. [Workflow step 1]
2. [Workflow step 2]
3. [Workflow step 3]

## Expected Output
- [Expected output 1]
- [Expected output 2]"""
            )

        # Switch to advanced tab to show the task
        tabs = self.findChild(QTabWidget, "agent_creator_tabs")
        if tabs:
            tabs.setCurrentIndex(1)

    def _on_create(self) -> None:
        """Create the agent skill directory and files."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Agent name cannot be empty")
            return

        # Validate name (alphanumeric, dashes, underscores only)
        if not name.replace("-", "").replace("_", "").isalnum():
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Agent name must contain only alphanumeric characters, dashes, and underscores",
            )
            return

        # Gather form data
        description = self._description_edit.text().strip() or f"Custom agent: {name}"
        tags_str = self._tags_edit.text().strip() or "custom"
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        mode = self._mode_combo.currentText()
        task_content = self._task_edit.toPlainText().strip()

        if not task_content:
            task_content = f"""Task: This agent performs custom analysis tasks.

## Approach
- Analyze the binary based on user requirements
- Provide detailed findings and insights

## Tools Used
- decompile_function
- search_functions

## Expected Output
- Detailed analysis results
- Actionable recommendations"""

        # Create skill directory
        skill_dir = self._skills_dir / name
        if skill_dir.exists():
            result = QMessageBox.question(
                self,
                "Agent Exists",
                f"An agent named '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result == QMessageBox.StandardButton.No:
                return

        try:
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Create skill.md file
            skill_md_content = f"""---
name: {name.replace("-", " ").replace("_", " ").title()}
description: {description}
tags: {tags}
mode: {mode}
---

{task_content}
"""

            skill_md_path = skill_dir / "skill.md"
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(skill_md_content)

            self._created_skill_path = skill_dir

            log_info(f"Created agent skill at: {skill_dir}")

            # Show success message
            QMessageBox.information(
                self,
                "Agent Created",
                f"Agent '{name}' has been created successfully!\n\n"
                f"Location: {skill_dir}\n\n"
                f"The agent will be available after Spectra reloads.\n"
                f"Use: /{name}",
            )

            # Trigger auto-reload
            try:
                trigger_reload()
                log_info("Triggered auto-reload after agent creation")
            except Exception as e:
                log_debug(f"Auto-reload trigger failed: {e}")

            self.accept()

        except Exception as e:
            log_error(f"Failed to create agent: {e}")
            QMessageBox.critical(
                self,
                "Creation Failed",
                f"Failed to create agent '{name}':\n{str(e)}",
            )

    def get_created_skill_path(self) -> Path | None:
        """Return the path to the created skill directory."""
        return self._created_skill_path

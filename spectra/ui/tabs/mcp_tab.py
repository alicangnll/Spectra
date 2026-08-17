"""MCP settings tab: enable/disable Spectra and external MCP servers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.config import SpectraConfig
from ...core.logging import log_debug, log_warn
from ...mcp.config import MCPServerConfig
from ...mcp.security import get_security_validator
from ..qt_compat import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..settings_service import SettingsService


class MCPTab(QWidget):
    """Tab for managing MCP servers: Spectra configured + external MCP."""

    def __init__(self, config: SpectraConfig, service: SettingsService, parent: QWidget = None):
        super().__init__(parent)
        self._config = config
        self._service = service
        self._spectra_checks: dict[str, QCheckBox] = {}
        self._external_checks: dict[str, QCheckBox] = {}
        self._spectra_servers: list[MCPServerConfig] = list(service.mcp.spectra)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Spectra MCP servers (pre-loaded by service)
        spectra_group = self._build_spectra_group()
        layout.addWidget(spectra_group)

        # External MCP (pre-loaded by service)
        for source_key, servers in sorted(self._service.mcp.external.items()):
            group = self._build_external_group(source_key, servers)
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _build_spectra_group(self) -> QGroupBox:
        """Build the Spectra MCP servers group box."""
        group = QGroupBox("Spectra MCP Servers")
        layout = QVBoxLayout(group)

        # Common button style matching Spectra's overall UI
        _BUTTON_STYLE = (
            "QPushButton { background: #252526; color: #cccccc; border: 1px solid #383838; "
            "border-radius: 4px; padding: 4px 6px; font-size: 11px; font-weight: 500; min-height: 22px; }"
            "QPushButton:hover { background: #3c3c3c; }"
        )

        # Add "Select All" and "Add Server" button row (always show)
        button_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip("Enable all Spectra MCP servers")
        select_all_btn.setStyleSheet(_BUTTON_STYLE)
        select_all_btn.clicked.connect(lambda: self._select_all_spectra_mcp(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setToolTip("Disable all Spectra MCP servers")
        deselect_all_btn.setStyleSheet(_BUTTON_STYLE)
        deselect_all_btn.clicked.connect(lambda: self._select_all_spectra_mcp(False))
        add_server_btn = QPushButton("Add Server")
        add_server_btn.setToolTip("Add a new MCP server")
        add_server_btn.setStyleSheet(_BUTTON_STYLE)
        add_server_btn.clicked.connect(self._add_server)
        button_row.addWidget(select_all_btn)
        button_row.addWidget(deselect_all_btn)
        button_row.addStretch()
        button_row.addWidget(add_server_btn)
        button_row.setSpacing(6)
        layout.addLayout(button_row)

        if not self._spectra_servers:
            no_servers_label = QLabel("No MCP servers configured")
            no_servers_label.setStyleSheet("color: #888; padding: 10px;")
            layout.addWidget(no_servers_label)
            return group

        for server in sorted(self._spectra_servers, key=lambda s: s.name):
            cb = QCheckBox(f"{server.name}  —  {server.command}")
            cb.setChecked(server.enabled)
            self._spectra_checks[server.name] = cb
            layout.addWidget(cb)

        return group

    def _select_all_spectra_mcp(self, checked: bool) -> None:
        """Select or deselect all Spectra MCP servers."""
        for checkbox in self._spectra_checks.values():
            checkbox.setChecked(checked)

    def _build_external_group(self, source_key: str, servers: list[MCPServerConfig]) -> QGroupBox:
        """Build a group box for external MCP servers from one source."""
        if source_key == "claude":
            title = "Claude Code MCP Servers"
        elif source_key == "codex":
            title = "Codex MCP Servers"
        else:
            title = f"{source_key} MCP Servers"

        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        # Common button style matching Spectra's overall UI
        _BUTTON_STYLE = (
            "QPushButton { background: #252526; color: #cccccc; border: 1px solid #383838; "
            "border-radius: 4px; padding: 4px 6px; font-size: 11px; font-weight: 500; min-height: 22px; }"
            "QPushButton:hover { background: #3c3c3c; }"
        )

        if not servers:
            layout.addWidget(QLabel("No MCP servers found"))
            return group

        enabled_set = set(self._config.enabled_external_mcp)

        # Add "Select All" button row for this source
        button_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip(f"Enable all {source_key} MCP servers")
        select_all_btn.setStyleSheet(_BUTTON_STYLE)
        select_all_btn.clicked.connect(lambda: self._select_all_external_mcp(source_key, True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setToolTip(f"Disable all {source_key} MCP servers")
        deselect_all_btn.setStyleSheet(_BUTTON_STYLE)
        deselect_all_btn.clicked.connect(lambda: self._select_all_external_mcp(source_key, False))
        button_row.addWidget(select_all_btn)
        button_row.addWidget(deselect_all_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        for server in sorted(servers, key=lambda s: s.name):
            ext_id = f"{source_key}:{server.name}"
            cb = QCheckBox(f"{server.name}  —  {server.command}")
            cb.setChecked(ext_id in enabled_set)
            self._external_checks[ext_id] = cb
            layout.addWidget(cb)

        return group

    def _select_all_external_mcp(self, source_key: str, checked: bool) -> None:
        """Select or deselect all external MCP servers from a specific source."""
        for ext_id, checkbox in self._external_checks.items():
            if ext_id.startswith(f"{source_key}:"):
                checkbox.setChecked(checked)

    def apply_to_config(self, config: SpectraConfig) -> None:
        """Write checkbox state back to config fields."""
        # Update Spectra MCP server enabled state
        for server in self._spectra_servers:
            cb = self._spectra_checks.get(server.name)
            if cb is not None:
                server.enabled = cb.isChecked()

        # Persist Spectra MCP config changes via the service
        if self._spectra_servers:
            self._service.save_mcp_servers(self._spectra_servers)

        # Enabled external MCP (checked = enabled)
        config.enabled_external_mcp = [ext_id for ext_id, cb in self._external_checks.items() if cb.isChecked()]

        log_debug(f"MCP config: {len(config.enabled_external_mcp)} external enabled")

    def _add_server(self) -> None:
        """Open dialog to add a new MCP server."""
        # First show category selection dialog
        category_dlg = MCPCategoryDialog(parent=self)
        if category_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        category = category_dlg.get_selected_category()

        dlg = AddMCPServerDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            server_data = dlg.get_server_data()
            if server_data:
                if category == "spectra":
                    # Check if server name already exists in Spectra
                    existing_names = {s.name for s in self._spectra_servers}
                    if server_data["name"] in existing_names:
                        QMessageBox.warning(
                            self,
                            "Duplicate Name",
                            f"An MCP server named '{server_data['name']}' already exists in Spectra.",
                        )
                        return

                    # Create new server config
                    new_server = MCPServerConfig(
                        name=server_data["name"],
                        command=server_data["command"],
                        args=server_data.get("args", []),
                        env=server_data.get("env", {}),
                        enabled=True,
                        timeout=server_data.get("timeout", 30.0),
                    )
                    self._spectra_servers.append(new_server)

                    # Refresh UI
                    self._refresh_spectra_group()
                    log_debug(f"Added MCP server to Spectra: {new_server.name}")
                else:
                    # For external categories, we'd need to handle them differently
                    # For now, just show info that this is not implemented
                    QMessageBox.information(
                        self,
                        "Not Implemented",
                        f"Adding MCP servers to {category.upper()} is not yet supported.\n"
                        "Currently, you can only add servers to Spectra MCP Servers.\n\n"
                        f"External MCP servers from {category.capitalize()} are auto-detected.",
                    )

    def _refresh_spectra_group(self) -> None:
        """Rebuild the Spectra MCP group with current servers."""
        # Find and remove the old spectra group
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QScrollArea):
                container = widget.widget()
                if container:
                    layout = container.layout()
                    for j in range(layout.count()):
                        item = layout.itemAt(j)
                        if item and isinstance(item.widget(), QGroupBox):
                            group = item.widget()
                            if group.title() == "Spectra MCP Servers":
                                # Remove old group
                                layout.removeWidget(group)
                                group.deleteLater()
                                # Add new group
                                new_group = self._build_spectra_group()
                                layout.insertWidget(j - 1, new_group)  # Insert before stretch
                                return


class AddMCPServerDialog(QDialog):
    """Dialog for adding a new MCP server."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Add MCP Server")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g., filesystem")
        form.addRow("Server Name:", self._name_edit)

        self._command_edit = QLineEdit()
        self._command_edit.setPlaceholderText("e.g., npx")
        form.addRow("Command:", self._command_edit)

        self._args_edit = QLineEdit()
        self._args_edit.setPlaceholderText("e.g., -y @modelcontextprotocol/server-filesystem")
        form.addRow("Arguments:", self._args_edit)

        self._env_edit = QLineEdit()
        self._env_edit.setPlaceholderText("e.g., KEY1=value1,KEY2=value2")
        form.addRow("Environment:", self._env_edit)

        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(1.0, 300.0)
        self._timeout_spin.setValue(30.0)
        self._timeout_spin.setSuffix(" seconds")
        form.addRow("Timeout:", self._timeout_spin)

        layout.addLayout(form)

        # Buttons with consistent styling
        _BUTTON_STYLE = (
            "QPushButton { background: #252526; color: #cccccc; border: 1px solid #383838; "
            "border-radius: 4px; padding: 6px 16px; font-size: 11px; font-weight: 500; min-height: 24px; }"
            "QPushButton:hover { background: #3c3c3c; }"
        )

        button_box = QHBoxLayout()
        ok_btn = QPushButton("Add")
        ok_btn.setStyleSheet(_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_box.addStretch()
        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

    def get_server_data(self) -> dict | None:
        """Validate and return server data, or None if invalid."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a server name.")
            return None

        command = self._command_edit.text().strip()
        if not command:
            QMessageBox.warning(self, "Missing Command", "Please enter a command.")
            return None

        # Parse arguments
        args = []
        args_text = self._args_edit.text().strip()
        if args_text:
            import shlex

            try:
                args = shlex.split(args_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Arguments", "Arguments could not be parsed. Use quotes for arguments with spaces."
                )
                return None

        # Parse environment variables
        env = {}
        env_text = self._env_edit.text().strip()
        if env_text:
            for pair in env_text.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    env[key.strip()] = value.strip()
                else:
                    QMessageBox.warning(self, "Invalid Environment", f"Invalid environment variable format: {pair}")
                    return None

        # SECURITY VALIDATION - Check the command and arguments for security issues
        validator = get_security_validator(strict_mode=True)
        is_allowed, warnings = validator.validate_server_config(
            name=name, command=command, args=args, env=env, timeout=self._timeout_spin.value()
        )

        # Build security warning message
        if warnings:
            warning_msg = "Security Validation Results:\n\n" + "\n".join(warnings) + "\n\n"
            if not is_allowed:
                # BLOCKED - Show error dialog
                warning_msg += (
                    "⛔ This MCP server configuration has been BLOCKED for security reasons.\n\n"
                    "The command or arguments contain potentially dangerous patterns that could "
                    "lead to arbitrary code execution or system compromise."
                )
                QMessageBox.critical(self, "Security Block", warning_msg)
                return None
            else:
                # Show warnings but allow in non-strict mode (for now)
                log_warn(f"MCP Server '{name}' added with security warnings: {warnings}")
                # In strict mode, warnings are allowed but we should inform the user
                pass

        return {
            "name": name,
            "command": command,
            "args": args,
            "env": env,
            "timeout": self._timeout_spin.value(),
        }


class MCPCategoryDialog(QDialog):
    """Dialog for selecting MCP server category."""

    CATEGORIES = [
        ("spectra", "Spectra MCP Servers", "Custom MCP servers configured in Spectra"),
        ("claude", "Claude Code MCP Servers", "External MCP servers from Claude Code"),
        ("codex", "Codex MCP Servers", "External MCP servers from Codex"),
    ]

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Select MCP Server Category")
        self.setMinimumWidth(450)
        self._selected_category = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Which type of MCP server do you want to add?")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #d4d4d4;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Select the category where you want to add the new MCP server:\n"
            "• Spectra: Custom servers you configure manually\n"
            "• Claude/Codex: External servers (auto-detected, read-only)"
        )
        desc.setStyleSheet("color: #888; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(10)

        # Category options
        from ..qt_compat import QButtonGroup, QRadioButton

        self._button_group = QButtonGroup(self)
        self._radio_buttons = {}

        for value, title, description in self.CATEGORIES:
            radio = QRadioButton(title)
            radio.setStyleSheet(
                "QRadioButton { color: #d4d4d4; font-size: 12px; }"
                "QRadioButton::indicator { width: 18px; height: 18px; }"
            )
            self._radio_buttons[value] = radio
            self._button_group.addButton(radio)

            # Description label
            desc_label = QLabel(f"  {description}")
            desc_label.setStyleSheet("color: #888; font-size: 10px; margin-left: 24px;")

            layout.addWidget(radio)
            layout.addWidget(desc_label)
            layout.addSpacing(5)

        # Select first option by default
        if self._radio_buttons:
            first_radio = next(iter(self._radio_buttons.values()))
            first_radio.setChecked(True)

        layout.addStretch()

        # Buttons
        _BUTTON_STYLE = (
            "QPushButton { background: #252526; color: #cccccc; border: 1px solid #383838; "
            "border-radius: 4px; padding: 6px 16px; font-size: 11px; font-weight: 500; min-height: 24px; }"
            "QPushButton:hover { background: #3c3c3c; }"
        )

        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Next")
        ok_btn.setStyleSheet(_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)

    def get_selected_category(self) -> str:
        """Return the selected category value."""
        for value, radio in self._radio_buttons.items():
            if radio.isChecked():
                return value
        return "spectra"  # Default fallback

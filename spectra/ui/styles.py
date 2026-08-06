"""Dark-theme stylesheet for Spectra UI."""

from __future__ import annotations

from .qt_compat import get_dpi_scale_factor, scale_font_size


def _get_scaled_theme() -> str:
    """Generate DPI-scaled dark theme stylesheet matching IDA Pro aesthetics."""
    scale = get_dpi_scale_factor()

    if scale > 2.0:
        scale = 2.0
    if scale < 1.0:
        scale = 1.0

    font_small = scale_font_size(12)
    font_normal = scale_font_size(14)
    font_medium = scale_font_size(15)
    font_large = scale_font_size(17)

    padding_small = int(4 * scale + 0.5)
    padding_normal = int(8 * scale + 0.5)
    padding_large = int(12 * scale + 0.5)

    font_mono = "'Consolas', 'JetBrains Mono', 'Fira Code', 'Courier New', monospace"

    return """
QWidget#spectra_panel {
    background-color: #141414;
    color: #d4d4d4;
}

QWidget#input_container {
    background-color: #1a1a1c;
    border-top: 1px solid #28282b;
    padding: 4px;
}

QScrollArea#chat_scroll {
    background-color: #141414;
    border: none;
}

QWidget#chat_container {
    background-color: #141414;
}

QFrame#message_user {
    background-color: #222225;
    border: 1px solid #2e2e33;
    border-radius: 8px;
    padding: """ + str(padding_normal) + """px;
    margin: 4px 10px 4px 10px;
}

QFrame#message_assistant {
    background-color: #18181b;
    border: 1px solid #242428;
    border-radius: 8px;
    padding: """ + str(padding_normal) + """px;
    margin: 4px 10px 4px 10px;
}

QFrame#message_tool {
    background-color: #1e1e22;
    border: 1px solid #2c2c32;
    border-left: 3px solid #4ec9b0;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 3px 12px;
}

QFrame#message_error {
    background-color: #281a1a;
    border: 1px solid #4a2424;
    border-left: 3px solid #f44747;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 3px 12px;
}

QFrame#message_thinking {
    background-color: #18181c;
    border: 1px solid #282830;
    border-radius: 6px;
    padding: 4px 10px;
    margin: 2px 10px;
}

QLabel#tool_header {
    color: #3a9fd5;
    font-weight: bold;
    font-size: """ + str(font_small) + """px;
    font-family: """ + font_mono + """;
}

QLabel#tool_content {
    color: #9cdcfe;
    font-family: """ + font_mono + """;
    font-size: """ + str(font_small) + """px;
}

QPlainTextEdit#input_area {
    background-color: #222225;
    color: #e0e0e0;
    border: 1.5px solid #333338;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: """ + str(font_normal) + """px;
    font-family: """ + font_mono + """;
    selection-background-color: #094771;
    min-height: """ + str(int(36 * scale)) + """px;
    max-height: """ + str(int(90 * scale)) + """px;
}

QPlainTextEdit#input_area:focus {
    border-color: #3a9fd5;
    background-color: #26262a;
}

QPushButton#send_button {
    background-color: #094771;
    color: #ffffff;
    border: 1px solid #135d96;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: """ + str(font_normal) + """px;
    min-height: 28px;
}

QPushButton#send_button:hover {
    background-color: #10598c;
    border-color: #3a9fd5;
}

QPushButton#send_button:pressed {
    background-color: #073454;
}

QPushButton#send_button:disabled {
    background-color: #222225;
    color: #55555d;
    border-color: #2a2a2e;
}

QPushButton#cancel_button {
    background-color: #3d1c1c;
    color: #f44747;
    border: 1px solid #5c2727;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: """ + str(font_normal) + """px;
    min-height: 28px;
}

QPushButton#cancel_button:hover {
    background-color: #522222;
    color: #ffffff;
    border-color: #f44747;
}

QPushButton {
    background-color: #222225;
    color: #cccccc;
    border: 1px solid #333338;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: """ + str(font_small) + """px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #2c2c30;
    color: #ffffff;
    border-color: #44444a;
}

QPushButton:disabled {
    background-color: #1a1a1c;
    color: #55555d;
    border-color: #222225;
}

QFrame#context_bar {
    background-color: #141416;
    border-top: 1px solid #242428;
    padding: 2px 8px;
}

QLabel#context_label {
    color: #6c6c75;
    font-weight: bold;
    font-size: """ + str(font_small) + """px;
}

QLabel#context_value {
    color: #d0d0d8;
    font-size: """ + str(font_small) + """px;
    font-family: """ + font_mono + """;
}

QToolButton#context_jump_btn {
    color: #3a9fd5;
    background: transparent;
    border: none;
    font-family: """ + font_mono + """;
    font-size: """ + str(font_small) + """px;
    font-weight: bold;
    padding: 1px 6px;
}

QToolButton#context_jump_btn:hover {
    color: #61afef;
    background-color: #222226;
    border-radius: 4px;
}

QFrame#plan_step {
    background-color: #1e1e22;
    border: 1px solid #2c2c32;
    border-radius: 4px;
    padding: 4px 8px;
    margin: 2px;
}

QFrame#plan_step_active {
    background-color: #1e1e22;
    border: 1px solid #3a9fd5;
    border-radius: 4px;
    padding: 4px 8px;
    margin: 2px;
}

QFrame#plan_step_done {
    background-color: #1e1e22;
    border: 1px solid #4ec9b0;
    border-radius: 4px;
    padding: 4px 8px;
    margin: 2px;
}

QToolButton#collapse_button {
    border: none;
    color: #777780;
    font-size: """ + str(font_small) + """px;
}

QToolButton#collapse_button:hover {
    color: #e0e0e0;
}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #222225;
    color: #d4d4d4;
    border: 1px solid #333338;
    border-radius: 4px;
    padding: """ + str(padding_small) + """px;
}

QGroupBox {
    color: #d4d4d4;
    border: 1px solid #333338;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QFrame#tools_panel {
    background-color: #141414;
    border-left: 1px solid #242428;
}

QFrame#tools_panel QTabWidget::pane {
    border: none;
}

QFrame#tools_panel QTabBar {
    background: #141414;
    border: none;
}

QFrame#tools_panel QTabBar::tab {
    background: #1c1c1f;
    color: #777780;
    padding: """ + str(padding_small) + """px """ + str(padding_normal) + """px;
    border: none;
    border-right: 1px solid #242428;
    font-size: """ + str(font_small) + """px;
    min-height: """ + str(int(22 * scale)) + """px;
}

QFrame#tools_panel QTabBar::tab:selected {
    background: #141414;
    color: #3a9fd5;
    border-bottom: 2px solid #3a9fd5;
}

QFrame#tools_panel QTabBar::tab:hover:!selected {
    background: #222225;
    color: #cccccc;
}

QTreeWidget {
    background-color: #141414;
    color: #d4d4d4;
    border: none;
    font-size: """ + str(font_small) + """px;
}

QTreeWidget::item {
    padding: 3px 6px;
}

QTreeWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QTreeWidget::item:hover:!selected {
    background-color: #202024;
}

QHeaderView::section {
    background-color: #1c1c1f;
    color: #9999a0;
    border: none;
    border-right: 1px solid #242428;
    padding: 4px 8px;
    font-size: """ + str(font_small) + """px;
}

QTableWidget {
    background-color: #141414;
    color: #d4d4d4;
    border: none;
    gridline-color: #242428;
    font-size: """ + str(font_small) + """px;
}

QTableWidget::item {
    padding: 3px 6px;
}

QTableWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QProgressBar {
    background-color: #222225;
    border: 1px solid #333338;
    border-radius: 4px;
    text-align: center;
    color: #d4d4d4;
    font-size: """ + str(font_small) + """px;
    height: 14px;
}

QProgressBar::chunk {
    background-color: #3a9fd5;
    border-radius: 3px;
}

QRadioButton {
    color: #d4d4d4;
    font-size: """ + str(font_small) + """px;
    spacing: 4px;
}

QTextEdit {
    background-color: #141414;
    color: #d4d4d4;
    border: 1px solid #242428;
    border-radius: 6px;
    font-size: """ + str(font_small) + """px;
    font-family: """ + font_mono + """;
}
"""


def get_mode_bar_style() -> str:
    """Get ModeBar QTabBar stylesheet."""
    return (
        "QTabBar { background: #1e1e1e; border: none; border-bottom: 1px solid #2d2d2d; }"
        "QTabBar::tab { background: #1e1e1e; color: #888888; padding: 4px 14px; "
        "border: none; border-bottom: 2px solid transparent; font-size: 11px; font-weight: bold; }"
        "QTabBar::tab:selected { color: #3a9fd5; border-bottom: 2px solid #3a9fd5; background: #181818; }"
        "QTabBar::tab:hover:!selected { color: #cccccc; background: #252526; }"
    )


def get_skill_chip_style() -> str:
    """Get Skill chip QPushButton stylesheet."""
    return (
        "QPushButton#skill_chip { background-color: #222223; color: #3a9fd5; border: 1px solid #2d2d2d; "
        "border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: bold; min-height: 18px; }"
        "QPushButton#skill_chip:hover { background-color: #094771; color: #ffffff; border-color: #3a9fd5; }"
    )



# Cached theme that gets regenerated when DPI changes
_cached_theme: str | None = None
_cached_scale: float | None = None


def get_dark_theme() -> str:
    """Get the DPI-scaled dark theme stylesheet.

    The theme is cached and only regenerated when the DPI scale factor changes.
    Call this function instead of using DARK_THEME directly.
    """
    global _cached_theme, _cached_scale

    current_scale = get_dpi_scale_factor()
    if _cached_theme is not None and _cached_scale == current_scale:
        return _cached_theme

    _cached_theme = _get_scaled_theme()
    _cached_scale = current_scale
    return _cached_theme

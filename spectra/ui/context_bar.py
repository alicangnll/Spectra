"""Context bar: shows current address, function, model, and token count."""

from __future__ import annotations

import importlib

from ..core.host import (
    get_binary_ninja_view,
    get_current_address,
    is_binary_ninja,
    is_ida,
)
from ..core.logging import log_debug
from .qt_compat import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTimer,
    QToolButton,
    QWidget,
)

if is_ida():
    try:
        ida_funcs = importlib.import_module("ida_funcs")
        ida_name = importlib.import_module("ida_name")
    except ImportError:
        ida_funcs = ida_name = None  # type: ignore[assignment]
else:
    ida_funcs = ida_name = None  # type: ignore[assignment]


def _function_name_at(ea: int) -> str | None:
    if is_ida() and ida_funcs is not None and ida_name is not None:
        try:
            func = ida_funcs.get_func(ea)
            if func:
                return ida_name.get_name(func.start_ea)
        except Exception:
            return None

    if is_binary_ninja():
        bv = get_binary_ninja_view()
        if bv is None:
            return None
        try:
            get_func_at = getattr(bv, "get_function_at", None)
            if callable(get_func_at):
                func = get_func_at(ea)
                if func is not None:
                    return getattr(func, "name", None)
            get_containing = getattr(bv, "get_functions_containing", None)
            if callable(get_containing):
                funcs = list(get_containing(ea))
                if funcs:
                    return getattr(funcs[0], "name", None)
        except Exception:
            return None

    return None


class ContextBar(QFrame):
    """Status bar showing current binary context and session info."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("context_bar")
        self.setFixedHeight(26)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 1, 6, 1)
        layout.setSpacing(12)

        # Status LED indicator (idle: gray, active: green dot)
        self._led_label = QLabel("●")
        self._led_label.setStyleSheet("color: #777777; font-size: 11px; font-weight: bold;")
        self._led_label.setToolTip("Agent Idle")
        layout.addWidget(self._led_label)

        # Clickable Address & Function
        self._address_btn = QToolButton(self)
        self._address_btn.setObjectName("context_jump_btn")
        self._address_btn.setText("Addr: —")
        self._address_btn.setToolTip("Click to jump to address in IDA/Binary Ninja")
        self._address_btn.clicked.connect(self._on_jump_address)
        layout.addWidget(self._address_btn)

        self._function_btn = QToolButton(self)
        self._function_btn.setObjectName("context_jump_btn")
        self._function_btn.setText("Func: —")
        self._function_btn.setToolTip("Click to jump to function start in IDA/Binary Ninja")
        self._function_btn.clicked.connect(self._on_jump_function)
        layout.addWidget(self._function_btn)

        self._model_label = self._make_pair("Model:", "—")
        self._tokens_label = self._make_pair("Tokens:", "0")

        for label, value in (
            self._model_label,
            self._tokens_label,
        ):
            layout.addWidget(label)
            layout.addWidget(value)

        layout.addStretch()

        self._stopped = False
        self._current_ea: int | None = None

        # Auto-update cursor position
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_cursor)
        self._timer.start(1500)

    def _make_pair(self, label_text: str, initial: str):
        label = QLabel(label_text)
        label.setObjectName("context_label")
        value = QLabel(initial)
        value.setObjectName("context_value")
        return label, value

    def set_agent_active(self, active: bool) -> None:
        """Update LED status indicator."""
        if active:
            self._led_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: bold;")
            self._led_label.setToolTip("Agent Working...")
        else:
            self._led_label.setStyleSheet("color: #777777; font-size: 11px; font-weight: bold;")
            self._led_label.setToolTip("Agent Idle")

    def stop(self) -> None:
        """Stop the auto-update timer. Call before destruction."""
        self._stopped = True
        try:
            self._timer.stop()
            self._timer.timeout.disconnect(self._update_cursor)
        except (RuntimeError, TypeError) as e:
            log_debug(f"ContextBar.stop: timer already destroyed: {e}")

    def set_address(self, addr: str) -> None:
        self._address_btn.setText(f"Addr: {addr}")

    def set_function(self, name: str) -> None:
        short_name = name if len(name) < 25 else name[:22] + "..."
        self._function_btn.setText(f"Func: {short_name}")

    def set_model(self, model: str) -> None:
        self._model_label[1].setText(model)

    def set_tokens(self, count: int, context_window: int = 0) -> None:
        if count >= 1000:
            text = f"{count / 1000:.1f}k"
        else:
            text = str(count)

        color_style = "color: #cccccc;"
        if context_window > 0:
            pct = min(int(count * 100 / context_window), 100)
            text += f" ({pct}%)"
            if pct >= 80:
                color_style = "color: #f44747; font-weight: bold;"
            elif pct >= 50:
                color_style = "color: #dcdcaa; font-weight: bold;"

        self._tokens_label[1].setText(text)
        self._tokens_label[1].setStyleSheet(color_style)

    def _on_jump_address(self) -> None:
        if self._current_ea is not None:
            self._jump_to(self._current_ea)

    def _on_jump_function(self) -> None:
        if self._current_ea is None:
            return
        if is_ida() and ida_funcs is not None:
            func = ida_funcs.get_func(self._current_ea)
            if func:
                self._jump_to(func.start_ea)
                return
        self._jump_to(self._current_ea)

    def _jump_to(self, ea: int) -> None:
        try:
            if is_ida():
                import ida_kernwin
                ida_kernwin.jumpto(ea)
            elif is_binary_ninja():
                bv = get_binary_ninja_view()
                if bv:
                    bv.navigate(bv.file.get_view_of_type("Linear"), ea)
        except Exception as e:
            log_debug(f"Jump to 0x{ea:x} failed: {e}")

    def _update_cursor(self) -> None:
        if self._stopped:
            return
        try:
            ea = get_current_address()
            if ea is None:
                return
            self._current_ea = int(ea)
            self.set_address(f"0x{int(ea):x}")
            name = _function_name_at(int(ea))
            self.set_function(name or "—")
        except Exception as e:
            log_debug(f"ContextBar._update_cursor failed: {e}")

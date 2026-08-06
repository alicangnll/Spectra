"""Binary Ninja tool registry.

Wires Binary Ninja-specific tool modules into the shared ToolRegistry.
"""

from __future__ import annotations

from ...core.thread_safety import idasync
from ...tools.registry import ToolRegistry
from ...tools import adb  # ADB tools (standalone, shared across hosts)
from . import (  # type: ignore[assignment]
    advanced_decomp,
    ai_features,
    annotations,
    auto_exploit,
    code_quality,
    collaboration,
    database,
    decompiler,
    disassembly,
    functions,
    il,
    il_analysis,
    il_transform,
    kernel_analysis,
    navigation,
    obfuscation_detect,
    scripting,
    ssl_pinning,
    strings,
    types_tools,
    xrefs,
)

_TOOL_MODULES = (
    navigation,
    functions,
    strings,
    database,
    disassembly,
    decompiler,
    xrefs,
    annotations,
    types_tools,
    scripting,
    il,
    il_analysis,
    il_transform,
    advanced_decomp,
    kernel_analysis,
    obfuscation_detect,
    collaboration,
    ssl_pinning,
    auto_exploit,
    code_quality,
    ai_features,
)


def create_default_registry() -> ToolRegistry:
    """Create a Binary Ninja registry with all built-in BN tools."""
    registry = ToolRegistry(dispatch_wrapper=idasync)
    for mod in _TOOL_MODULES:
        registry.register_module(mod)
    # Register standalone ADB tools
    registry.register_module(adb)
    return registry

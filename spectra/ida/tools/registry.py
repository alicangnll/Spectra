"""IDA tool registry: wires IDA-specific tool modules into the shared ToolRegistry."""

from __future__ import annotations

from spectra.core.host import HAS_HEXRAYS
from spectra.core.thread_safety import idasync
from spectra.tools.registry import ToolRegistry
from spectra.tools import adb  # ADB tools (standalone, shared across hosts)

from . import (
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
    kernel_analysis,
    microcode,
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
    microcode,
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
    """Create a registry with all built-in IDA tools."""
    registry = ToolRegistry(dispatch_wrapper=idasync)
    registry.set_capabilities({"hexrays": HAS_HEXRAYS})
    for mod in _TOOL_MODULES:
        registry.register_module(mod)
    # Register standalone ADB tools
    registry.register_module(adb)
    return registry

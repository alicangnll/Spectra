"""IDA tool registry: wires IDA-specific tool modules into the shared ToolRegistry."""

from __future__ import annotations

from spectra.core.host import HAS_HEXRAYS
from spectra.core.thread_safety import idasync
from spectra.tools import (  # standalone device + file-level tools, shared across hosts
    adb,
    binary_diff,
    checksec,
    crypto_detect,
    entropy,
    file_meta,
    fingerprint_libs,
    ioc_collector,
    ios,
    str_decode,
    yara_tools,
)
from spectra.tools.registry import ToolRegistry

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
    exploit_advanced,
    functions,
    kernel_analysis,
    microcode,
    navigation,
    novel_hunter,
    obfuscation_detect,
    scripting,
    ssl_pinning,
    strings,
    types_tools,
    vuln_analysis_advanced,
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
    exploit_advanced,
    novel_hunter,
    vuln_analysis_advanced,
    code_quality,
    ai_features,
)

# Standalone file-level analysis tools — host-agnostic, shared with Binary Ninja.
_FILE_TOOL_MODULES = (
    checksec,
    entropy,
    binary_diff,
    crypto_detect,
    ioc_collector,
    str_decode,
    yara_tools,
    file_meta,
    fingerprint_libs,
)


def create_default_registry() -> ToolRegistry:
    """Create a registry with all built-in IDA tools."""
    registry = ToolRegistry(dispatch_wrapper=idasync)
    registry.set_capabilities({"hexrays": HAS_HEXRAYS})
    for mod in _TOOL_MODULES:
        registry.register_module(mod)
        # Register standalone device tools
    registry.register_module(adb)
    registry.register_module(ios)
    # Register standalone file-level analysis tools
    for mod in _FILE_TOOL_MODULES:
        registry.register_module(mod)
    return registry

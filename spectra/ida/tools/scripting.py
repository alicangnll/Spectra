"""Python scripting execution tool."""

from __future__ import annotations

import importlib
from typing import Annotated

from ...core.logging import log_debug
from ...tools.base import tool
from ...tools.script_guard import run_guarded_script, safe_builtins

# Cached namespace of common IDA modules — populated once, reused across calls.
_IDA_MODULE_NAMES = (
    "idaapi",
    "idautils",
    "idc",
    "ida_funcs",
    "ida_name",
    "ida_bytes",
    "ida_segment",
    "ida_struct",
    "ida_enum",
    "ida_typeinf",
    "ida_nalt",
    "ida_xref",
    "ida_kernwin",
)
_cached_namespace: dict | None = None


def _get_base_namespace() -> dict:
    """Return a cached namespace with common IDA modules pre-imported."""
    global _cached_namespace
    if _cached_namespace is None:
        ns: dict = {}
        for mod_name in _IDA_MODULE_NAMES:
            try:
                ns[mod_name] = importlib.import_module(mod_name)
            except ImportError as e:
                log_debug(f"Optional IDA module {mod_name!r} not available: {e}")
        _cached_namespace = ns
    # Return a copy so user code can't pollute the cache
    result: dict = {"__builtins__": safe_builtins()}
    result.update(_cached_namespace)
    return result


@tool(category="scripting", mutating=True)
def execute_python(
    code: Annotated[str, "Python code to execute in IDA's scripting environment"],
) -> str:
    """LAST RESORT — call only when NO dedicated tool covers the task.

    Every call pauses for explicit user approval. Before calling this,
    check the tool list: decompiling, disassembly, xrefs, functions,
    strings, imports, segments, renaming, comments, types, structs, enums
    and microcode ALL have dedicated tools that are faster, batchable and
    need no approval. Legitimate uses: bulk operations over hundreds of
    items, computations no tool provides (z3, custom crypto), or the user
    explicitly asking for a script.
    """
    return run_guarded_script(code, _get_base_namespace)

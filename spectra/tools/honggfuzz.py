"""Honggfuzz fuzzing tool integration.

Provides tools for:
- Running Honggfuzz on targets
- Analyzing crashes
- Getting fuzzer statistics
- Corpus management
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from ..core.tool_infrastructure import ExternalTool, ToolSafety
from ..core.logging import log_debug, log_error, log_info
from ..tools.base import ParameterSchema, ToolDefinition


class HonggfuzzTool(ExternalTool):
    """Honggfuzz security-oriented fuzzer."""

    tool_name = "Honggfuzz"
    executable_names = ["honggfuzz"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "Windows": [],
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract Honggfuzz version."""
        match = re.search(r"honggfuzz\s+(\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_honggfuzz_instance: HonggfuzzTool | None = None


def get_honggfuzz() -> HonggfuzzTool:
    """Get or create Honggfuzz tool instance."""
    global _honggfuzz_instance
    if _honggfuzz_instance is None:
        _honggfuzz_instance = HonggfuzzTool()
    return _honggfuzz_instance


def check_honggfuzz_available() -> bool:
    """Check if Honggfuzz is available."""
    return get_honggfuzz().is_available()


def _ensure_honggfuzz() -> str:
    """Ensure Honggfuzz is available and return its path."""
    hfuzz = get_honggfuzz()
    if not hfuzz.is_available():
        raise RuntimeError("Honggfuzz not found. Install from https://github.com/google/honggfuzz")
    return hfuzz.get_path()


# ============================================================================
# Tool Functions
# ============================================================================

def honggfuzz_run(target: str, input_dir: str, output_dir: str, args: str = "", duration: int = 3600, threads: int = 1) -> str:
    """Run Honggfuzz on target.

    Args:
        target: Target binary path
        input_dir: Input directory with corpus
        output_dir: Output directory for results
        args: Target arguments (use @@FILE for input file)
        duration: Fuzzing duration in seconds
        threads: Number of threads

    Returns:
        Honggfuzz run command/status
    """
    # Check safety
    is_safe, reason = ToolSafety.check_fuzzing_safety(duration, 0)
    if not is_safe:
        return f"Fuzzing blocked: {reason}"

    hfuzz_path = _ensure_honggfuzz()

    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    if not os.path.isdir(input_dir):
        return f"Error: Input directory not found: {input_dir}"

    os.makedirs(output_dir, exist_ok=True)

    # Build Honggfuzz command
    cmd = [
        hfuzz_path,
        "--input", input_dir,
        "--output", output_dir,
        "--iterations", "0",  # Run indefinitely
        "--threads", str(threads),
        "--timeout", "1000",  # Per-input timeout
        "--verbose",
    ]

    # Add duration (Honggfuzz uses --run_time)
    cmd.extend(["--run_time", str(duration // 1000)])  # Convert to seconds

    # Add target and args
    cmd.append(target)
    if args:
        cmd.extend(args.split())

    output = [
        "=== Honggfuzz Fuzzing Command ===",
        " ".join(cmd),
        "",
        f"Duration: {duration}s",
        f"Threads: {threads}",
        "",
        "Note: Run this command in a terminal for live output.",
    ]

    return "\n".join(output)


def honggfuzz_crashes(output_dir: str) -> str:
    """Get crash information.

    Args:
        output_dir: Honggfuzz output directory

    Returns:
        Crash information
    """
    if not os.path.isdir(output_dir):
        return f"Error: Output directory not found: {output_dir}"

    output = [f"=== Honggfuzz Crashes: {output_dir} ==="]

    # Honggfuzz creates subdirectories for each thread
    try:
        contents = os.listdir(output_dir)
    except Exception as e:
        return f"Error listing directory: {e}"

    crash_count = 0
    for item in contents:
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path):
            # Check for crashes in thread directory
            crash_files = [f for f in os.listdir(item_path) if "crash" in f.lower() or "sig" in f.lower()]
            if crash_files:
                crash_count += len(crash_files)
                output.append(f"{item}: {len(crash_files)} crashes")

    output.append(f"\nTotal crashes: {crash_count}")

    # Check for Honggfuzz stats
    stats_file = os.path.join(output_dir, "stats.txt")
    if os.path.isfile(stats_file):
        output.append("\n=== Fuzzer Stats ===")
        try:
            with open(stats_file, 'r') as f:
                output.append(f.read()[:500])
        except Exception:
            pass

    return "\n".join(output)


def honggfuzz_cov(target: str, input_dir: str, args: str = "") -> str:
    """Check code coverage.

    Args:
        target: Target binary
        input_dir: Input corpus
        args: Target arguments

    Returns:
        Coverage information
    """
    hfuzz_path = _ensure_honggfuzz()

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    corpus_files = []
    if os.path.isdir(input_dir):
        corpus_files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    output = [
        "=== Honggfuzz Coverage ===",
        f"Target: {target}",
        f"Corpus: {len(corpus_files)} files",
        "",
        "Honggfuzz supports coverage feedback:",
        "1. Compile with -fsanitize-coverage=trace-pc-guard",
        "2. Run with --sanitizer flag",
        "3. Honggfuzz will track coverage automatically",
        "",
        "Coverage options:",
        "  --cov_feedback_all    Use all coverage feedback",
        "  --cov_feedback_edge   Use edge coverage",
        "  --cov_feedback_cmplog Use comparison feedback",
    ]

    return "\n".join(output)


def honggfuzz_minimize(target: str, input_dir: str, output_dir: str) -> str:
    """Minimize corpus.

    Args:
        target: Target binary
        input_dir: Input corpus directory
        output_dir: Output directory for minimized corpus

    Returns:
        Minimization command
    """
    hfuzz_path = _ensure_honggfuzz()

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        hfuzz_path,
        "--input", input_dir,
        "--output", output_dir,
        "--minimize",
        target,
    ]

    output = [
        "=== Honggfuzz Corpus Minimization ===",
        "Command: " + " ".join(cmd),
        "",
        "This will minimize the corpus while maintaining coverage.",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


def honggfuzz_dict(target: str, input_dir: str, dict_file: str, output_dir: str = "") -> str:
    """Run with dictionary.

    Args:
        target: Target binary
        input_dir: Input corpus
        dict_file: Dictionary file path
        output_dir: Optional output directory

    Returns:
        Dictionary fuzzing command
    """
    hfuzz_path = _ensure_honggfuzz()

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    if not os.path.isfile(dict_file):
        return f"Error: Dictionary file not found: {dict_file}"

    cmd = [
        hfuzz_path,
        "--input", input_dir,
        "--dict", dict_file,
    ]

    if output_dir:
        cmd.extend(["--output", output_dir])

    cmd.append(target)

    output = [
        "=== Honggfuzz with Dictionary ===",
        "Command: " + " ".join(cmd),
        "",
        "Dictionary format (one entry per line):",
        "  keyword1",
        "  keyword2",
        "  \"string with spaces\"",
        "",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


def honggfuzz_persistent(target: str, input_dir: str, output_dir: str, persistent_addr: str) -> str:
    """Run in persistent mode.

    Args:
        target: Target binary
        input_dir: Input corpus
        output_dir: Output directory
        persistent_addr: Persistent function address (hex)

    Returns:
        Persistent mode command
    """
    hfuzz_path = _ensure_honggfuzz()

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        hfuzz_path,
        "--input", input_dir,
        "--output", output_dir,
        "--persistent",
        "--persistent_addr", persistent_addr,
        target,
    ]

    output = [
        "=== Honggfuzz Persistent Mode ===",
        "Command: " + " ".join(cmd),
        "",
        f"Persistent function address: {persistent_addr}",
        "",
        "Persistent mode requirements:",
        "1. Target must support persistent fuzzing",
        "2. Use LLVMFuzzerInitialize and LLVMFuzzerTestOneInput",
        "3. Get function address from nm or objdump",
        "",
        "Example:",
        "  nm target | grep LLVMFuzzerTestOneInput",
    ]

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================

def create_honggfuzz_tools() -> list[ToolDefinition]:
    """Create Honggfuzz tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="honggfuzz_run",
            description="Run Honggfuzz on target (requires approval)",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary path", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input directory with corpus", required=True),
                ParameterSchema(name="output_dir", type="string", description="Output directory for results", required=True),
                ParameterSchema(name="args", type="string", description="Target arguments (use @@FILE for input)", required=False, default=""),
                ParameterSchema(name="duration", type="integer", description="Fuzzing duration in seconds", required=False, default=3600),
                ParameterSchema(name="threads", type="integer", description="Number of threads", required=False, default=1),
            ],
            handler=lambda target, input_dir, output_dir, args="", duration=3600, threads=1, **kwargs: honggfuzz_run(target, input_dir, output_dir, args, duration, threads),
        ),

        ToolDefinition(
            name="honggfuzz_crashes",
            description="Get crash information from Honggfuzz output",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="output_dir", type="string", description="Honggfuzz output directory", required=True),
            ],
            handler=lambda output_dir, **kwargs: honggfuzz_crashes(output_dir),
        ),

        ToolDefinition(
            name="honggfuzz_cov",
            description="Check code coverage information",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(name="args", type="string", description="Target arguments", required=False, default=""),
            ],
            handler=lambda target, input_dir, args="", **kwargs: honggfuzz_cov(target, input_dir, args),
        ),

        ToolDefinition(
            name="honggfuzz_minimize",
            description="Minimize corpus",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(name="output_dir", type="string", description="Output directory for minimized corpus", required=True),
            ],
            handler=lambda target, input_dir, output_dir, **kwargs: honggfuzz_minimize(target, input_dir, output_dir),
        ),

        ToolDefinition(
            name="honggfuzz_dict",
            description="Run fuzzer with dictionary",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(name="dict_file", type="string", description="Dictionary file path", required=True),
                ParameterSchema(name="output_dir", type="string", description="Optional output directory", required=False, default=""),
            ],
            handler=lambda target, input_dir, dict_file, output_dir="", **kwargs: honggfuzz_dict(target, input_dir, dict_file, output_dir),
        ),

        ToolDefinition(
            name="honggfuzz_persistent",
            description="Run in persistent mode",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(name="output_dir", type="string", description="Output directory", required=True),
                ParameterSchema(name="persistent_addr", type="string", description="Persistent function address (hex)", required=True),
            ],
            handler=lambda target, input_dir, output_dir, persistent_addr, **kwargs: honggfuzz_persistent(target, input_dir, output_dir, persistent_addr),
        ),
    ]


def register_honggfuzz_tools(registry: Any) -> int:
    """Register Honggfuzz tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_honggfuzz_available():
        log_debug("Honggfuzz not available, skipping tool registration")
        return 0

    tools = create_honggfuzz_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Honggfuzz tools")
    return len(tools)

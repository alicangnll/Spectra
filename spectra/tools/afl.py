"""AFL++ fuzzing tool integration.

Provides tools for:
- Running AFL++ on targets
- Analyzing crashes
- Getting plot data
- Corpus management
- Minimization
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool, ToolSafety
from ..tools.base import ParameterSchema, ToolDefinition


class AFLTool(ExternalTool):
    """AFL++ fuzzing tool."""

    tool_name = "AFL++"
    executable_names = ["afl-fuzz", "afl-gcc", "afl-g++"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "Windows": [],  # AFL++ not available on Windows
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract AFL++ version."""
        match = re.search(r"afl\+\+\s+(\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_afl_instance: AFLTool | None = None


def get_afl() -> AFLTool:
    """Get or create AFL tool instance."""
    global _afl_instance
    if _afl_instance is None:
        _afl_instance = AFLTool()
    return _afl_instance


def check_afl_available() -> bool:
    """Check if AFL++ is available."""
    return get_afl().is_available()


def _ensure_afl(tool: str = "afl-fuzz") -> str:
    """Ensure AFL is available and return tool path."""
    afl = get_afl()
    if not afl.is_available():
        raise RuntimeError("AFL++ not found. Install from https://github.com/AFLplusplus/AFLplusplus")

    # Try to find specific tool
    import shutil

    path = shutil.which(tool)
    if path:
        return path

    # Fallback to base path
    base_path = afl.get_path()
    if base_path:
        tool_dir = os.path.dirname(base_path)
        tool_path = os.path.join(tool_dir, tool)
        if os.path.isfile(tool_path):
            return tool_path

    return base_path


# ============================================================================
# Tool Functions
# ============================================================================


def afl_run(
    target: str, input_dir: str, output_dir: str, args: str = "", duration: int = 3600, memory_limit: int = 8192
) -> str:
    """Run AFL++ on target.

    Args:
        target: Target binary path
        input_dir: Input directory with seed corpus
        output_dir: Output directory for results
        args: Command-line arguments for target (use @@ for input file)
        duration: Fuzzing duration in seconds
        memory_limit: Memory limit in MB

    Returns:
        AFL run command/status
    """
    # Check safety
    is_safe, reason = ToolSafety.check_fuzzing_safety(duration, memory_limit)
    if not is_safe:
        return f"Fuzzing blocked: {reason}"

    afl_fuzz_path = _ensure_afl("afl-fuzz")

    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    if not os.path.isdir(input_dir):
        return f"Error: Input directory not found: {input_dir}"

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        afl_fuzz_path,
        "-i",
        input_dir,
        "-o",
        output_dir,
        "-t",
        "1000",  # Timeout
        "-m",
        str(memory_limit),
        "-V",
        "60",  # Smash threshold
    ]

    # Add duration (AFL++ doesn't have built-in duration, use timeout)
    # We'll provide command info instead of running

    output = [
        "=== AFL++ Fuzzing Command ===",
        " ".join([*cmd, target, (args or "@@")]),
        "",
        f"Duration: {duration}s (note: AFL++ runs until manually stopped)",
        f"Memory limit: {memory_limit}MB",
        "",
        "Note: Run this command in a terminal. AFL++ requires interactive mode.",
        "To run with timeout:",
        f"timeout {duration}s {' '.join(cmd)} {target} {args or '@@'}",
    ]

    return "\n".join(output)


def afl_crashes(output_dir: str) -> str:
    """Get crash information.

    Args:
        output_dir: AFL output directory

    Returns:
        Crash information
    """
    if not os.path.isdir(output_dir):
        return f"Error: Output directory not found: {output_dir}"

    crashes_dir = os.path.join(output_dir, "default", "crashes")
    hang_dir = os.path.join(output_dir, "default", "hangs")

    output = [f"=== AFL Crashes: {output_dir} ==="]

    if os.path.isdir(crashes_dir):
        crash_files = [f for f in os.listdir(crashes_dir) if f not in ["README.txt", "README.dmpi"]]

        output.append(f"Crashes: {len(crash_files)}")
        output.append("")

        # Show unique crashes
        _unique_crashes = [f for f in crash_files if ",sync:" in f or "id:" in f or f == "README.txt"]
        output.append(f"Unique crashes: {len([c for c in crash_files if 'id' in c or 'sync' in c])}")

        if crash_files:
            output.append("Recent crashes:")
            for crash in crash_files[:5]:
                crash_path = os.path.join(crashes_dir, crash)
                if os.path.isfile(crash_path):
                    size = os.path.getsize(crash_path)
                    output.append(f"  {crash}: {size} bytes")
    else:
        output.append("No crashes directory found")

    if os.path.isdir(hang_dir):
        hang_files = [f for f in os.listdir(hang_dir) if f != "README.txt"]
        output.append(f"Hangs: {len(hang_files)}")

    # Show stats
    stats_file = os.path.join(output_dir, "default", "fuzzer_stats")
    if os.path.isfile(stats_file):
        output.append("")
        output.append("=== Fuzzer Stats ===")
        try:
            with open(stats_file) as f:
                stats = f.read()
            output.append(stats[:500])  # Show first 500 chars
        except Exception:
            pass

    return "\n".join(output)


def afl_plot_data(output_dir: str) -> str:
    """Get plot data for visualization.

    Args:
        output_dir: AFL output directory

    Returns:
        Plot data
    """
    if not os.path.isdir(output_dir):
        return f"Error: Output directory not found: {output_dir}"

    # Check for plot_data file
    plot_data_file = os.path.join(output_dir, "default", "plot_data")

    if not os.path.isfile(plot_data_file):
        return "No plot data found. Run AFL++ with -M flag for master mode."

    output = [f"=== AFL Plot Data: {output_dir} ==="]

    try:
        with open(plot_data_file) as f:
            lines = f.readlines()

        # Parse AFL plot data format
        # unix_time, execs_sec, execs_total, corpus_count, unique_crashes, unique_hangs, max_depth
        output.append(" unix_time, execs_sec, execs_total, corpus, crashes, hangs, depth")

        for line in lines[:10]:  # Show first 10 entries
            output.append(line.strip())

        if len(lines) > 10:
            output.append(f"... and {len(lines) - 10} more entries")

        output.append("")
        output.append("Use afl-plot-gui or gnuplot for visualization")

    except Exception as e:
        output.append(f"Error reading plot data: {e}")

    return "\n".join(output)


def afl_triage_crashes(output_dir: str, target: str, args: str = "") -> str:
    """Triage crashes with target.

    Args:
        output_dir: AFL output directory
        target: Target binary
        args: Target arguments (use @@ for input file)

    Returns:
        Triage information
    """
    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    crashes_dir = os.path.join(output_dir, "default", "crashes")

    if not os.path.isdir(crashes_dir):
        return f"Error: No crashes directory in {output_dir}"

    crash_files = [f for f in os.listdir(crashes_dir) if f != "README.txt"]

    output = [
        "=== AFL Crash Triage ===",
        f"Target: {target}",
        f"Crashes: {len(crash_files)}",
        "",
    ]

    if not crash_files:
        output.append("No crashes to triage")
        return "\n".join(output)

    output.append("Running crashes through target...")

    for crash_file in crash_files[:5]:  # Show first 5
        crash_path = os.path.join(crashes_dir, crash_file)
        output.append(f"\nTesting: {crash_file}")

        cmd = target.split()
        if args:
            cmd.extend(args.split())

        # Replace @@ with crash file
        cmd = [c.replace("@@", crash_path) for c in cmd]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            signal = "NONE"
            if result.returncode < 0:
                signal = f"SIGNAL ({-result.returncode})"

            output.append(f"  Exit code: {result.returncode} ({signal})")

        except subprocess.TimeoutExpired:
            output.append("  Exit code: TIMEOUT")
        except Exception as e:
            output.append(f"  Error: {e}")

    if len(crash_files) > 5:
        output.append(f"\n... and {len(crash_files) - 5} more crashes")

    return "\n".join(output)


def afl_minimize_corpus(target: str, input_dir: str, output_dir: str, args: str = "") -> str:
    """Minimize corpus with afl-cmin.

    Args:
        target: Target binary
        input_dir: Input corpus directory
        output_dir: Output directory for minimized corpus
        args: Target arguments

    Returns:
        Minimization result
    """
    afl_cmin_path = _ensure_afl("afl-cmin")

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    if not os.path.isdir(input_dir):
        return f"Error: Input directory not found: {input_dir}"

    cmd = [
        afl_cmin_path,
        "--all",
        "-i",
        input_dir,
        "-o",
        output_dir,
        "-t",
        "1000",
    ]

    cmd.extend(target.split())

    if args:
        cmd.extend(args.split())

    output = [
        "=== AFL Corpus Minimization ===",
        "Command: " + " ".join(cmd),
        "",
        "Run this command to minimize the corpus.",
        "This removes redundant inputs from the corpus.",
    ]

    return "\n".join(output)


def afl_analyze_crash(crash_file: str, target: str, args: str = "") -> str:
    """Analyze specific crash with AFL's crash analyzer.

    Args:
        crash_file: Path to crash file
        target: Target binary
        args: Target arguments

    Returns:
        Crash analysis
    """
    if not os.path.isfile(crash_file):
        return f"Error: Crash file not found: {crash_file}"

    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    output = [
        "=== AFL Crash Analysis ===",
        f"Crash: {crash_file}",
        f"Target: {target}",
        "",
    ]

    # Get crash file size
    size = os.path.getsize(crash_file)
    output.append(f"Size: {size} bytes")

    # Show hexdump of crash
    output.append("\nCrash data (hex):")
    try:
        with open(crash_file, "rb") as f:
            data = f.read()

        hex_str = data[:100].hex()  # First 100 bytes
        output.append(hex_str[:200])  # Show first 200 chars

    except Exception as e:
        output.append(f"Error reading crash: {e}")

    # Run with target to see signal
    output.append("\nRunning with target:")
    cmd = target.split()
    if args:
        cmd_args = [c.replace("@@", crash_file) for c in args.split()]
        cmd.extend(cmd_args)
    else:
        cmd.append(crash_file)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode < 0:
            output.append(f"Signal: {-result.returncode}")
        elif result.returncode > 128:
            output.append(f"Signal: {result.returncode - 128}")
        else:
            output.append(f"Exit code: {result.returncode}")

    except subprocess.TimeoutExpired:
        output.append("Result: TIMEOUT")
    except Exception as e:
        output.append(f"Error: {e}")

    return "\n".join(output)


def afl_cov(target: str, input_dir: str, args: str = "") -> str:
    """Check code coverage with AFL++ coverage tools.

    Args:
        target: Target binary
        input_dir: Input corpus directory
        args: Target arguments

    Returns:
        Coverage info
    """
    _afl_what_path = _ensure_afl("afl-whatsup")

    if not os.path.isdir(input_dir):
        return f"Error: Input directory not found: {input_dir}"

    # Count corpus files
    corpus_files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    output = [
        "=== AFL Coverage Information ===",
        f"Target: {target}",
        f"Corpus: {len(corpus_files)} files",
        "",
        "For detailed coverage analysis:",
        "1. Compile with afl-gcc -coverage",
        "2. Run corpus through target",
        "3. Use gcov/lcov to analyze",
        "",
        "Or use AFL++'s qemu mode for binary-only coverage.",
    ]

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================


def create_afl_tools() -> list[ToolDefinition]:
    """Create AFL tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="afl_run",
            description="Run AFL++ on target (requires approval)",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="input_dir", type="string", description="Input directory with seed corpus", required=True
                ),
                ParameterSchema(
                    name="output_dir", type="string", description="Output directory for results", required=True
                ),
                ParameterSchema(
                    name="args",
                    type="string",
                    description="Target arguments (use @@ for input file)",
                    required=False,
                    default="",
                ),
                ParameterSchema(
                    name="duration",
                    type="integer",
                    description="Fuzzing duration in seconds",
                    required=False,
                    default=3600,
                ),
                ParameterSchema(
                    name="memory_limit", type="integer", description="Memory limit in MB", required=False, default=8192
                ),
            ],
            handler=lambda target, input_dir, output_dir, args="", duration=3600, memory_limit=8192, **kwargs: afl_run(
                target, input_dir, output_dir, args, duration, memory_limit
            ),
        ),
        ToolDefinition(
            name="afl_crashes",
            description="Get crash information from AFL output",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="output_dir", type="string", description="AFL output directory", required=True),
            ],
            handler=lambda output_dir, **kwargs: afl_crashes(output_dir),
        ),
        ToolDefinition(
            name="afl_plot_data",
            description="Get plot data for visualization",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="output_dir", type="string", description="AFL output directory", required=True),
            ],
            handler=lambda output_dir, **kwargs: afl_plot_data(output_dir),
        ),
        ToolDefinition(
            name="afl_triage_crashes",
            description="Triage crashes with target",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="output_dir", type="string", description="AFL output directory", required=True),
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(
                    name="args",
                    type="string",
                    description="Target arguments (use @@ for input)",
                    required=False,
                    default="",
                ),
            ],
            handler=lambda output_dir, target, args="", **kwargs: afl_triage_crashes(output_dir, target, args),
        ),
        ToolDefinition(
            name="afl_minimize_corpus",
            description="Minimize corpus with afl-cmin",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(
                    name="output_dir", type="string", description="Output directory for minimized corpus", required=True
                ),
                ParameterSchema(name="args", type="string", description="Target arguments", required=False, default=""),
            ],
            handler=lambda target, input_dir, output_dir, args="", **kwargs: afl_minimize_corpus(
                target, input_dir, output_dir, args
            ),
        ),
        ToolDefinition(
            name="afl_analyze_crash",
            description="Analyze specific crash file",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="crash_file", type="string", description="Path to crash file", required=True),
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="args", type="string", description="Target arguments", required=False, default=""),
            ],
            handler=lambda crash_file, target, args="", **kwargs: afl_analyze_crash(crash_file, target, args),
        ),
        ToolDefinition(
            name="afl_cov",
            description="Check code coverage information",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="input_dir", type="string", description="Input corpus directory", required=True),
                ParameterSchema(name="args", type="string", description="Target arguments", required=False, default=""),
            ],
            handler=lambda target, input_dir, args="", **kwargs: afl_cov(target, input_dir, args),
        ),
    ]


def register_afl_tools(registry: Any) -> int:
    """Register AFL tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_afl_available():
        log_debug("AFL++ not available, skipping tool registration")
        return 0

    tools = create_afl_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} AFL tools")
    return len(tools)

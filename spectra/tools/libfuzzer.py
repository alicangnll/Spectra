"""LibFuzzer fuzzing tool integration.

Provides tools for:
- Running LibFuzzer on targets
- Minimizing crash inputs
- Merging corpora
- Corpus analysis
"""

from __future__ import annotations

import os
from typing import Any

from ..core.logging import log_info
from ..core.tool_infrastructure import ExternalTool, ToolSafety
from ..tools.base import ParameterSchema, ToolDefinition


class LibFuzzerTool(ExternalTool):
    """LibFuzzer coverage-guided fuzzing tool."""

    tool_name = "LibFuzzer"
    # LibFuzzer is typically compiled into the target binary
    # So we check for common fuzzing binaries
    executable_names = []  # No standard executable

    def __init__(self, required: bool = False):
        super().__init__(required)

    def find_tool(self) -> Any:
        """LibFuzzer is a library, not a standalone tool."""
        # Check if we can find any fuzzer binaries
        import shutil

        fuzzer_binaries = shutil.which("llvm-symbolizer") or shutil.which("asan_symbolize")
        if fuzzer_binaries:
            from ..core.tool_infrastructure import ToolLocation

            location = ToolLocation(path=fuzzer_binaries, version="linked")
            location.is_valid = True
            self._location = location
            return location
        return None


# Global instance
_libfuzzer_instance: LibFuzzerTool | None = None


def get_libfuzzer() -> LibFuzzerTool:
    """Get or create LibFuzzer tool instance."""
    global _libfuzzer_instance
    if _libfuzzer_instance is None:
        _libfuzzer_instance = LibFuzzerTool()
    return _libfuzzer_instance


def check_libfuzzer_available() -> bool:
    """Check if LibFuzzer environment is available."""
    return get_libfuzzer().is_available()


# ============================================================================
# Tool Functions
# ============================================================================


def libfuzzer_run(target: str, corpus_dir: str, max_time: int = 600, max_inputs: int = 0, args: str = "") -> str:
    """Run LibFuzzer on target.

    Args:
        target: Fuzzer binary (compiled with LibFuzzer)
        corpus_dir: Corpus directory
        max_time: Maximum fuzzing time in seconds
        max_inputs: Maximum number of inputs (0 = unlimited)
        args: Additional LibFuzzer arguments

    Returns:
        LibFuzzer run command/status
    """
    # Check safety
    is_safe, reason = ToolSafety.check_fuzzing_safety(max_time, 0)
    if not is_safe:
        return f"Fuzzing blocked: {reason}"

    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    os.makedirs(corpus_dir, exist_ok=True)

    # Build LibFuzzer command
    cmd = [target, corpus_dir]

    # Add LibFuzzer flags
    if max_time > 0:
        cmd.append(f"-max_total_time={max_time}")

    if max_inputs > 0:
        cmd.append(f"-max_inputs={max_inputs}")

    # Parse additional args
    if args:
        cmd.extend(args.split())

    output = [
        "=== LibFuzzer Command ===",
        " ".join(cmd),
        "",
        "Note: LibFuzzer binaries are compiled with -fsanitize=fuzzer",
        "The target should be a fuzzer-specific binary.",
        "",
        "Common LibFuzzer flags:",
        "  -max_total_time=SECONDS   Total fuzzing time",
        "  -max_inputs=N            Maximum number of inputs",
        "  -timeout=SECONDS         Timeout per input",
        "  -seed=INT                Random seed",
        "  -jobs=N                  Number of parallel jobs",
        "  -workers=N               Number of parallel workers",
        "  -dict=FILE               Dictionary file",
        "",
        "Run this command in a terminal for live output.",
    ]

    return "\n".join(output)


def libfuzzer_minimize_crash(crash: str, target: str, args: str = "") -> str:
    """Minimize crash input.

    Args:
        crash: Crash input file
        target: Fuzzer binary
        args: Additional arguments

    Returns:
        Minimization result
    """
    if not os.path.isfile(crash):
        return f"Error: Crash file not found: {crash}"

    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    # Create temp directory for minimization
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="libfuzzer_min_")

    cmd = [
        target,
        temp_dir,
        "-minimize_crash=1",
        f"-exact_artifact_path={crash}",
    ]

    if args:
        cmd.extend(args.split())

    output = [
        "=== LibFuzzer Crash Minimization ===",
        "Command: " + " ".join(cmd),
        "",
        "This will minimize the crash input while preserving the crash.",
        "The minimized crash will be written to the original path.",
        "",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


def libfuzzer_merge_corpus(target: str, corpus_dirs: list, output_dir: str) -> str:
    """Merge and minimize multiple corpora.

    Args:
        target: Fuzzer binary
        corpus_dirs: List of corpus directories to merge
        output_dir: Output directory for merged corpus

    Returns:
        Merge result
    """
    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    for corpus_dir in corpus_dirs:
        if not os.path.isdir(corpus_dir):
            return f"Error: Corpus directory not found: {corpus_dir}"

    os.makedirs(output_dir, exist_ok=True)

    cmd = [target, output_dir, "-merge=1"]

    for corpus_dir in corpus_dirs:
        cmd.append(corpus_dir)

    output = [
        "=== LibFuzzer Corpus Merge ===",
        "Command: " + " ".join(cmd),
        "",
        f"Merging {len(corpus_dirs)} corpus directories to {output_dir}",
        "",
        "This will:",
        "1. Merge all corpora",
        "2. Remove redundant inputs",
        "3. Minimize corpus size",
        "",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


def libfuzzer_cov(target: str, corpus_dir: str) -> str:
    """Check corpus coverage.

    Args:
        target: Fuzzer binary
        corpus_dir: Corpus directory

    Returns:
        Coverage information
    """
    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    if not os.path.isdir(corpus_dir):
        return f"Error: Corpus directory not found: {corpus_dir}"

    corpus_files = [f for f in os.listdir(corpus_dir) if os.path.isfile(os.path.join(corpus_dir, f))]

    output = [
        "=== LibFuzzer Coverage ===",
        f"Target: {target}",
        f"Corpus: {corpus_dir}",
        f"Files: {len(corpus_files)}",
        "",
        "For detailed coverage:",
        "1. Recompile with -fsanitize-coverage=trace-pc-guard",
        "2. Run with -coverage=1 flag",
        "3. Use sancov/llvm-cov to analyze",
        "",
        "Quick coverage check:",
        f"  {target} {corpus_dir} -runs=0",
    ]

    return "\n".join(output)


def libfuzzer_crash_info(crash_file: str) -> str:
    """Analyze crash file.

    Args:
        crash_file: Path to crash input

    Returns:
        Crash information
    """
    if not os.path.isfile(crash_file):
        return f"Error: Crash file not found: {crash_file}"

    size = os.path.getsize(crash_file)

    output = [
        "=== LibFuzzer Crash Info ===",
        f"File: {crash_file}",
        f"Size: {size} bytes",
        "",
        "To analyze the crash:",
        "1. Run fuzzer with the crash file:",
        f"   fuzzer_binary corpus_dir -exact_artifact_path={crash_file}",
        "2. Check for ASAN/MSAN/UBSAN output",
        "3. Use debugger for detailed analysis",
        "",
    ]

    # Show hexdump
    try:
        with open(crash_file, "rb") as f:
            data = f.read()

        output.append("Crash data (hex, first 100 bytes):")
        output.append(data[:100].hex())

    except Exception as e:
        output.append(f"Error reading file: {e}")

    return "\n".join(output)


def libfuzzer_dict(target: str, dict_file: str, corpus_dir: str) -> str:
    """Run fuzzer with dictionary.

    Args:
        target: Fuzzer binary
        dict_file: Dictionary file path
        corpus_dir: Corpus directory

    Returns:
        Dictionary fuzzing command
    """
    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    if not os.path.isfile(dict_file):
        return f"Error: Dictionary file not found: {dict_file}"

    cmd = [
        target,
        corpus_dir,
        f"-dict={dict_file}",
    ]

    output = [
        "=== LibFuzzer with Dictionary ===",
        "Command: " + " ".join(cmd),
        "",
        "Dictionary format:",
        "  # Comments start with #",
        '  kw1="keyword 1"',
        '  kw2="keyword 2"',
        "",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


def libfuzzer_parallel(target: str, corpus_dir: str, jobs: int = 4, workers: int = 4) -> str:
    """Run fuzzer in parallel mode.

    Args:
        target: Fuzzer binary
        corpus_dir: Corpus directory
        jobs: Number of parallel jobs
        workers: Number of parallel workers

    Returns:
        Parallel fuzzing command
    """
    if not os.path.isfile(target):
        return f"Error: Target binary not found: {target}"

    cmd = [
        target,
        corpus_dir,
        f"-jobs={jobs}",
        f"-workers={workers}",
    ]

    output = [
        "=== LibFuzzer Parallel Mode ===",
        "Command: " + " ".join(cmd),
        "",
        f"Running {workers} workers in {jobs} jobs",
        "",
        "Note: Parallel mode requires shared corpus directory.",
        "Use NFS or shared filesystem for best results.",
        "",
        "Run this command in a terminal.",
    ]

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================


def create_libfuzzer_tools() -> list[ToolDefinition]:
    """Create LibFuzzer tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="libfuzzer_run",
            description="Run LibFuzzer on target (requires approval)",
            category="fuzzing",
            parameters=[
                ParameterSchema(
                    name="target",
                    type="string",
                    description="Fuzzer binary (compiled with -fsanitize=fuzzer)",
                    required=True,
                ),
                ParameterSchema(name="corpus_dir", type="string", description="Corpus directory", required=True),
                ParameterSchema(
                    name="max_time",
                    type="integer",
                    description="Maximum fuzzing time in seconds",
                    required=False,
                    default=600,
                ),
                ParameterSchema(
                    name="max_inputs",
                    type="integer",
                    description="Maximum number of inputs (0 = unlimited)",
                    required=False,
                    default=0,
                ),
                ParameterSchema(
                    name="args", type="string", description="Additional LibFuzzer arguments", required=False, default=""
                ),
            ],
            handler=lambda target, corpus_dir, max_time=600, max_inputs=0, args="", **kwargs: libfuzzer_run(
                target, corpus_dir, max_time, max_inputs, args
            ),
        ),
        ToolDefinition(
            name="libfuzzer_minimize_crash",
            description="Minimize crash input",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="crash", type="string", description="Crash input file", required=True),
                ParameterSchema(name="target", type="string", description="Fuzzer binary", required=True),
                ParameterSchema(
                    name="args", type="string", description="Additional arguments", required=False, default=""
                ),
            ],
            handler=lambda crash, target, args="", **kwargs: libfuzzer_minimize_crash(crash, target, args),
        ),
        ToolDefinition(
            name="libfuzzer_merge_corpus",
            description="Merge and minimize multiple corpora",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Fuzzer binary", required=True),
                ParameterSchema(
                    name="corpus_dirs",
                    type="string",
                    description="Comma-separated list of corpus directories",
                    required=True,
                ),
                ParameterSchema(
                    name="output_dir", type="string", description="Output directory for merged corpus", required=True
                ),
            ],
            handler=lambda target, corpus_dirs, output_dir, **kwargs: libfuzzer_merge_corpus(
                target, corpus_dirs.split(","), output_dir
            ),
        ),
        ToolDefinition(
            name="libfuzzer_cov",
            description="Check corpus coverage",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Fuzzer binary", required=True),
                ParameterSchema(name="corpus_dir", type="string", description="Corpus directory", required=True),
            ],
            handler=lambda target, corpus_dir, **kwargs: libfuzzer_cov(target, corpus_dir),
        ),
        ToolDefinition(
            name="libfuzzer_crash_info",
            description="Analyze crash file",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="crash_file", type="string", description="Path to crash input", required=True),
            ],
            handler=lambda crash_file, **kwargs: libfuzzer_crash_info(crash_file),
        ),
        ToolDefinition(
            name="libfuzzer_dict",
            description="Run fuzzer with dictionary",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Fuzzer binary", required=True),
                ParameterSchema(name="dict_file", type="string", description="Dictionary file path", required=True),
                ParameterSchema(name="corpus_dir", type="string", description="Corpus directory", required=True),
            ],
            handler=lambda target, dict_file, corpus_dir, **kwargs: libfuzzer_dict(target, dict_file, corpus_dir),
        ),
        ToolDefinition(
            name="libfuzzer_parallel",
            description="Run fuzzer in parallel mode",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Fuzzer binary", required=True),
                ParameterSchema(name="corpus_dir", type="string", description="Corpus directory", required=True),
                ParameterSchema(
                    name="jobs", type="integer", description="Number of parallel jobs", required=False, default=4
                ),
                ParameterSchema(
                    name="workers", type="integer", description="Number of parallel workers", required=False, default=4
                ),
            ],
            handler=lambda target, corpus_dir, jobs=4, workers=4, **kwargs: libfuzzer_parallel(
                target, corpus_dir, jobs, workers
            ),
        ),
    ]


def register_libfuzzer_tools(registry: Any) -> int:
    """Register LibFuzzer tools.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    # LibFuzzer tools are available even without fuzzer binaries
    # They provide guidance and command generation
    tools = create_libfuzzer_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} LibFuzzer tools")
    return len(tools)

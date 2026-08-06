"""Custom fuzzing framework for Spectra.

Provides tools for:
- Creating fuzzing templates
- Running fuzzing with templates
- Analyzing crashes
- Mutation strategies
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
from typing import Any

from ..core.tool_infrastructure import ToolSafety
from ..core.logging import log_debug, log_error, log_info
from ..tools.base import ParameterSchema, ToolDefinition


# ============================================================================
# Tool Functions
# ============================================================================

def fuzz_create_template(target: str, input_format: str, output_file: str) -> str:
    """Create fuzzing template for target.

    Args:
        target: Target binary path
        input_format: Input format (text|binary|json|xml|http)
        output_file: Output template file path

    Returns:
        Template creation result
    """
    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    # Create template based on format
    templates = {
        "text": {
            "description": "Text input fuzzing template",
            "format": "text",
            "mutations": ["bit_flip", "byte_flip", "random", "magic_values"],
            "magic_values": ["", "\n", "\r\n", "\x00", "\xff", "../../etc/passwd", "{{user_input}}"],
        },
        "binary": {
            "description": "Binary input fuzzing template",
            "format": "binary",
            "mutations": ["bit_flip", "byte_flip", "insert_random", "delete"],
            "magic_values": ["\x00\x00\x00\x00", "\xff\xff\xff\xff", "\x7f\x45\x4c\x46"],
        },
        "json": {
            "description": "JSON input fuzzing template",
            "format": "json",
            "mutations": ["key_mutation", "value_mutation", "structure_mutation"],
            "magic_values": ["null", "{}", "[]", "true", "false", '{"key": "value"}'],
        },
        "xml": {
            "description": "XML input fuzzing template",
            "format": "xml",
            "mutations": ["tag_mutation", "attribute_mutation", "injection"],
            "magic_values": ["<?xml version='1.0'?><root/>", "<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>"],
        },
        "http": {
            "description": "HTTP request fuzzing template",
            "format": "http",
            "mutations": ["header_mutation", "method_mutation", "path_mutation", "body_mutation"],
            "magic_values": ["GET / HTTP/1.0", "User-Agent: ", "Connection: close"],
        },
    }

    template = templates.get(input_format.lower(), templates["text"])
    template["target"] = target
    template["created"] = str(subprocess.run(["date"], capture_output=True, text=True).stdout.strip())

    try:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)

        return f"Template created: {output_file}\n\n{json.dumps(template, indent=2)}"

    except Exception as e:
        return f"Error creating template: {e}"


def fuzz_run_template(template_file: str, iterations: int = 100, output_dir: str = "") -> str:
    """Run fuzzing with template.

    Args:
        template_file: Template file path
        iterations: Number of fuzzing iterations
        output_dir: Optional output directory for generated inputs

    Returns:
        Fuzzing results
    """
    if not os.path.isfile(template_file):
        return f"Error: Template file not found: {template_file}"

    # Load template
    try:
        with open(template_file, 'r') as f:
            template = json.load(f)
    except Exception as e:
        return f"Error loading template: {e}"

    output = [
        f"=== Fuzzing with Template: {template_file} ===",
        f"Target: {template.get('target', 'unknown')}",
        f"Format: {template.get('format', 'unknown')}",
        f"Iterations: {iterations}",
        "",
    ]

    mutations = template.get("mutations", ["random"])
    magic_values = template.get("magic_values", [])

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output.append(f"Output directory: {output_dir}")
        output.append("")

    # Generate fuzzed inputs
    generated = 0
    for i in range(iterations):
        # Select mutation strategy
        mutation = random.choice(mutations)
        magic = random.choice(magic_values) if magic_values else ""

        # Generate input based on format
        if template.get("format") == "text":
            fuzzed_input = f"Test input {i}: {mutation} - {magic}"
        elif template.get("format") == "binary":
            fuzzed_input = bytes([random.randint(0, 255) for _ in random.randint(1, 100)]).hex()
        elif template.get("format") == "json":
            fuzzed_input = json.dumps({"test": i, "mutation": mutation, "magic": magic})
        elif template.get("format") == "http":
            fuzzed_input = f"GET /test{i}?mut={mutation} HTTP/1.1\r\nHost: target\r\n\r\n"
        else:
            fuzzed_input = f"Fuzzed input {i}: {magic}"

        # Save to file if output_dir specified
        if output_dir:
            output_file = os.path.join(output_dir, f"input_{generated:06d}")
            try:
                mode = 'wb' if template.get("format") == "binary" else 'w'
                with open(output_file, mode) as f:
                    if template.get("format") == "binary":
                        f.write(bytes.fromhex(fuzzed_input))
                    else:
                        f.write(fuzzed_input)
            except Exception:
                pass

        generated += 1

        # Show first few samples
        if i < 3:
            output.append(f"[{i}] {mutation}: {fuzzed_input[:100]}")

    if iterations > 3:
        output.append(f"... and {iterations - 3} more inputs")

    output.append(f"\nGenerated {generated} fuzzed inputs")

    return "\n".join(output)


def fuzz_analyze_crash(crash_input: str, target: str, args: str = "") -> str:
    """Analyze crash with debugger.

    Args:
        crash_input: Crash input data
        target: Target binary
        args: Target arguments

    Returns:
        Crash analysis
    """
    if not os.path.isfile(target):
        return f"Error: Target not found: {target}"

    output = [
        f"=== Crash Analysis ===",
        f"Target: {target}",
        f"Input: {crash_input[:100]}...",
        "",
    ]

    # Try to run with input
    try:
        cmd = [target] + args.split() if args else [target]

        # Write input to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(crash_input)
            temp_file = f.name

        # Try to run with input
        result = subprocess.run(
            cmd + [temp_file] if not any("@@" in a for a in args.split()) else cmd,
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

        if result.stderr:
            output.append("\nStderr:")
            output.append(result.stderr[:500])

    except subprocess.TimeoutExpired:
        output.append("Result: TIMEOUT")
    except Exception as e:
        output.append(f"Error: {e}")
    finally:
        try:
            os.unlink(temp_file)
        except:
            pass

    return "\n".join(output)


def fuzz_mutation_strategies(input_data: str, count: int = 10) -> str:
    """Generate mutations using various strategies.

    Args:
        input_data: Original input data
        count: Number of mutations to generate

    Returns:
        Generated mutations
    """
    output = [f"=== Mutation Strategies for: {input_data[:50]}... ===", ""]

    strategies = {
        "bit_flip": lambda d: ''.join(chr(ord(c) ^ (1 << (i % 8))) if len(d) > i else c for i, c in enumerate(d)),
        "byte_flip": lambda d: ''.join(chr(ord(c) ^ 0xFF) if random.random() < 0.1 else c for c in d),
        "random_byte": lambda d: ''.join(chr(random.randint(0, 255)) if random.random() < 0.1 else c for c in d),
        "delete": lambda d: ''.join(c for i, c in enumerate(d) if random.random() < 0.9),
        "duplicate": lambda d: ''.join(c * 2 if random.random() < 0.1 else c for c in d),
        "null_insert": lambda d: d[:len(d)//2] + '\x00' + d[len(d)//2:],
        "format_string": lambda d: d.replace("%s", "{{placeholder}}"),
    }

    for strategy_name, strategy_func in strategies.items():
        try:
            mutated = strategy_func(input_data)
            output.append(f"{strategy_name}: {mutated[:100]}")
        except Exception as e:
            output.append(f"{strategy_name}: Error - {e}")

    return "\n".join(output)


def fuzz_coverage_guided(target: str, corpus_dir: str) -> str:
    """Set up coverage-guided fuzzing.

    Args:
        target: Target binary
        corpus_dir: Corpus directory

    Returns:
        Coverage-guided fuzzing setup
    """
    output = [
        "=== Coverage-Guided Fuzzing Setup ===",
        f"Target: {target}",
        f"Corpus: {corpus_dir}",
        "",
        "Requirements:",
        "1. Compile target with coverage instrumentation:",
        "   -fsanitize=fuzzer (LibFuzzer)",
        "   -fsanitize=address,fuzzer (ASan + LibFuzzer)",
        "   -fsanitize-coverage=trace-pc-guard (manual)",
        "",
        "2. Collect initial corpus:",
        "   mkdir corpus && cp /path/to/interesting/* corpus/",
        "",
        "3. Run coverage-guided fuzzer:",
        "   ./fuzzer_binary corpus -max_total_time=3600",
        "",
        "For Spectra integration:",
        "1. Use libfuzzer_run tool",
        "2. Specify corpus_dir and max_time",
        "3. Analyze crashes with afl_analyze_crash or libfuzzer_crash_info",
    ]

    return "\n".join(output)


def fuzz_dictionary_format(format: str, keywords: list) -> str:
    """Create dictionary file for fuzzers.

    Args:
        format: Dictionary format (afl|libfuzzer|honggfuzz)
        keywords: List of keywords

    Returns:
        Dictionary file content
    """
    output = [f"=== Dictionary Format: {format} ===", ""]

    if format.lower() == "afl":
        output.append("# AFL dictionary format")
        output.extend(keywords)
    elif format.lower() == "libfuzzer":
        output.append("# LibFuzzer dictionary format")
        for kw in keywords:
            output.append(f'"{kw}"')
    elif format.lower() == "honggfuzz":
        output.append("# Honggfuzz dictionary format (one per line)")
        output.extend(keywords)
    else:
        output.append(f"Unknown format: {format}")

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================

def create_fuzzing_framework_tools() -> list[ToolDefinition]:
    """Create fuzzing framework tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="fuzz_create_template",
            description="Create fuzzing template for target",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary path", required=True),
                ParameterSchema(name="input_format", type="string", description="Input format (text|binary|json|xml|http)", required=True, enum=["text", "binary", "json", "xml", "http"]),
                ParameterSchema(name="output_file", type="string", description="Output template file path", required=True),
            ],
            handler=lambda target, input_format, output_file, **kwargs: fuzz_create_template(target, input_format, output_file),
        ),

        ToolDefinition(
            name="fuzz_run_template",
            description="Run fuzzing with template",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="template_file", type="string", description="Template file path", required=True),
                ParameterSchema(name="iterations", type="integer", description="Number of fuzzing iterations", required=False, default=100),
                ParameterSchema(name="output_dir", type="string", description="Optional output directory", required=False, default=""),
            ],
            handler=lambda template_file, iterations=100, output_dir="", **kwargs: fuzz_run_template(template_file, iterations, output_dir),
        ),

        ToolDefinition(
            name="fuzz_analyze_crash",
            description="Analyze crash with target",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="crash_input", type="string", description="Crash input data", required=True),
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="args", type="string", description="Target arguments", required=False, default=""),
            ],
            handler=lambda crash_input, target, args="", **kwargs: fuzz_analyze_crash(crash_input, target, args),
        ),

        ToolDefinition(
            name="fuzz_mutation_strategies",
            description="Generate mutations using various strategies",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="input_data", type="string", description="Original input data", required=True),
                ParameterSchema(name="count", type="integer", description="Number of mutations", required=False, default=10),
            ],
            handler=lambda input_data, count=10, **kwargs: fuzz_mutation_strategies(input_data, count),
        ),

        ToolDefinition(
            name="fuzz_coverage_guided",
            description="Set up coverage-guided fuzzing",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary", required=True),
                ParameterSchema(name="corpus_dir", type="string", description="Corpus directory", required=True),
            ],
            handler=lambda target, corpus_dir, **kwargs: fuzz_coverage_guided(target, corpus_dir),
        ),

        ToolDefinition(
            name="fuzz_dictionary_format",
            description="Create dictionary file for fuzzers",
            category="fuzzing",
            parameters=[
                ParameterSchema(name="format", type="string", description="Dictionary format", required=True, enum=["afl", "libfuzzer", "honggfuzz"]),
                ParameterSchema(name="keywords", type="string", description="Comma-separated keywords", required=True),
            ],
            handler=lambda format, keywords, **kwargs: fuzz_dictionary_format(format, keywords.split(",")),
        ),
    ]


def register_fuzzing_framework_tools(registry: Any) -> int:
    """Register fuzzing framework tools.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    # Fuzzing framework tools are always available (no external dependencies)
    tools = create_fuzzing_framework_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} fuzzing framework tools")
    return len(tools)

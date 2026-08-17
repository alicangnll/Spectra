"""Wireshark packet analysis tool integration (via tshark CLI).

Provides tools for:
- Parsing PCAP files with display filters
- Extracting specific fields from packets
- Generating PCAP statistics
- Protocol hierarchy analysis
- Conversations analysis
- Endpoint analysis
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class WiresharkTool(ExternalTool):
    """Wireshark/tshark packet analysis tool."""

    tool_name = "Wireshark"
    executable_names = ["tshark"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin", "/Applications/Wireshark.app/Contents/MacOS"],
        "Windows": ["C:\\Program Files\\Wireshark", "C:\\Program Files (x86)\\Wireshark"],
    }

    def get_version_args(self) -> list[str]:
        return ["-v"]

    def _extract_version(self, output: str) -> str:
        """Extract TShark version."""
        match = re.search(r"TShark\s+\(GCC\)\s+(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"version\s+(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_wireshark_instance: WiresharkTool | None = None


def get_wireshark() -> WiresharkTool:
    """Get or create Wireshark tool instance."""
    global _wireshark_instance
    if _wireshark_instance is None:
        _wireshark_instance = WiresharkTool()
    return _wireshark_instance


def get_tshark() -> WiresharkTool:
    """Get or create Tshark tool instance (alias for get_wireshark)."""
    return get_wireshark()


def check_wireshark_available() -> bool:
    """Check if Wireshark (tshark) is available."""
    return get_wireshark().is_available()


def _ensure_wireshark() -> str:
    """Ensure Wireshark is available and return tshark path."""
    wireshark = get_wireshark()
    if not wireshark.is_available():
        raise RuntimeError("Wireshark/tshark not found. Install Wireshark from https://www.wireshark.org")
    return wireshark.get_path()


# ============================================================================
# Tool Functions
# ============================================================================


def wireshark_parse(pcap: str, display_filter: str = "", output_format: str = "text") -> str:
    """Parse PCAP file with optional display filter.

    Args:
        pcap: Path to PCAP file
        display_filter: Optional Wireshark display filter
        output_format: Output format (text|json|tabs)

    Returns:
        Packet parsing output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    cmd = [tshark_path, "-r", pcap]

    if display_filter:
        cmd.extend(["-Y", display_filter])

    # Output format
    if output_format == "json":
        cmd.extend(["-T", "json"])
    elif output_format == "tabs":
        cmd.extend(["-T", "tabs"])
    else:
        cmd.extend(["-T", "text"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error parsing PCAP: {result.stderr}"

        return result.stdout or "No packets matched filter"

    except subprocess.TimeoutExpired:
        return "Error: PCAP parsing timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_extract_fields(pcap: str, fields: list[str], display_filter: str = "") -> str:
    """Extract specific fields from packets.

    Args:
        pcap: Path to PCAP file
        fields: List of field names (e.g., ip.src, tcp.dstport, http.request.uri)
        display_filter: Optional display filter

    Returns:
        Extracted fields output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    cmd = [tshark_path, "-r", pcap]

    if display_filter:
        cmd.extend(["-Y", display_filter])

    # Add fields to extract
    cmd.extend(["-T", "fields"])
    for field in fields:
        cmd.extend(["-e", field])

    # Use header and separator for readability
    cmd.extend(["-E", "header=y", "-E", "separator=|"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error extracting fields: {result.stderr}"

        return result.stdout or "No packets matched"

    except subprocess.TimeoutExpired:
        return "Error: Field extraction timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_statistics(pcap: str) -> str:
    """Get PCAP statistics.

    Args:
        pcap: Path to PCAP file

    Returns:
        PCAP statistics output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    # Get general stats
    cmd = [tshark_path, "-r", pcap, "-q", "-z", "conv,tcp", "-z", "conv,udp", "-z", "prot,hierarchy"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        output = []
        output.append("=== PCAP Statistics ===")
        output.append(f"File: {pcap}")

        # Get packet count
        count_cmd = [tshark_path, "-r", pcap, "-q", "-z", "io,stat,0"]
        count_result = subprocess.run(count_cmd, capture_output=True, text=True, timeout=60)
        if count_result.returncode == 0:
            output.append(count_result.stdout)

        # Add detailed stats
        if result.returncode == 0:
            output.append(result.stdout)

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Statistics generation timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_protocols(pcap: str) -> str:
    """Get protocol hierarchy from PCAP.

    Args:
        pcap: Path to PCAP file

    Returns:
        Protocol hierarchy output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    cmd = [tshark_path, "-r", pcap, "-q", "-z", "prot,hierarchy,tree"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error getting protocol hierarchy: {result.stderr}"

        return result.stdout or "No protocol data"

    except subprocess.TimeoutExpired:
        return "Error: Protocol analysis timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_conversations(pcap: str, proto: str = "tcp") -> str:
    """Get conversations from PCAP.

    Args:
        pcap: Path to PCAP file
        proto: Protocol type (tcp|udp)

    Returns:
        Conversations output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    cmd = [tshark_path, "-r", pcap, "-q", "-z", f"conv,{proto}"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error getting conversations: {result.stderr}"

        return result.stdout or f"No {proto.upper()} conversations"

    except subprocess.TimeoutExpired:
        return "Error: Conversations analysis timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_endpoints(pcap: str, proto: str = "tcp") -> str:
    """Get endpoints from PCAP.

    Args:
        pcap: Path to PCAP file
        proto: Protocol type (tcp|udp)

    Returns:
        Endpoints output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    cmd = [tshark_path, "-r", pcap, "-q", "-z", f"endpoints,{proto}"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error getting endpoints: {result.stderr}"

        return result.stdout or f"No {proto.upper()} endpoints"

    except subprocess.TimeoutExpired:
        return "Error: Endpoints analysis timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_http_objects(pcap: str) -> str:
    """Export HTTP objects from PCAP.

    Args:
        pcap: Path to PCAP file

    Returns:
        HTTP objects export info
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    # Use export objects command
    cmd = [tshark_path, "-r", pcap, "--export-objects", "http,http_objects"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = []
        output.append("HTTP Objects Export")
        output.append(f"PCAP: {pcap}")

        if result.returncode == 0:
            output.append("Objects exported to http_objects/ directory")
            output.append(result.stdout)
        else:
            output.append(f"Error: {result.stderr}")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: HTTP objects export timed out"
    except Exception as e:
        return f"Error: {e}"


def wireshark_follow_stream(pcap: str, stream_index: int, proto: str = "tcp") -> str:
    """Follow TCP/UDP stream.

    Args:
        pcap: Path to PCAP file
        stream_index: Stream index to follow
        proto: Protocol (tcp|udp)

    Returns:
        Stream data output
    """
    if not os.path.isfile(pcap):
        return f"Error: PCAP file not found: {pcap}"

    tshark_path = _ensure_wireshark()

    # Follow stream using filters
    # Note: This is a simplified version - tshark doesn't have direct "follow stream" CLI
    # We use display filters instead
    filter_cmd = [tshark_path, "-r", pcap, "-Y", f"{proto}.stream eq {stream_index}", "-T", "fields", "-e", "data.text"]

    try:
        result = subprocess.run(
            filter_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        output = []
        output.append(f"=== Stream {stream_index} ({proto.upper()}) ===")

        if result.returncode == 0:
            output.append(result.stdout)
        else:
            output.append(f"Error: {result.stderr}")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Stream follow timed out"
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Tool Definitions
# ============================================================================


def create_wireshark_tools() -> list[ToolDefinition]:
    """Create Wireshark tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="wireshark_parse",
            description="Parse PCAP file with optional display filter",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
                ParameterSchema(
                    name="display_filter",
                    type="string",
                    description="Wireshark display filter (optional)",
                    required=False,
                    default="",
                ),
                ParameterSchema(
                    name="output_format",
                    type="string",
                    description="Output format (text|json|tabs)",
                    required=False,
                    default="text",
                    enum=["text", "json", "tabs"],
                ),
            ],
            handler=lambda pcap, display_filter="", output_format="text", **kwargs: wireshark_parse(
                pcap, display_filter, output_format
            ),
        ),
        ToolDefinition(
            name="wireshark_extract_fields",
            description="Extract specific fields from packets",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
                ParameterSchema(
                    name="fields",
                    type="string",
                    description="Comma-separated field names (e.g., ip.src,tcp.dstport)",
                    required=True,
                ),
                ParameterSchema(
                    name="display_filter",
                    type="string",
                    description="Display filter (optional)",
                    required=False,
                    default="",
                ),
            ],
            handler=lambda pcap, fields, display_filter="", **kwargs: wireshark_extract_fields(
                pcap, fields.split(","), display_filter
            ),
        ),
        ToolDefinition(
            name="wireshark_statistics",
            description="Get PCAP statistics",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
            ],
            handler=lambda pcap, **kwargs: wireshark_statistics(pcap),
        ),
        ToolDefinition(
            name="wireshark_protocols",
            description="Get protocol hierarchy from PCAP",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
            ],
            handler=lambda pcap, **kwargs: wireshark_protocols(pcap),
        ),
        ToolDefinition(
            name="wireshark_conversations",
            description="Get conversations from PCAP",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
                ParameterSchema(
                    name="proto",
                    type="string",
                    description="Protocol (tcp|udp)",
                    required=False,
                    default="tcp",
                    enum=["tcp", "udp"],
                ),
            ],
            handler=lambda pcap, proto="tcp", **kwargs: wireshark_conversations(pcap, proto),
        ),
        ToolDefinition(
            name="wireshark_endpoints",
            description="Get endpoints from PCAP",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
                ParameterSchema(
                    name="proto",
                    type="string",
                    description="Protocol (tcp|udp)",
                    required=False,
                    default="tcp",
                    enum=["tcp", "udp"],
                ),
            ],
            handler=lambda pcap, proto="tcp", **kwargs: wireshark_endpoints(pcap, proto),
        ),
        ToolDefinition(
            name="wireshark_http_objects",
            description="Export HTTP objects from PCAP",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
            ],
            handler=lambda pcap, **kwargs: wireshark_http_objects(pcap),
        ),
        ToolDefinition(
            name="wireshark_follow_stream",
            description="Follow TCP/UDP stream",
            category="network",
            parameters=[
                ParameterSchema(name="pcap", type="string", description="Path to PCAP file", required=True),
                ParameterSchema(
                    name="stream_index", type="integer", description="Stream index to follow", required=True
                ),
                ParameterSchema(
                    name="proto",
                    type="string",
                    description="Protocol (tcp|udp)",
                    required=False,
                    default="tcp",
                    enum=["tcp", "udp"],
                ),
            ],
            handler=lambda pcap, stream_index, proto="tcp", **kwargs: wireshark_follow_stream(
                pcap, stream_index, proto
            ),
        ),
    ]


def register_wireshark_tools(registry: Any) -> int:
    """Register Wireshark tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_wireshark_available():
        log_debug("Wireshark/tshark not available, skipping tool registration")
        return 0

    tools = create_wireshark_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Wireshark tools")
    return len(tools)

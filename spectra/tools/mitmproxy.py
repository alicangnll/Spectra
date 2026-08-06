"""mitmproxy HTTPS interception tool integration.

Provides tools for:
- Starting mitmproxy proxy server
- Capturing HTTP/HTTPS flows
- Exporting flows
- Flow analysis
- Certificate handling
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

from ..core.tool_infrastructure import ExternalTool, ToolSafety
from ..core.logging import log_debug, log_error, log_info
from ..tools.base import ParameterSchema, ToolDefinition


class MitmproxyTool(ExternalTool):
    """mitmproxy HTTPS interception tool."""

    tool_name = "mitmproxy"
    executable_names = ["mitmproxy", "mitmdump", "mitmweb"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "Windows": ["C:\\Program Files\\mitmproxy", "%LOCALAPPDATA%\\Programs\\Python\\Scripts"],
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract mitmproxy version."""
        match = re.search(r"Mitmproxy[:\s]+(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_mitmproxy_instance: MitmproxyTool | None = None


def get_mitmproxy() -> MitmproxyTool:
    """Get or create mitmproxy tool instance."""
    global _mitmproxy_instance
    if _mitmproxy_instance is None:
        _mitmproxy_instance = MitmproxyTool()
    return _mitmproxy_instance


def check_mitmproxy_available() -> bool:
    """Check if mitmproxy is available."""
    return get_mitmproxy().is_available()


def _ensure_mitmproxy(tool: str = "mitmdump") -> str:
    """Ensure mitmproxy is available and return tool path."""
    mitmproxy = get_mitmproxy()
    if not mitmproxy.is_available():
        raise RuntimeError("mitmproxy not found. Install from https://mitmproxy.org")

    # Try to find specific tool
    path = shutil.which(tool)
    if path:
        return path

    # Fallback to base tool
    return mitmproxy.get_path()


# ============================================================================
# Tool Functions
# ============================================================================

def mitmproxy_start(listen_port: int, listen_host: str = "127.0.0.1", ssl_insecure: bool = False, upstream_proxy: str = "") -> str:
    """Start mitmproxy on specified port.

    Args:
        listen_port: Port to listen on
        listen_host: Host to bind to (default: 127.0.0.1)
        ssl_insecure: Skip SSL certificate verification
        upstream_proxy: Upstream proxy (host:port)

    Returns:
        Start command/status
    """
    # Check safety
    is_safe, reason = ToolSafety.check_network_safety("intercept", f"{listen_host}:{listen_port}")
    if not is_safe:
        return f"HTTPS interception blocked: {reason}"

    mitmproxy_path = _ensure_mitmproxy("mitmdump")

    cmd = [
        mitmproxy_path,
        "--listen-host", listen_host,
        "--listen-port", str(listen_port),
    ]

    if ssl_insecure:
        cmd.append("--insecure")

    if upstream_proxy:
        cmd.extend(["--mode", f"upstream:{upstream_proxy}"])

    output = [
        "=== mitmproxy Start Command ===",
        " ".join(cmd),
        "",
        "Note: mitmproxy requires interactive terminal for full operation",
        "For automated capture, use mitmproxy_capture with output file",
    ]

    return "\n".join(output)


def mitmproxy_flows_to_file(output_file: str, listen_port: int = 8080, filter: str = "", duration: int = 60) -> str:
    """Capture flows to file.

    Args:
        output_file: Output file path
        listen_port: Port to listen on
        filter: Flow filter (optional)
        duration: Capture duration in seconds

    Returns:
        Capture result
    """
    mitmproxy_path = _ensure_mitmproxy("mitmdump")

    cmd = [
        mitmproxy_path,
        "--listen-port", str(listen_port),
        "--set", f"outfile={output_file}",
    ]

    if filter:
        cmd.extend(["--set", f"flow_filter={filter}"])

    output = [
        f"=== mitmproxy Capture to {output_file} ===",
        f"Port: {listen_port}",
        f"Duration: {duration}s",
        "",
        "Command: " + " ".join(cmd),
        "",
        "Note: This requires running mitmdump in background",
    ]

    return "\n".join(output)


def mitmproxy_parse_flows(flow_file: str, filter: str = "") -> str:
    """Parse and analyze flows from file.

    Args:
        flow_file: Path to flow file
        filter: Optional filter string

    Returns:
        Flow analysis output
    """
    if not os.path.isfile(flow_file):
        return f"Error: Flow file not found: {flow_file}"

    mitmproxy_path = _ensure_mitmproxy("mitmdump")

    # Use mitmdump to parse flows
    cmd = [
        mitmproxy_path,
        "--rfile", flow_file,
        "--scripts", "-",
    ]

    # Create simple analysis script
    script = """
from mitmproxy import http

def flow(flow):
    # Print flow info
    print(f"{flow.request.method} {flow.request.pretty_url}")
    if flow.response:
        print(f"  -> {flow.response.status_code}")
    print()
"""

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name

        cmd[-1] = script_path

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return f"Error parsing flows: {result.stderr}"

        output = [
            f"=== Flows from {flow_file} ===",
            "",
            result.stdout or "No flows",
        ]

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Flow parsing timed out"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


def mitmproxy_export_flows(flow_file: str, output: str, format: str = "json", filter: str = "") -> str:
    """Export flows to specified format.

    Args:
        flow_file: Path to flow file
        output: Output file path
        format: Export format (json|curl|har)
        filter: Optional filter

    Returns:
        Export result
    """
    if not os.path.isfile(flow_file):
        return f"Error: Flow file not found: {flow_file}"

    mitmproxy_path = _ensure_mitmproxy("mitmdump")

    cmd = [mitmproxy_path, "--rfile", flow_file]

    if format == "curl":
        cmd.extend(["--scripts", "-"])
        script = """
from mitmproxy import http

def flow(flow):
    if flow.response:
        print(flow.request.get_curl_command())
"""
    elif format == "har":
        cmd.extend(["--set", f"hardump={output}"])
    else:  # json
        cmd.extend(["--scripts", "-"])
        script = """
import json
from mitmproxy import http

def flow(flow):
    data = {
        "method": flow.request.method,
        "url": flow.request.pretty_url,
        "headers": dict(flow.request.headers),
    }
    if flow.response:
        data["status"] = flow.response.status_code
        data["response_headers"] = dict(flow.response.headers)
    print(json.dumps(data))
"""

    try:
        if format in ["json", "curl"]:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                script_path = f.name

            cmd[-1] = script_path

            with open(output, 'w') as outf:
                result = subprocess.run(cmd, stdout=outf, text=True, timeout=120)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return f"Error exporting flows: {result.stderr}"

        return f"Flows exported to {output} in {format.upper()} format"

    except subprocess.TimeoutExpired:
        return "Error: Export timed out"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            if format in ["json", "curl"]:
                os.unlink(script_path)
        except:
            pass


def mitmproxy_cert_info() -> str:
    """Get mitmproxy certificate information.

    Returns:
        Certificate info
    """
    # Find mitmproxy CA cert
    home = os.path.expanduser("~")
    cert_paths = [
        os.path.join(home, ".mitmproxy", "mitmproxy-ca-cert.pem"),
        os.path.join(home, ".mitmproxy", "mitmproxy-ca-cert.p12"),
    ]

    output = ["=== mitmproxy Certificate Info ==="]

    for cert_path in cert_paths:
        if os.path.isfile(cert_path):
            output.append(f"Found: {cert_path}")

    if not any(os.path.exists(p) for p in cert_paths):
        output.append("No certificates found")
        output.append("Certificates will be generated on first run")
        output.append("Location: ~/.mitmproxy/")
    else:
        output.append("\nTo install on client:")
        output.append("1. Transfer mitmproxy-ca-cert.pem to device")
        output.append("2. Install as trusted CA certificate")

    return "\n".join(output)


def mitmproxy_reverse_proxy(upstream: str, listen_port: int = 8080) -> str:
    """Start reverse proxy.

    Args:
        upstream: Upstream server (host:port or https://host)
        listen_port: Listen port

    Returns:
        Reverse proxy info
    """
    mitmproxy_path = _ensure_mitmproxy("mitmdump")

    cmd = [
        mitmproxy_path,
        "--listen-port", str(listen_port),
        "--mode", f"reverse:{upstream}",
    ]

    output = [
        "=== mitmproxy Reverse Proxy ===",
        f"Upstream: {upstream}",
        f"Listen port: {listen_port}",
        "",
        "Command: " + " ".join(cmd),
        "",
        "Note: Reverse proxy requires running mitmdump",
    ]

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================

def create_mitmproxy_tools() -> list[ToolDefinition]:
    """Create mitmproxy tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="mitmproxy_start",
            description="Start mitmproxy on specified port (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="listen_port", type="integer", description="Port to listen on", required=True),
                ParameterSchema(name="listen_host", type="string", description="Host to bind to (default: 127.0.0.1)", required=False, default="127.0.0.1"),
                ParameterSchema(name="ssl_insecure", type="boolean", description="Skip SSL certificate verification", required=False, default=False),
                ParameterSchema(name="upstream_proxy", type="string", description="Upstream proxy (host:port)", required=False, default=""),
            ],
            handler=lambda listen_port, listen_host="127.0.0.1", ssl_insecure=False, upstream_proxy="", **kwargs: mitmproxy_start(listen_port, listen_host, ssl_insecure, upstream_proxy),
        ),

        ToolDefinition(
            name="mitmproxy_flows_to_file",
            description="Capture flows to file",
            category="network",
            parameters=[
                ParameterSchema(name="output_file", type="string", description="Output file path", required=True),
                ParameterSchema(name="listen_port", type="integer", description="Port to listen on", required=False, default=8080),
                ParameterSchema(name="filter", type="string", description="Flow filter (optional)", required=False, default=""),
                ParameterSchema(name="duration", type="integer", description="Capture duration in seconds", required=False, default=60),
            ],
            handler=lambda output_file, listen_port=8080, filter="", duration=60, **kwargs: mitmproxy_flows_to_file(output_file, listen_port, filter, duration),
        ),

        ToolDefinition(
            name="mitmproxy_parse_flows",
            description="Parse and analyze flows from file",
            category="network",
            parameters=[
                ParameterSchema(name="flow_file", type="string", description="Path to flow file", required=True),
                ParameterSchema(name="filter", type="string", description="Optional filter string", required=False, default=""),
            ],
            handler=lambda flow_file, filter="", **kwargs: mitmproxy_parse_flows(flow_file, filter),
        ),

        ToolDefinition(
            name="mitmproxy_export_flows",
            description="Export flows to specified format",
            category="network",
            parameters=[
                ParameterSchema(name="flow_file", type="string", description="Path to flow file", required=True),
                ParameterSchema(name="output", type="string", description="Output file path", required=True),
                ParameterSchema(name="format", type="string", description="Export format (json|curl|har)", required=False, default="json", enum=["json", "curl", "har"]),
                ParameterSchema(name="filter", type="string", description="Optional filter", required=False, default=""),
            ],
            handler=lambda flow_file, output, format="json", filter="", **kwargs: mitmproxy_export_flows(flow_file, output, format, filter),
        ),

        ToolDefinition(
            name="mitmproxy_cert_info",
            description="Get mitmproxy certificate information",
            category="network",
            parameters=[],
            handler=lambda **kwargs: mitmproxy_cert_info(),
        ),

        ToolDefinition(
            name="mitmproxy_reverse_proxy",
            description="Start reverse proxy to upstream server",
            category="network",
            parameters=[
                ParameterSchema(name="upstream", type="string", description="Upstream server (host:port or https://host)", required=True),
                ParameterSchema(name="listen_port", type="integer", description="Listen port", required=False, default=8080),
            ],
            handler=lambda upstream, listen_port=8080, **kwargs: mitmproxy_reverse_proxy(upstream, listen_port),
        ),
    ]


def register_mitmproxy_tools(registry: Any) -> int:
    """Register mitmproxy tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_mitmproxy_available():
        log_debug("mitmproxy not available, skipping tool registration")
        return 0

    tools = create_mitmproxy_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} mitmproxy tools")
    return len(tools)

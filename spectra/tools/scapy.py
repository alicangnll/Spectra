"""Scapy packet crafting and manipulation tool integration.

Provides tools for:
- Crafting custom packets
- Sending packets
- Sniffing network traffic
- Packet analysis
- Protocol-specific operations (TCP, UDP, ICMP, ARP, DNS, etc.)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any

from ..core.tool_infrastructure import ExternalTool, ToolSafety
from ..core.logging import log_debug, log_error, log_info
from ..tools.base import ParameterSchema, ToolDefinition


class ScapyTool(ExternalTool):
    """Scapy packet manipulation tool."""

    tool_name = "Scapy"
    executable_names = ["scapy"]  # Check if scapy module is available

    def __init__(self, required: bool = False):
        super().__init__(required)
        self._python_path = sys.executable

    def find_tool(self) -> Any:
        """Check if Scapy Python module is available."""
        if self._location:
            return self._location if self._location.is_valid else None

        try:
            # Try to import scapy
            import importlib
            spec = importlib.util.find_spec("scapy")
            if spec is not None:
                from ..core.tool_infrastructure import ToolLocation
                location = ToolLocation(path=spec.origin or "scapy", version=self._extract_version(""))
                location.is_valid = True
                self._location = location
                return location
        except Exception as e:
            log_debug(f"Scapy check failed: {e}")

        return None

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract Scapy version."""
        try:
            from scapy import VERSION
            return VERSION
        except Exception:
            return "unknown"


# Global instance
_scapy_instance: ScapyTool | None = None


def get_scapy() -> ScapyTool:
    """Get or create Scapy tool instance."""
    global _scapy_instance
    if _scapy_instance is None:
        _scapy_instance = ScapyTool()
    return _scapy_instance


def check_scapy_available() -> bool:
    """Check if Scapy is available."""
    return get_scapy().is_available()


def _ensure_scapy() -> bool:
    """Ensure Scapy is available."""
    if not check_scapy_available():
        raise RuntimeError("Scapy not found. Install with: pip install scapy")
    return True


def _run_scapy_script(script: str) -> str:
    """Run Python script with Scapy.

    Args:
        script: Scapy Python code

    Returns:
        Script output
    """
    _ensure_scapy()

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name

        cmd = [sys.executable, script_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(result.stderr)

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Scapy script timed out"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


# ============================================================================
# Tool Functions
# ============================================================================

def scapy_craft_packet(protocol: str, parameters: dict) -> str:
    """Craft packet with Scapy.

    Args:
        protocol: Protocol name (ethernet, ip, tcp, udp, icmp, arp, dns, http)
        parameters: Protocol parameters dict

    Returns:
        Packet representation
    """
    _ensure_scapy()

    # Build Scapy script
    script_lines = [
        "from scapy.all import *",
        "",
    ]

    # Map protocol names to Scapy classes
    protocol_map = {
        "ethernet": "Ether",
        "ip": "IP",
        "tcp": "TCP",
        "udp": "UDP",
        "icmp": "ICMP",
        "arp": "ARP",
        "dns": "DNS",
        "http": "HTTP",  # Note: HTTP requires scapy-http
    }

    scapy_class = protocol_map.get(protocol.lower(), "Raw")

    # Build packet
    params_str = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}' for k, v in parameters.items())

    script_lines.extend([
        f'pkt = {scapy_class}({params_str})',
        'print(pkt)',
        'print(pkt.summary())',
    ])

    return _run_scapy_script("\n".join(script_lines))


def scapy_send_packet(packet: str, interface: str = "", count: int = 1) -> str:
    """Send crafted packet.

    Args:
        packet: Packet description (JSON or simplified format)
        interface: Network interface (optional)
        count: Number of times to send

    Returns:
        Send result
    """
    _ensure_scapy()

    # Check safety
    is_safe, reason = ToolSafety.check_network_safety("send", "")
    if not is_safe:
        return f"Operation blocked: {reason}"

    # Parse packet (simplified - in real use, would parse JSON)
    # For now, create basic script
    script_lines = [
        "from scapy.all import *",
        "",
        f"conf.iface = '{interface}'" if interface else "# Using default interface",
        "",
        f"# Send packet {count} times",
        f"# Packet: {packet[:100]}...",
        'print("Packet sending requires explicit approval")',
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_sniff(filter: str, count: int = 10, interface: str = "", timeout: int = 30) -> str:
    """Sniff packets with BPF filter.

    Args:
        filter: BPF filter string
        count: Number of packets to capture
        interface: Network interface (optional)
        timeout: Capture timeout in seconds

    Returns:
        Captured packets
    """
    _ensure_scapy()

    # Check safety
    is_safe, reason = ToolSafety.check_network_safety("sniff", "")
    if not is_safe:
        return f"Operation blocked: {reason}"

    filter_display = filter or "none"
    script_lines = [
        "from scapy.all import *",
        "",
        f"conf.iface = '{interface}'" if interface else "# Using default interface",
        "",
        f'print("Sniffing {count} packets with filter: {filter_display}")',
        'print("Note: Packet capture requires explicit approval")',
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_trace(target: str, max_ttl: int = 30, timeout: int = 2) -> str:
    """TCP/UDP/ICMP traceroute.

    Args:
        target: Target host
        max_ttl: Maximum TTL
        timeout: Per-hop timeout

    Returns:
        Traceroute results
    """
    _ensure_scapy()

    script_lines = [
        "from scapy.all import *",
        "",
        f"target = '{target}'",
        f"max_ttl = {max_ttl}",
        f"timeout = {timeout}",
        "",
        "print('Traceroute requires explicit approval')",
        "print(f'Target: {target}, Max TTL: {max_ttl}')",
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_tcp_scan(target: str, ports: str, timeout: int = 2) -> str:
    """TCP port scan (SYN/ACK/XMAS/etc).

    Args:
        target: Target host
        ports: Port range (e.g., "1-100" or "22,80,443")
        timeout: Timeout per port

    Returns:
        Scan results
    """
    _ensure_scapy()

    # Check safety - port scanning requires approval
    is_safe, reason = ToolSafety.check_network_safety("scan", target)
    if not is_safe:
        return f"Operation blocked: {reason}"

    script_lines = [
        "from scapy.all import *",
        "",
        f"target = '{target}'",
        f"ports = '{ports}'",
        f"timeout = {timeout}",
        "",
        "print('Port scanning requires explicit approval')",
        "print(f'Target: {target}, Ports: {ports}')",
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_arp_scan(network: str) -> str:
    """ARP scan local network.

    Args:
        network: Network in CIDR (e.g., "192.168.1.0/24")

    Returns:
        ARP scan results
    """
    _ensure_scapy()

    is_safe, reason = ToolSafety.check_network_safety("scan", network)
    if not is_safe:
        return f"Operation blocked: {reason}"

    script_lines = [
        "from scapy.all import *",
        "",
        f"network = '{network}'",
        "",
        "print('ARP scanning requires explicit approval')",
        "print(f'Network: {network}')",
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_dns_query(domain: str, server: str = "8.8.8.8", record_type: str = "A") -> str:
    """Send DNS query.

    Args:
        domain: Domain to query
        server: DNS server (default: 8.8.8.8)
        record_type: DNS record type (A, AAAA, MX, TXT, etc.)

    Returns:
        DNS response
    """
    _ensure_scapy()

    script_lines = [
        "from scapy.all import *",
        "",
        f"domain = '{domain}'",
        f"server = '{server}'",
        f"record_type = '{record_type}'",
        "",
        f"pkt = IP(dst=server) / UDP(dport=53) / DNS(qd=DNSQR(qname=domain, qtype='{record_type}'))",
        "resp = sr1(pkt, timeout=5)",
        "if resp:",
        "    print(resp.summary())",
        "    print(resp[DNS].summary())",
        "else:",
        "    print('No response')",
    ]

    return _run_scapy_script("\n".join(script_lines))


def scapy_packet_info(packet: str) -> str:
    """Analyze packet hex dump or description.

    Args:
        packet: Packet data (hex string or description)

    Returns:
        Packet analysis
    """
    _ensure_scapy()

    script_lines = [
        "from scapy.all import *",
        "",
        f"packet_hex = '{packet}'",
        "",
        "try:",
        "    pkt = Ether(packet_hex)",
        "    print(pkt.show())",
        "except:",
        "    print('Could not parse packet')",
    ]

    return _run_scapy_script("\n".join(script_lines))


# ============================================================================
# Tool Definitions
# ============================================================================

def create_scapy_tools() -> list[ToolDefinition]:
    """Create Scapy tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="scapy_craft_packet",
            description="Craft custom packet with Scapy",
            category="network",
            parameters=[
                ParameterSchema(name="protocol", type="string", description="Protocol (ethernet|ip|tcp|udp|icmp|arp|dns)", required=True),
                ParameterSchema(name="parameters", type="string", description="Packet parameters as JSON", required=True),
            ],
            handler=lambda protocol, parameters, **kwargs: scapy_craft_packet(protocol, json.loads(parameters) if isinstance(parameters, str) else parameters),
        ),

        ToolDefinition(
            name="scapy_send_packet",
            description="Send crafted packet (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="packet", type="string", description="Packet description", required=True),
                ParameterSchema(name="interface", type="string", description="Network interface (optional)", required=False, default=""),
                ParameterSchema(name="count", type="integer", description="Number of times to send", required=False, default=1),
            ],
            handler=lambda packet, interface="", count=1, **kwargs: scapy_send_packet(packet, interface, count),
        ),

        ToolDefinition(
            name="scapy_sniff",
            description="Sniff packets with BPF filter (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="filter", type="string", description="BPF filter string", required=False, default=""),
                ParameterSchema(name="count", type="integer", description="Number of packets to capture", required=False, default=10),
                ParameterSchema(name="interface", type="string", description="Network interface (optional)", required=False, default=""),
                ParameterSchema(name="timeout", type="integer", description="Capture timeout in seconds", required=False, default=30),
            ],
            handler=lambda filter="", count=10, interface="", timeout=30, **kwargs: scapy_sniff(filter, count, interface, timeout),
        ),

        ToolDefinition(
            name="scapy_trace",
            description="Traceroute to target (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target host", required=True),
                ParameterSchema(name="max_ttl", type="integer", description="Maximum TTL", required=False, default=30),
                ParameterSchema(name="timeout", type="integer", description="Per-hop timeout", required=False, default=2),
            ],
            handler=lambda target, max_ttl=30, timeout=2, **kwargs: scapy_trace(target, max_ttl, timeout),
        ),

        ToolDefinition(
            name="scapy_tcp_scan",
            description="TCP port scan (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target host", required=True),
                ParameterSchema(name="ports", type="string", description="Port range (e.g., 1-100 or 22,80,443)", required=True),
                ParameterSchema(name="timeout", type="integer", description="Timeout per port", required=False, default=2),
            ],
            handler=lambda target, ports, timeout=2, **kwargs: scapy_tcp_scan(target, ports, timeout),
        ),

        ToolDefinition(
            name="scapy_arp_scan",
            description="ARP scan local network (requires approval)",
            category="network",
            parameters=[
                ParameterSchema(name="network", type="string", description="Network in CIDR (e.g., 192.168.1.0/24)", required=True),
            ],
            handler=lambda network, **kwargs: scapy_arp_scan(network),
        ),

        ToolDefinition(
            name="scapy_dns_query",
            description="Send DNS query",
            category="network",
            parameters=[
                ParameterSchema(name="domain", type="string", description="Domain to query", required=True),
                ParameterSchema(name="server", type="string", description="DNS server", required=False, default="8.8.8.8"),
                ParameterSchema(name="record_type", type="string", description="DNS record type (A|AAAA|MX|TXT|CNAME)", required=False, default="A"),
            ],
            handler=lambda domain, server="8.8.8.8", record_type="A", **kwargs: scapy_dns_query(domain, server, record_type),
        ),

        ToolDefinition(
            name="scapy_packet_info",
            description="Analyze packet hex dump",
            category="network",
            parameters=[
                ParameterSchema(name="packet", type="string", description="Packet data (hex string)", required=True),
            ],
            handler=lambda packet, **kwargs: scapy_packet_info(packet),
        ),
    ]


def register_scapy_tools(registry: Any) -> int:
    """Register Scapy tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_scapy_available():
        log_debug("Scapy not available, skipping tool registration")
        return 0

    tools = create_scapy_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Scapy tools")
    return len(tools)

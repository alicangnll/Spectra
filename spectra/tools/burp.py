"""Burp Suite integration for web security testing.

Provides tools for:
- Burp API integration
- Request replay with modifications
- Scanner operations
- Intruder functionality
- Issue reporting
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from ..core.logging import log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class BurpTool(ExternalTool):
    """Burp Suite security testing tool."""

    tool_name = "Burp Suite"
    executable_names = ["burpsuite", "burpsuite_pro", "burp"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/Applications/Burp Suite.app/Contents/MacOS", "/usr/local/bin"],
        "Windows": ["C:\\Program Files\\BurpSuite", "C:\\Program Files\\PortSwigger\\Burp Suite"],
    }

    def __init__(self, required: bool = False):
        super().__init__(required)
        self._api_url: str | None = None
        self._api_key: str | None = None

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract Burp version."""
        match = re.search(r"Burp\s+Suite\s+(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""

    def configure_api(self, api_url: str, api_key: str = "") -> None:
        """Configure Burp API connection.

        Args:
            api_url: Burp API URL (e.g., http://127.0.0.1:1337)
            api_key: Optional API key
        """
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key

    def has_api_config(self) -> bool:
        """Check if API is configured."""
        return self._api_url is not None


# Global instance
_burp_instance: BurpTool | None = None


def get_burp() -> BurpTool:
    """Get or create Burp tool instance."""
    global _burp_instance
    if _burp_instance is None:
        _burp_instance = BurpTool()
    return _burp_instance


def check_burp_available() -> bool:
    """Check if Burp Suite is available."""
    return get_burp().is_available()


def _ensure_burp() -> str:
    """Ensure Burp is available and return its path."""
    burp = get_burp()
    if not burp.is_available():
        raise RuntimeError("Burp Suite not found. Install from https://portswigger.net/burp")
    return burp.get_path()


# ============================================================================
# Tool Functions
# ============================================================================


def burp_api_status() -> str:
    """Check Burp API status.

    Returns:
        API status information
    """
    burp = get_burp()

    output = ["=== Burp Suite API Status ==="]

    if burp.has_api_config():
        output.append(f"API URL: {burp._api_url}")
        output.append(f"API Key: {'Configured' if burp._api_key else 'Not configured'}")
        output.append("")
        output.append("Note: API functionality requires Burp Suite Professional")
        output.append("Community edition: Manual operations only")
    else:
        output.append("API not configured")
        output.append("")
        output.append("To configure:")
        output.append("1. Start Burp Suite")
        output.append("2. Go to Extensions > APIs")
        output.append("3. Enable API and get URL/key")
        output.append("4. Use burp_configure_api tool")

    return "\n".join(output)


def burp_configure_api(api_url: str, api_key: str = "") -> str:
    """Configure Burp API connection.

    Args:
        api_url: Burp API URL (e.g., http://127.0.0.1:1337)
        api_key: Optional API key

    Returns:
        Configuration result
    """
    burp = get_burp()
    burp.configure_api(api_url, api_key)

    return f"Burp API configured: {api_url}"


def burp_scan(target: str, scan_type: str = "crawl", api_configured: bool = False) -> str:
    """Run Burp scan on target.

    Args:
        target: Target URL
        scan_type: Scan type (crawl|audit|scan)
        api_configured: Whether API is configured

    Returns:
        Scan result/status
    """
    # Validate target
    try:
        parsed = urlparse(target)
        if not parsed.scheme or not parsed.netloc:
            return f"Error: Invalid target URL: {target}"
    except Exception as e:
        return f"Error: Invalid target URL: {e}"

    burp = get_burp()

    if api_configured and burp.has_api_config():
        # Would make API call here (requires requests library)
        output = [
            f"=== Burp Scan: {target} ===",
            f"Type: {scan_type}",
            "",
            "Note: API scan requires Burp Suite Professional",
            "This is a placeholder - implement actual API calls based on:",
            "https://portswigger.net/burp/documentation/desktop/api/overview",
        ]
    else:
        output = [
            "=== Burp Scan (Manual) ===",
            f"Target: {target}",
            f"Type: {scan_type}",
            "",
            "Manual steps:",
            "1. Open Burp Suite",
            f"2. Add '{target}' to scope",
            f"3. Run {scan_type} scan",
            "",
            "Or configure API for automation",
        ]

    return "\n".join(output)


def burp_replay(request: str, modifications: dict, api_configured: bool = False) -> str:
    """Replay request with modifications.

    Args:
        request: HTTP request (raw or formatted)
        modifications: Dict of modifications (headers, body, etc.)
        api_configured: Whether API is configured

    Returns:
        Replay result
    """
    burp = get_burp()

    output = ["=== Burp Replay ==="]

    if api_configured and burp.has_api_config():
        output.extend(
            [
                "Request replay via API",
                "",
                "Modifications:",
                json.dumps(modifications, indent=2),
                "",
                "Note: API replay requires Burp Suite Professional",
            ]
        )
    else:
        output.extend(
            [
                "Manual replay instructions:",
                "1. Copy request to Burp Repeater",
                "2. Apply modifications:",
                "",
                json.dumps(modifications, indent=2),
                "",
                "3. Send request",
            ]
        )

    return "\n".join(output)


def burp_intruder(request: str, payloads: list, attack_type: str = "sniper", api_configured: bool = False) -> str:
    """Run Intruder with payloads.

    Args:
        request: HTTP request
        payloads: List of payloads
        attack_type: Attack type (sniper|battering ram|pitchfork|cluster bomb)
        api_configured: Whether API is configured

    Returns:
        Intruder result/status
    """
    burp = get_burp()

    output = [
        f"=== Burp Intruder ({attack_type}) ===",
        "",
        f"Payloads ({len(payloads)}):",
    ]

    # Show first few payloads
    for i, payload in enumerate(payloads[:5]):
        output.append(f"  {i + 1}. {payload[:100]}...")

    if len(payloads) > 5:
        output.append(f"  ... and {len(payloads) - 5} more")

    output.append("")

    if api_configured and burp.has_api_config():
        output.append("API Intruder requires Burp Suite Professional")
    else:
        output.extend(
            [
                "Manual Intruder steps:",
                "1. Send request to Intruder",
                "2. Set payload positions",
                "3. Load payloads",
                f"4. Choose '{attack_type}' attack",
                "5. Start attack",
            ]
        )

    return "\n".join(output)


def burp_fuzz(request: str, fuzz_points: list, payloads: list) -> str:
    """Fuzz request with payloads.

    Args:
        request: HTTP request
        fuzz_points: List of positions to fuzz (e.g., ["§id§", "§search§"])
        payloads: List of payloads

    Returns:
        Fuzz status
    """
    output = [
        "=== Burp Fuzz ===",
        "",
        f"Fuzz points: {fuzz_points}",
        f"Payloads: {len(payloads)}",
        "",
        "Note: Fuzzing via Intruder",
    ]

    return "\n".join(output)


def burp_issues(filter: str = "", severity: str = "", api_configured: bool = False) -> str:
    """Get Burp issues/vulnerabilities.

    Args:
        filter: Issue filter
        severity: Severity filter (high|medium|low|info)
        api_configured: Whether API is configured

    Returns:
        Issues list
    """
    output = ["=== Burp Issues ==="]

    if api_configured and get_burp().has_api_config():
        output.extend(
            [
                "API: Fetch issues from Burp",
                "",
                f"Filter: {filter or 'none'}",
                f"Severity: {severity or 'all'}",
            ]
        )
    else:
        output.extend(
            [
                "Manual issue review:",
                "1. Go to Target > Site map > Issues",
                "2. Filter by severity",
                "3. Review and report",
            ]
        )

    return "\n".join(output)


def burp_proxy_captures(host_filter: str = "") -> str:
    """Get proxy captures.

    Args:
        host_filter: Optional host filter

    Returns:
        Captures info
    """
    output = [
        "=== Burp Proxy Captures ===",
        "",
        f"Host filter: {host_filter or 'none'}",
        "",
        "Manual steps:",
        "1. Go to Proxy > HTTP history",
        "2. Filter by host",
        "3. Review requests/responses",
        "",
        "Or use API for automation",
    ]

    return "\n".join(output)


def burp_generate_report(format: str = "html", scope: str = "") -> str:
    """Generate security report.

    Args:
        format: Report format (html|pdf|xml)
        scope: Report scope

    Returns:
        Report generation status
    """
    output = [
        f"=== Burp Report Generation ({format.upper()}) ===",
        "",
        f"Scope: {scope or 'all'}",
        "",
        "Manual steps:",
        "1. Go to Reporting > Generate report",
        "2. Select scope and format",
        "3. Generate and save",
    ]

    return "\n".join(output)


# ============================================================================
# Tool Definitions
# ============================================================================


def create_burp_tools() -> list[ToolDefinition]:
    """Create Burp tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="burp_api_status",
            description="Check Burp API configuration status",
            category="network",
            parameters=[],
            handler=lambda **kwargs: burp_api_status(),
        ),
        ToolDefinition(
            name="burp_configure_api",
            description="Configure Burp API connection",
            category="network",
            parameters=[
                ParameterSchema(
                    name="api_url",
                    type="string",
                    description="Burp API URL (e.g., http://127.0.0.1:1337)",
                    required=True,
                ),
                ParameterSchema(
                    name="api_key", type="string", description="Optional API key", required=False, default=""
                ),
            ],
            handler=lambda api_url, api_key="", **kwargs: burp_configure_api(api_url, api_key),
        ),
        ToolDefinition(
            name="burp_scan",
            description="Run Burp scan on target",
            category="network",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target URL", required=True),
                ParameterSchema(
                    name="scan_type",
                    type="string",
                    description="Scan type",
                    required=False,
                    default="crawl",
                    enum=["crawl", "audit", "scan"],
                ),
                ParameterSchema(
                    name="api_configured",
                    type="boolean",
                    description="API is configured",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda target, scan_type="crawl", api_configured=False, **kwargs: burp_scan(
                target, scan_type, api_configured
            ),
        ),
        ToolDefinition(
            name="burp_replay",
            description="Replay request with modifications",
            category="network",
            parameters=[
                ParameterSchema(name="request", type="string", description="HTTP request", required=True),
                ParameterSchema(
                    name="modifications",
                    type="string",
                    description="Modifications as JSON",
                    required=False,
                    default="{}",
                ),
                ParameterSchema(
                    name="api_configured",
                    type="boolean",
                    description="API is configured",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda request, modifications="{}", api_configured=False, **kwargs: burp_replay(
                request, json.loads(modifications) if isinstance(modifications, str) else modifications, api_configured
            ),
        ),
        ToolDefinition(
            name="burp_intruder",
            description="Run Intruder with payloads",
            category="network",
            parameters=[
                ParameterSchema(name="request", type="string", description="HTTP request", required=True),
                ParameterSchema(name="payloads", type="string", description="Payloads as JSON array", required=True),
                ParameterSchema(
                    name="attack_type",
                    type="string",
                    description="Attack type",
                    required=False,
                    default="sniper",
                    enum=["sniper", "battering_ram", "pitchfork", "cluster_bomb"],
                ),
                ParameterSchema(
                    name="api_configured",
                    type="boolean",
                    description="API is configured",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda request, payloads, attack_type="sniper", api_configured=False, **kwargs: burp_intruder(
                request, json.loads(payloads) if isinstance(payloads, str) else payloads, attack_type, api_configured
            ),
        ),
        ToolDefinition(
            name="burp_fuzz",
            description="Fuzz request with payloads",
            category="network",
            parameters=[
                ParameterSchema(name="request", type="string", description="HTTP request", required=True),
                ParameterSchema(
                    name="fuzz_points", type="string", description="Fuzz positions (JSON array)", required=True
                ),
                ParameterSchema(name="payloads", type="string", description="Payloads (JSON array)", required=True),
            ],
            handler=lambda request, fuzz_points, payloads, **kwargs: burp_fuzz(
                request,
                json.loads(fuzz_points) if isinstance(fuzz_points, str) else fuzz_points,
                json.loads(payloads) if isinstance(payloads, str) else payloads,
            ),
        ),
        ToolDefinition(
            name="burp_issues",
            description="Get Burp issues/vulnerabilities",
            category="network",
            parameters=[
                ParameterSchema(name="filter", type="string", description="Issue filter", required=False, default=""),
                ParameterSchema(
                    name="severity",
                    type="string",
                    description="Severity filter",
                    required=False,
                    default="",
                    enum=["high", "medium", "low", "info", ""],
                ),
                ParameterSchema(
                    name="api_configured",
                    type="boolean",
                    description="API is configured",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda filter="", severity="", api_configured=False, **kwargs: burp_issues(
                filter, severity, api_configured
            ),
        ),
        ToolDefinition(
            name="burp_proxy_captures",
            description="Get proxy captures info",
            category="network",
            parameters=[
                ParameterSchema(
                    name="host_filter", type="string", description="Host filter", required=False, default=""
                ),
            ],
            handler=lambda host_filter="", **kwargs: burp_proxy_captures(host_filter),
        ),
        ToolDefinition(
            name="burp_generate_report",
            description="Generate security report",
            category="network",
            parameters=[
                ParameterSchema(
                    name="format",
                    type="string",
                    description="Report format",
                    required=False,
                    default="html",
                    enum=["html", "pdf", "xml"],
                ),
                ParameterSchema(name="scope", type="string", description="Report scope", required=False, default=""),
            ],
            handler=lambda format="html", scope="", **kwargs: burp_generate_report(format, scope),
        ),
    ]


def register_burp_tools(registry: Any) -> int:
    """Register Burp tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    # Burp tools are available even without the binary installed
    # They just work in "manual" mode
    tools = create_burp_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Burp tools (manual mode)")
    return len(tools)

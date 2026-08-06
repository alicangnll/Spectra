"""SSL Pinning Bypass tool for Binary Ninja."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.ssl_pinning import detect_ssl_pinning, get_bypass_techniques
from .compat import require_bv


@tool(category="analysis", description="Detect SSL certificate pinning and provide bypass techniques")
def detect_ssl_pinning_impl() -> str:
    """Scan the binary for SSL certificate pinning implementations.

    Detects SSL pinning in:
    - Android apps (OkHttp, TrustManager, Network Security Config)
    - iOS apps (NSURLSession, AFNetworking, Alamofire)
    - Desktop apps (curl, OpenSSL, WinHTTP, Schannel)

    Returns:
        Detailed report with detected frameworks, functions,
        and bypass techniques for each.
    """
    bv = require_bv()
    return detect_ssl_pinning(binary_view=bv)


@tool(category="analysis", description="Get SSL pinning bypass commands and techniques")
def get_ssl_bypass(
    framework: Annotated[str, "Framework name (okhttp, nssession, openssl, curl, etc.) or 'auto'"] = "auto",
) -> str:
    """Get specific bypass techniques for SSL pinning.

    Args:
        framework: Specific framework name or 'auto' to detect all

    Returns:
        Bypass techniques including:
        - Frida scripts
        - Objection commands
        - Patch locations
        - Hook points
    """
    from ...tools.ssl_pinning import _detect_ssl_pinning_binja

    bv = require_bv()

    if framework == "auto":
        detection = _detect_ssl_pinning_binja(bv)
        frameworks = detection.get("frameworks", [])
    else:
        frameworks = [framework]

    if not frameworks:
        return "No SSL pinning detected. TLS traffic can be intercepted freely."

    techniques = get_bypass_techniques(frameworks)

    report = f"## SSL Pinning Bypass Techniques\n\n"
    report += f"**Target Frameworks:** {', '.join(frameworks)}\n\n"

    if techniques["frida"]:
        report += "### Frida Scripts\n"
        for tech in techniques["frida"]:
            report += f"- **{tech['framework']}** ({tech['language']}): {tech['technique']}\n"

    if techniques["objection"]:
        report += "\n### Objection Commands\n"
        for tech in techniques["objection"]:
            report += f"- **{tech['framework']}**: `{tech['technique']}`\n"

    if techniques["hook"]:
        report += "\n### Hook Points\n"
        for tech in techniques["hook"]:
            report += f"- **{tech['framework']}**: {tech['technique']}\n"

    return report

"""SSL Pinning detection and bypass analysis tool.

Detects SSL certificate pinning implementations in mobile/desktop applications
and provides bypass techniques for Android, iOS, and various frameworks.
"""

from __future__ import annotations

import re
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idc
    import idautils
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Import compatibility helpers
from .ida_helpers import get_disasm_text

# Try to import Binary Ninja API
try:
    import binaryninja
    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# SSL Pinning detection patterns for various frameworks
SSL_PINNING_PATTERNS = {
    # Android
    "okhttp": {
        "language": "android",
        "patterns": [
            r"certificatePinner\s*\(",
            r"CertificatePinger\.builder",
            r"\.certificatePinner\s*\(",
            r"okhttp.*CertificatePinner",
        ],
        "bypass": [
            "Hook OkHttpClient.Builder",
            "Modify certificatePinner to return empty",
            "Use Frida: sslpinnerfrida",
        ],
        "severity": "medium",
    },
    "network_security_config": {
        "language": "android",
        "patterns": [
            r"network_security_config",
            r"res/xml/network_security_config",
            r"android:networkSecurityConfig",
        ],
        "bypass": [
            "Modify network_security_config.xml",
            "Add <base-config cleartextTrafficPermitted=\"true\">",
            "Disable certificate validation",
        ],
        "severity": "low",
    },
    "trust_manager": {
        "language": "android",
        "patterns": [
            r"TrustManagerFactory",
            r"X509TrustManager",
            r"checkServerTrusted",
            r"checkClientTrusted",
            r"getAcceptedIssuers",
        ],
        "bypass": [
            "Hook X509TrustManager.checkServerTrusted",
            "Return empty array for getAcceptedIssuers",
            "Implement custom TrustManager that accepts all",
        ],
        "severity": "high",
    },
    "ssl_context": {
        "language": "android",
        "patterns": [
            r"SSLContext\.init",
            r"TrustManager.*init",
            r"keyManager\.init",
            r"SSLContext\.getInstance",
        ],
        "bypass": [
            "Hook SSLContext.init",
            "Pass custom TrustManager that accepts all",
            "Use Frida: android-ssl-pinning-bypass",
        ],
        "severity": "high",
    },

    # iOS
    "ns_url_session": {
        "language": "ios",
        "patterns": [
            r"NSURLSession.*delegate",
            r"didReceiveChallenge",
            r"URLSession.*didReceiveChallenge",
            r"canAuthenticateAgainstProtectionSpace",
        ],
        "bypass": [
            "Hook NSURLSessionDelegate",
            "Implement URLAuthenticationChallenge sender to use credential=None",
            "Use Frida: ios-ssl-kill-switch",
            "Use objection: ios sslpinning disable",
        ],
        "severity": "medium",
    },
    "af_networking": {
        "language": "ios",
        "patterns": [
            r"AFSecurityPolicy",
            r"setSSLPinningMode",
            r"validateCertificateChain",
            r"pinningMode",
        ],
        "bypass": [
            "Hook AFSecurityPolicy.validateCertificateChain",
            "Change pinningMode to None",
            "Use Frida: frida-afnetworking-bypass",
        ],
        "severity": "medium",
    },
    "alamofire": {
        "language": "ios",
        "patterns": [
            r"ServerTrustPolicy",
            r"pinPublicKeys",
            r"evaluateServerTrust",
            r"Alamofire.*certificate",
        ],
        "bypass": [
            "Hook ServerTrustPolicy evaluators",
            "Modify certificate pinning validators",
            "Use objection: ios sslpinning disable --quiet",
        ],
        "severity": "medium",
    },

    # Cross-platform / Desktop
    "curl": {
        "language": "cpp",
        "patterns": [
            r"CURLOPT_SSL_VERIFYPEER",
            r"CURLOPT_SSL_VERIFYHOST",
            r"curl_easy_setopt.*SSL",
            r"CURLOPT_CAINFO",
        ],
        "bypass": [
            "Patch CURLOPT_SSL_VERIFYPEER to 0",
            "Patch CURLOPT_SSL_VERIFYHOST to 0",
            "Hook libcurl SSL verification",
        ],
        "severity": "low",
    },
    "openssl": {
        "language": "cpp",
        "patterns": [
            r"SSL_CTX_set_verify",
            r"SSL_set_verify",
            r"X509_verify_cert",
            r"SSL_CTX_load_verify_locations",
            r"SSL_CTX_set_default_verify_paths",
        ],
        "bypass": [
            "Hook SSL_CTX_set_verify with SSL_VERIFY_NONE",
            "Hook X509_verify_cert to always return 1",
            "Use LD_PRELOAD with custom libssl",
        ],
        "severity": "high",
    },
    "winhttp": {
        "language": "windows",
        "patterns": [
            r"WinHttpSetOption",
            r"WINHTTP_OPTION_SECURITY_FLAGS",
            r"WINHTTP_OPTION_CLIENT_CERT_CONTEXT",
        ],
        "bypass": [
            "Hook WinHttpSetOption",
            "Clear SECURITY_FLAG_STRICT flags",
            "Patch certificate validation in winhttp",
        ],
        "severity": "medium",
    },
    "schannel": {
        "language": "windows",
        "patterns": [
            r"CertVerifyCertificateChainPolicy",
            r"CertGetCertificateChain",
            r"VerifyCertificateChainPolicy",
        ],
        "bypass": [
            "Hook CertVerifyCertificateChainPolicy",
            "Always return CERT_E_UNTRUSTEDROOT or success",
            "Patch schannel.dll",
        ],
        "severity": "high",
    },

    # Certificate Pinning Services
    "certificate_transparency": {
        "language": "general",
        "patterns": [
            r"certificate-transparency",
            r"sct_list",
            r"expect_ct",
            r"ct_policy",
        ],
        "bypass": [
            "Disable CT verification",
            "Patch SCT validation",
            "Clear Expect-CT headers",
        ],
        "severity": "low",
    },
}


# Certificate hash patterns (pinned certificates)
CERT_PATTERNS = {
    "sha256_hash": r"[a-f0-9]{64}",
    "sha1_hash": r"[a-f0-9]{40}",
    "md5_hash": r"[a-f0-9]{32}",
    "base64_cert": r"[A-Za-z0-9+/]{100,}={0,2}",
}


def _detect_ssl_pinning_ida() -> dict[str, Any]:
    """Detect SSL pinning in IDA Pro."""
    if not IDA_AVAILABLE:
        return {"detected": [], "strings": [], "functions": []}

    results = {
        "detected": [],
        "strings": [],
        "functions": [],
        "frameworks": [],
    }

    # Search for SSL pinning strings
    for seg_ea in idautils.Segments():
        seg_name = idc.get_segm_name(seg_ea)
        if not seg_name.startswith((".data", ".rdata", "DATA")):
            continue

        for str_ea in idautils.Strings(seg_ea):
            string = str(str_ea).lower()

            # Check for SSL/TLS related strings
            ssl_keywords = [
                "ssl", "tls", "certificate", "pinning", "trustmanager",
                "x509", "certificatepinner", "afsecuritypolicy",
            ]

            for keyword in ssl_keywords:
                if keyword in string:
                    results["strings"].append({
                        "address": str_ea,
                        "value": string.strip(),
                        "keyword": keyword,
                    })
                    break

    # Search for SSL pinning patterns in functions
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Check function name for SSL-related patterns
        for pattern_name, pattern_info in SSL_PINNING_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, func_name, re.IGNORECASE):
                    if pattern_name not in results["frameworks"]:
                        results["frameworks"].append(pattern_name)
                    results["functions"].append({
                        "address": func_ea,
                        "name": func_name,
                        "framework": pattern_name,
                        "language": pattern_info["language"],
                    })
                    break

        # Get function pseudocode/disassembly for pattern matching
        try:
            func_text = ""
            func = idaapi.get_func(func_ea)
            func_end = func.end_ea if func else func_ea
            for instr_ea in idautils.Heads(func_ea, func_end):
                disasm = get_disasm_text(instr_ea)
                if disasm:
                    func_text += disasm.lower() + "\n"

            for pattern_name, pattern_info in SSL_PINNING_PATTERNS.items():
                for pattern in pattern_info["patterns"]:
                    if re.search(pattern, func_text, re.IGNORECASE):
                        if pattern_name not in results["frameworks"]:
                            results["frameworks"].append(pattern_name)
                        results["detected"].append({
                            "address": func_ea,
                            "function": func_name,
                            "framework": pattern_name,
                            "pattern": pattern,
                        })
                        break
        except Exception:
            pass

    return results


def _detect_ssl_pinning_binja(bv) -> dict[str, Any]:
    """Detect SSL pinning in Binary Ninja."""
    if not BINJA_AVAILABLE:
        return {"detected": [], "strings": [], "functions": []}

    results = {
        "detected": [],
        "strings": [],
        "functions": [],
        "frameworks": [],
    }

    # Search for SSL-related strings
    for string in bv.get_strings():
        value = string.value.lower()

        ssl_keywords = [
            "ssl", "tls", "certificate", "pinning", "trustmanager",
            "x509", "certificatepinner", "afsecuritypolicy",
        ]

        for keyword in ssl_keywords:
            if keyword in value:
                results["strings"].append({
                    "address": hex(string.start),
                    "value": value,
                    "keyword": keyword,
                })
                break

    # Search for SSL pinning patterns in functions
    for func in bv.functions:
        func_name_lower = func.name.lower()

        for pattern_name, pattern_info in SSL_PINNING_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, func_name_lower, re.IGNORECASE):
                    if pattern_name not in results["frameworks"]:
                        results["frameworks"].append(pattern_name)
                    results["functions"].append({
                        "address": hex(func.start),
                        "name": func.name,
                        "framework": pattern_name,
                        "language": pattern_info["language"],
                    })
                    break

        # Check in disassembly
        func_text = "\n".join(str(instr) for instr in func.instructions).lower()

        for pattern_name, pattern_info in SSL_PINNING_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, func_text, re.IGNORECASE):
                    if pattern_name not in results["frameworks"]:
                        results["frameworks"].append(pattern_name)
                    results["detected"].append({
                        "address": hex(func.start),
                        "function": func.name,
                        "framework": pattern_name,
                        "pattern": pattern,
                    })
                    break

    return results


def get_bypass_techniques(frameworks: list[str]) -> dict[str, Any]:
    """Get bypass techniques for detected SSL pinning frameworks.

    Args:
        frameworks: List of detected framework names

    Returns:
        Dict with bypass techniques grouped by method
    """
    techniques = {
        "frida": [],
        "objection": [],
        "patch": [],
        "config": [],
        "hook": [],
    }

    for framework in frameworks:
        info = SSL_PINNING_PATTERNS.get(framework, {})
        language = info.get("language", "unknown")
        bypass_list = info.get("bypass", [])

        for bypass in bypass_list:
            bypass_lower = bypass.lower()

            if "frida" in bypass_lower:
                techniques["frida"].append({
                    "framework": framework,
                    "language": language,
                    "technique": bypass,
                })
            elif "objection" in bypass_lower:
                techniques["objection"].append({
                    "framework": framework,
                    "language": language,
                    "technique": bypass,
                })
            elif "hook" in bypass_lower:
                techniques["hook"].append({
                    "framework": framework,
                    "language": language,
                    "technique": bypass,
                })
            elif "modify" in bypass_lower or "patch" in bypass_lower:
                techniques["patch"].append({
                    "framework": framework,
                    "language": language,
                    "technique": bypass,
                })
            elif "config" in bypass_lower or "xml" in bypass_lower:
                techniques["config"].append({
                    "framework": framework,
                    "language": language,
                    "technique": bypass,
                })

    return techniques


def format_ssl_pinning_report(results: dict[str, Any]) -> str:
    """Format SSL pinning detection results as markdown report."""
    report_lines = ["## SSL Pinning Detection Report\n"]

    # Summary
    frameworks = results.get("frameworks", [])
    report_lines.append(f"**Detected Frameworks:** {len(frameworks)}\n")

    if frameworks:
        report_lines.append("**Frameworks Found:**\n")
        for fw in frameworks:
            info = SSL_PINNING_PATTERNS.get(fw, {})
            severity = info.get("severity", "unknown")
            language = info.get("language", "unknown")
            severity_icon = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}.get(severity, "[?]")
            report_lines.append(f"- {severity_icon} **{fw}** ({language})\n")
    else:
        report_lines.append("*No SSL pinning frameworks detected*\n")

    # Functions
    if results.get("functions"):
        report_lines.append("\n### SSL Pinning Functions\n")
        for func in results["functions"][:15]:
            report_lines.append(
                f"- **{func['name']}** at `{func['address']}`\n"
                f"  - Framework: {func['framework']} ({func['language']})\n"
            )

    # Strings
    if results.get("strings"):
        report_lines.append("\n### SSL-Related Strings\n")
        for string in results["strings"][:20]:
            report_lines.append(f"- `{string['value'][:80]}` at `{string['address']}`\n")

    # Bypass techniques
    if frameworks:
        techniques = get_bypass_techniques(frameworks)
        report_lines.append("\n### Bypass Techniques\n")

        if techniques["frida"]:
            report_lines.append("\n#### Frida Scripts\n")
            for tech in techniques["frida"][:5]:
                report_lines.append(f"- **{tech['framework']}** ({tech['language']}): {tech['technique']}\n")

        if techniques["objection"]:
            report_lines.append("\n#### Objection Commands\n")
            for tech in techniques["objection"]:
                report_lines.append(f"- **{tech['framework']}**: `{tech['technique']}`\n")

        if techniques["patch"]:
            report_lines.append("\n#### Patch Techniques\n")
            for tech in techniques["patch"][:5]:
                report_lines.append(f"- **{tech['framework']}**: {tech['technique']}\n")

        if techniques["hook"]:
            report_lines.append("\n#### Hook Points\n")
            for tech in techniques["hook"][:5]:
                report_lines.append(f"- **{tech['framework']}**: {tech['technique']}\n")

    # Recommendations
    report_lines.append("\n### Recommendations\n")

    if frameworks:
        report_lines.append("**SSL Pinning Detected** - Use appropriate bypass method:\n\n")

        high_severity = [fw for fw in frameworks if SSL_PINNING_PATTERNS.get(fw, {}).get("severity") == "high"]
        if high_severity:
            report_lines.append(f"⚠️ **High severity pinning**: {', '.join(high_severity)}\n")
            report_lines.append("- Use Frida with SSL pinning bypass scripts\n")
            report_lines.append("- Consider memory patching at runtime\n")
            report_lines.append("- Root/jailbreak detection may be present\n\n")

        # Common Frida scripts
        report_lines.append("**Common Frida Commands:**\n")
        report_lines.append("```javascript\n")
        report_lines.append("// Universal Android SSL pinning bypass\n")
        report_lines.append("frida -U -l frida-ssl-unpinning.js -f com.app.package\n\n")
        report_lines.append("// iOS SSL pinning bypass\n")
        report_lines.append("objection --gadget com.app.package explore\n")
        report_lines.append("ios sslpinning disable\n")
        report_lines.append("```\n")
    else:
        report_lines.append("*No SSL pinning detected - TLS traffic can be intercepted freely*\n")

    return "\n".join(report_lines)


def detect_ssl_pinning(binary_view=None) -> str:
    """Main entry point for SSL pinning detection.

    Args:
        binary_view: Binary Ninja BinaryView object (optional)

    Returns:
        Formatted markdown report
    """
    if IDA_AVAILABLE:
        results = _detect_ssl_pinning_ida()
    elif BINJA_AVAILABLE and binary_view:
        results = _detect_ssl_pinning_binja(binary_view)
    else:
        return "Error: Neither IDA Pro nor Binary Ninja API is available"

    return format_ssl_pinning_report(results)


if __name__ == "__main__":
    print(detect_ssl_pinning())

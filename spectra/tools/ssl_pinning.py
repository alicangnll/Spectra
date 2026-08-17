"""SSL Pinning detection and bypass analysis tool.

Detects SSL certificate pinning through structural analysis of the binary —
import tables, cross-references to verification entry points, symbols
defined inside the binary, and embedded pin material (pin hashes, PEM
certificates). Source-level framework patterns are never matched against
disassembly text; every finding is backed by a concrete address.

Provides bypass techniques for Android, iOS, and various frameworks.
"""

from __future__ import annotations

import re
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idautils
    import idc

    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Try to import Binary Ninja API
try:
    import binaryninja  # noqa: F401 — availability probe

    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Bypass technique catalog (keyed by framework name used in detection)
# ---------------------------------------------------------------------------

SSL_PINNING_PATTERNS = {
    # Android
    "okhttp": {
        "language": "android",
        "patterns": [r"certificatePinner"],
        "bypass": [
            "Hook OkHttpClient.Builder",
            "Modify certificatePinner to return empty",
            "Use Frida: sslpinnerfrida",
        ],
        "severity": "medium",
    },
    "network_security_config": {
        "language": "android",
        "patterns": [r"network_security_config"],
        "bypass": [
            "Modify network_security_config.xml",
            'Add <base-config cleartextTrafficPermitted="true">',
            "Disable certificate validation",
        ],
        "severity": "low",
    },
    "trust_manager": {
        "language": "android",
        "patterns": [r"checkServerTrusted"],
        "bypass": [
            "Hook X509TrustManager.checkServerTrusted",
            "Return empty array for getAcceptedIssuers",
            "Implement custom TrustManager that accepts all",
        ],
        "severity": "high",
    },
    # iOS / macOS native
    "sectrust": {
        "language": "ios",
        "patterns": [r"SecTrustSetAnchorCertificates"],
        "bypass": [
            "Hook SecTrustEvaluateWithError to return true",
            "Hook SecTrustSetAnchorCertificates to a no-op",
            "Use Frida: SSL-Kill-Swift / ios-ssl-kill-switch",
        ],
        "severity": "high",
    },
    "ns_url_session": {
        "language": "ios",
        "patterns": [r"didReceiveChallenge"],
        "bypass": [
            "Hook NSURLSessionDelegate",
            "Implement URLAuthenticationChallenge sender to use credential=None",
            "Use Frida: ios-ssl-kill-switch",
            "Use objection: ios sslpinning disable",
        ],
        "severity": "medium",
    },
    # Cross-platform / desktop
    "curl": {
        "language": "cpp",
        "patterns": [r"CURLOPT_SSL_VERIFYPEER"],
        "bypass": [
            "Patch CURLOPT_SSL_VERIFYPEER to 0",
            "Patch CURLOPT_SSL_VERIFYHOST to 0",
            "Hook libcurl SSL verification",
        ],
        "severity": "low",
    },
    "openssl": {
        "language": "cpp",
        "patterns": [r"SSL_CTX_set_verify"],
        "bypass": [
            "Hook SSL_CTX_set_verify with SSL_VERIFY_NONE",
            "Hook X509_verify_cert to always return 1",
            "Hook BoringSSL SSL_CTX_set_custom_verify callback to ssl_verify_ok",
            "Use LD_PRELOAD with custom libssl",
        ],
        "severity": "high",
    },
    "winhttp": {
        "language": "windows",
        "patterns": [r"WinHttpSetOption"],
        "bypass": [
            "Hook WinHttpSetOption",
            "Clear SECURITY_FLAG_STRICT flags",
            "Patch certificate validation in winhttp",
        ],
        "severity": "medium",
    },
    "schannel": {
        "language": "windows",
        "patterns": [r"CertVerifyCertificateChainPolicy"],
        "bypass": [
            "Hook CertVerifyCertificateChainPolicy",
            "Always return CERT_E_UNTRUSTEDROOT or success",
            "Patch schannel.dll",
        ],
        "severity": "high",
    },
}


# ---------------------------------------------------------------------------
# Structural detection tables
# ---------------------------------------------------------------------------

# Symbols whose import means the binary drives TLS verification itself.
# Mapped to the framework bucket used by the bypass catalog above.
VERIFY_IMPORTS: dict[str, tuple[str, ...]] = {
    # OpenSSL / BoringSSL / LibreSSL share these entry points.
    # SSL_CTX_set_custom_verify (BoringSSL) and an explicit verify callback
    # are how native pinning is implemented on Android NDK.
    "openssl": (
        "SSL_CTX_set_verify",
        "SSL_set_verify",
        "SSL_CTX_set_custom_verify",
        "SSL_get_verify_result",
        "X509_check_host",
        "X509_check_purpose",
        "SSL_set_custom_verify",
    ),
    "sectrust": (
        "SecTrustSetAnchorCertificates",
        "SecTrustEvaluate",
        "SecTrustEvaluateWithError",
        "SecTrustSetAnchorCertificatesOnly",
    ),
    "schannel": (
        "CertVerifyCertificateChainPolicy",
        "CertGetCertificateChain",
        "WinVerifyTrust",
    ),
    "winhttp": ("WinHttpSetOption",),
    "curl": ("curl_easy_setopt",),
}

# Verification symbols that specifically indicate pinning-style logic
# (custom callbacks / anchor pinning), not just default TLS usage.
_PINNING_SPECIFIC_SYMBOLS = frozenset(
    {
        "SSL_CTX_set_verify",
        "SSL_set_verify",
        "SSL_CTX_set_custom_verify",
        "SSL_set_custom_verify",
        "X509_check_host",
        "SecTrustSetAnchorCertificates",
        "SecTrustSetAnchorCertificatesOnly",
        "CertVerifyCertificateChainPolicy",
        "WinHttpSetOption",
    }
)

# Trust-manager / pinning logic implemented *inside* this binary (JNI
# exports, bundled pinning libraries) — matched against the binary's own
# symbols, not against any source-level pattern.
NATIVE_TRUST_SYMBOLS: tuple[str, ...] = (
    "checkservertrusted",
    "checkclienttrusted",
    "getacceptedissuers",
    "x509trustmanager",
    "trustmanagerimpl",
    "trustmanagerextensions",
    "sslpinning",
    "certificatepinner",
    "okhostnameverify",
    "hostnameverify",
    "certpin",
    "verifypin",
    "pincertificate",
    "pinnedpublickey",
)

# Embedded pin material. These string shapes are how pinned certificates
# and key hashes are shipped inside binaries.
_OKHTTP_PIN_PREFIXES = ("sha256/", "sha1/")  # CertificatePinner.pin(...) format
_PEM_MARKER = "BEGIN CERTIFICATE"
_HPKP_PREFIX = "pin-sha256"  # HPKP header-style pin list
_HEX_PIN_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")  # raw sha1/sha256 key hash

# Low-weight TLS strings used only for corroboration.
_SSL_STRING_KEYWORDS = (
    "ssl",
    "tls",
    "x509",
    "certificate",
    "trustmanager",
    "certificatepinner",
    "networksecurityconfig",
    "network_security_config",
)


def _classify_string(value: str) -> dict[str, str] | None:
    """Classify a string as embedded pin material, or None if irrelevant."""
    v = value.strip()
    if not v or len(v) > 4096:
        return None

    if v.startswith(_OKHTTP_PIN_PREFIXES):
        # OkHttp pin format: sha256/<base64 hash>
        rest = v.split("/", 1)[1]
        if re.fullmatch(r"[A-Za-z0-9+/]{32,44}={0,2}", rest):
            return {"kind": "pin_material", "detail": "OkHttp CertificatePinner pin", "framework": "okhttp"}

    if _PEM_MARKER in v:
        return {"kind": "pin_material", "detail": "embedded PEM certificate", "framework": ""}

    if _HPKP_PREFIX in v.lower():
        return {"kind": "pin_material", "detail": "HPKP pin list (pin-sha256)", "framework": ""}

    if _HEX_PIN_RE.fullmatch(v.lower()):
        return {"kind": "possible_pin", "detail": "40/64-hex string (possible pinned key hash)", "framework": ""}

    return None


def _match_verify_import(symbol: str) -> str | None:
    """Return the framework bucket for a verification-related import."""
    # Mach-O prefixes C symbols with "_"; ELF versions use "@"/"$" suffixes.
    stripped = symbol.lstrip("_")
    for framework, names in VERIFY_IMPORTS.items():
        for base in names:
            if stripped == base or stripped.startswith(base + "@") or stripped.startswith(base + "$"):
                return framework
    return None


def _base_symbol(symbol: str) -> str:
    """Normalize a symbol to its unversioned, un-prefixed base name."""
    return symbol.split("@")[0].split("$")[0].lstrip("_")


def _is_native_trust_symbol(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in NATIVE_TRUST_SYMBOLS)


def analyze_pinning_facts(
    imports: list[dict[str, Any]],
    defined_names: list[dict[str, Any]],
    strings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive an SSL-pinning verdict from raw structural facts.

    Pure analysis — no disassembler API involved — so it is directly
    testable. Each collector (IDA, Binary Ninja) gathers:

    - imports: [{"address", "symbol", "callers": [{"address", "name"}]}]
    - defined_names: [{"address", "name"}] — symbols defined in this binary
    - strings: [{"address", "value"}]

    Returns a report dict with a confidence-backed verdict, concrete
    evidence, and hook/patch targets.
    """
    findings: list[dict[str, Any]] = []
    frameworks: list[str] = []
    hook_targets: list[dict[str, Any]] = []
    seen_targets: set[int | str] = set()

    def _add_framework(name: str) -> None:
        if name and name not in frameworks:
            frameworks.append(name)

    def _add_hook_target(addr: int | str, name: str, reason: str) -> None:
        key = addr if not isinstance(addr, str) else name
        if key in seen_targets:
            return
        seen_targets.add(key)
        hook_targets.append({"address": addr, "name": name, "reason": reason})

    # 1. Imported verification entry points and their in-binary callers.
    weak_verify_present = False
    strong_verify_with_caller = False
    curl_import_present = False
    for entry in imports:
        symbol = entry.get("symbol", "")
        framework = _match_verify_import(symbol)
        if framework is None:
            continue

        callers = entry.get("callers", [])
        is_pinning_specific = _base_symbol(symbol) in _PINNING_SPECIFIC_SYMBOLS

        if callers:
            if is_pinning_specific:
                strong_verify_with_caller = True
            else:
                weak_verify_present = True
        elif is_pinning_specific:
            weak_verify_present = True

        if framework == "curl":
            curl_import_present = True
            if not callers:
                # curl_easy_setopt alone is ordinary HTTP usage — only keep
                # it when corroborated by TLS strings (handled below).
                continue

        _add_framework(framework)
        findings.append(
            {
                "kind": "verify_import",
                "framework": framework,
                "symbol": symbol,
                "address": entry.get("address"),
                "callers": callers,
                "pinning_specific": is_pinning_specific,
            }
        )
        for caller in callers:
            _add_hook_target(caller["address"], caller.get("name", ""), f"calls {symbol}")

    # 2. Trust-manager / pinning logic defined inside this binary.
    # (j_ names are JNI exports in IDA — exactly the trust managers we want;
    # only IDA's auto-generated names are skipped.)
    for entry in defined_names:
        name = entry.get("name", "")
        if not name or name.startswith(("sub_", "loc_", "unk_", "off_", "def_")):
            continue
        if _is_native_trust_symbol(name):
            _add_framework("trust_manager")
            findings.append(
                {
                    "kind": "native_trust_symbol",
                    "framework": "trust_manager",
                    "symbol": name,
                    "address": entry.get("address"),
                }
            )
            _add_hook_target(entry.get("address", ""), name, "trust-manager implementation in binary")

    # 3. Embedded pin material and TLS-adjacent strings.
    pin_material_found = False
    possible_pin_found = False
    nsc_string_found = False
    ssl_strings: list[dict[str, Any]] = []
    for entry in strings:
        value = entry.get("value", "")
        lowered = value.lower()
        classified = _classify_string(value)
        if classified is not None:
            if classified["kind"] == "pin_material":
                pin_material_found = True
            else:
                possible_pin_found = True
            _add_framework(classified["framework"])
            findings.append(
                {
                    "kind": classified["kind"],
                    "detail": classified["detail"],
                    "value": value[:100],
                    "address": entry.get("address"),
                }
            )
        else:
            if "network_security_config" in lowered:
                nsc_string_found = True
            if any(kw in lowered for kw in _SSL_STRING_KEYWORDS):
                ssl_strings.append({"value": value[:100], "address": entry.get("address")})

    # A bare curl import counts only when TLS strings corroborate it.
    if curl_import_present and ssl_strings:
        _add_framework("curl")
    if nsc_string_found:
        _add_framework("network_security_config")

    # 4. Verdict.
    if pin_material_found or any(f["kind"] == "native_trust_symbol" for f in findings) or strong_verify_with_caller:
        confidence = "high"
        detected = True
    elif weak_verify_present or possible_pin_found:
        confidence = "medium"
        detected = True
    elif frameworks:
        confidence = "low"
        detected = bool(ssl_strings)
    else:
        confidence = "none"
        detected = False

    return {
        "detected": detected,
        "confidence": confidence,
        "frameworks": frameworks,
        "findings": findings,
        "hook_targets": hook_targets[:15],
        "strings": ssl_strings[:20],
        "functions": [f for f in findings if f["kind"] in ("verify_import", "native_trust_symbol")],
    }


# ---------------------------------------------------------------------------
# IDA collector
# ---------------------------------------------------------------------------


def _collect_facts_ida() -> dict[str, list[dict[str, Any]]]:
    """Gather structural facts from the IDA database."""
    imports: list[dict[str, Any]] = []
    defined_names: list[dict[str, Any]] = []
    strings: list[dict[str, Any]] = []

    # All named locations: imports, exports, library thunks.
    for ea, name in idautils.Names():
        framework = _match_verify_import(name)
        if framework is not None:
            callers = []
            seen: set[int] = set()
            try:
                for ref in idautils.XrefsTo(ea, 0):
                    func = idaapi.get_func(ref.frm)
                    if func and func.start_ea not in seen:
                        seen.add(func.start_ea)
                        callers.append(
                            {"address": func.start_ea, "name": idc.get_func_name(func.start_ea)}
                        )
            except Exception:
                pass
            imports.append({"address": ea, "symbol": name, "callers": callers})
        else:
            defined_names.append({"address": ea, "name": name})

    for s in idautils.Strings():
        try:
            strings.append({"address": s.ea, "value": str(s)})
        except Exception:
            continue

    return {"imports": imports, "defined_names": defined_names, "strings": strings}


# ---------------------------------------------------------------------------
# Binary Ninja collector
# ---------------------------------------------------------------------------


def _collect_facts_binja(bv) -> dict[str, list[dict[str, Any]]]:
    """Gather structural facts from a Binary Ninja BinaryView."""
    imports: list[dict[str, Any]] = []
    defined_names: list[dict[str, Any]] = []
    strings: list[dict[str, Any]] = []

    symbols: list[Any] = []
    try:
        for value in (bv.symbols or {}).values():
            if isinstance(value, (list, tuple)):
                symbols.extend(value)
            else:
                symbols.append(value)
    except Exception:
        symbols = []

    seen_addresses: set[int] = set()
    for sym in symbols:
        try:
            name = str(sym.short_name if hasattr(sym, "short_name") else sym)
            raw_name = getattr(sym, "raw_name", None) or name
            addr = int(sym.address)
        except Exception:
            continue

        framework = _match_verify_import(raw_name) or _match_verify_import(name)
        if framework is not None:
            if addr in seen_addresses:
                continue
            seen_addresses.add(addr)
            callers = []
            try:
                for ref in bv.get_code_refs(addr):
                    fn = ref.function
                    if fn is not None:
                        callers.append({"address": int(fn.start), "name": fn.name})
            except Exception:
                pass
            imports.append({"address": addr, "symbol": raw_name, "callers": callers})
        else:
            defined_names.append({"address": addr, "name": raw_name})

    try:
        for fn in bv.functions:
            defined_names.append({"address": int(fn.start), "name": fn.name})
    except Exception:
        pass

    try:
        for s in bv.get_strings():
            strings.append({"address": int(s.start), "value": s.value})
    except Exception:
        pass

    return {"imports": imports, "defined_names": defined_names, "strings": strings}


# ---------------------------------------------------------------------------
# Detection entry points
# ---------------------------------------------------------------------------


def _detect_ssl_pinning_ida() -> dict[str, Any]:
    """Detect SSL pinning in IDA Pro via structural analysis."""
    if not IDA_AVAILABLE:
        return {
            "detected": False,
            "confidence": "none",
            "frameworks": [],
            "findings": [],
            "hook_targets": [],
            "strings": [],
            "functions": [],
        }
    facts = _collect_facts_ida()
    return analyze_pinning_facts(facts["imports"], facts["defined_names"], facts["strings"])


def _detect_ssl_pinning_binja(bv) -> dict[str, Any]:
    """Detect SSL pinning in Binary Ninja via structural analysis."""
    if not BINJA_AVAILABLE:
        return {
            "detected": False,
            "confidence": "none",
            "frameworks": [],
            "findings": [],
            "hook_targets": [],
            "strings": [],
            "functions": [],
        }
    facts = _collect_facts_binja(bv)
    return analyze_pinning_facts(facts["imports"], facts["defined_names"], facts["strings"])


def get_bypass_techniques(frameworks: list[str]) -> dict[str, Any]:
    """Get bypass techniques for detected SSL pinning frameworks.

    Args:
        frameworks: List of detected framework names

    Returns:
        Dict with bypass techniques grouped by method
    """
    techniques: dict[str, Any] = {
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
                techniques["frida"].append(
                    {"framework": framework, "language": language, "technique": bypass}
                )
            elif "objection" in bypass_lower:
                techniques["objection"].append(
                    {"framework": framework, "language": language, "technique": bypass}
                )
            elif "hook" in bypass_lower:
                techniques["hook"].append(
                    {"framework": framework, "language": language, "technique": bypass}
                )
            elif "modify" in bypass_lower or "patch" in bypass_lower:
                techniques["patch"].append(
                    {"framework": framework, "language": language, "technique": bypass}
                )
            elif "config" in bypass_lower or "xml" in bypass_lower:
                techniques["config"].append(
                    {"framework": framework, "language": language, "technique": bypass}
                )

    return techniques


_CONFIDENCE_ICONS = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]", "none": "[--]"}


def format_ssl_pinning_report(results: dict[str, Any]) -> str:
    """Format SSL pinning detection results as markdown report."""
    lines = ["## SSL Pinning Detection Report\n"]

    confidence = results.get("confidence", "none")
    frameworks = results.get("frameworks", [])
    findings = results.get("findings", [])

    lines.append(f"**Verdict:** {'Pinning likely' if results.get('detected') else 'No pinning evidence'}")
    lines.append(f"**Confidence:** {_CONFIDENCE_ICONS.get(confidence, '[?]')} {confidence}\n")

    if frameworks:
        lines.append("**Frameworks:** " + ", ".join(frameworks) + "\n")
    else:
        lines.append("*No TLS verification frameworks identified*\n")

    # Evidence with concrete addresses
    if findings:
        lines.append("### Evidence\n")
        for f in findings[:20]:
            addr = f.get("address")
            addr_txt = hex(addr) if isinstance(addr, int) else (str(addr) if addr else "?")
            if f["kind"] == "verify_import":
                callers = f.get("callers", [])
                caller_txt = f"{len(callers)} caller(s)" if callers else "no in-binary callers"
                flag = "pinning-specific" if f.get("pinning_specific") else "generic verification"
                lines.append(
                    f"- `{addr_txt}` import **{f['symbol']}** ({f['framework']}, {flag}, {caller_txt})"
                )
                for caller in callers[:3]:
                    caddr = caller["address"]
                    caddr_txt = hex(caddr) if isinstance(caddr, int) else str(caddr)
                    lines.append(f"  - called by `{caddr_txt}` {caller.get('name', '')}")
            elif f["kind"] == "native_trust_symbol":
                lines.append(f"- `{addr_txt}` symbol **{f['symbol']}** — trust-manager logic in this binary")
            elif f["kind"] in ("pin_material", "possible_pin"):
                lines.append(f"- `{addr_txt}` {f['detail']}: `{f.get('value', '')}`")
        lines.append("")

    # Hook / patch targets
    hook_targets = results.get("hook_targets", [])
    if hook_targets:
        lines.append("### Hook / Patch Targets\n")
        for t in hook_targets:
            addr = t["address"]
            addr_txt = hex(addr) if isinstance(addr, int) else str(addr)
            lines.append(f"- `{addr_txt}` **{t['name']}** — {t['reason']}")
        lines.append("")

    # Corroborating strings
    if results.get("strings"):
        lines.append("### TLS-Related Strings\n")
        for string in results["strings"]:
            lines.append(f"- `{string['value']}` at `{string['address']}`")
        lines.append("")

    # Bypass techniques
    if frameworks:
        techniques = get_bypass_techniques(frameworks)
        lines.append("### Bypass Techniques\n")

        if techniques["frida"]:
            lines.append("**Frida Scripts:**")
            for tech in techniques["frida"][:5]:
                lines.append(f"- **{tech['framework']}** ({tech['language']}): {tech['technique']}")
            lines.append("")

        if techniques["objection"]:
            lines.append("**Objection Commands:**")
            for tech in techniques["objection"]:
                lines.append(f"- **{tech['framework']}**: `{tech['technique']}`")
            lines.append("")

        if techniques["hook"]:
            lines.append("**Hook Points:**")
            for tech in techniques["hook"][:5]:
                lines.append(f"- **{tech['framework']}**: {tech['technique']}")
            lines.append("")

        if techniques["patch"]:
            lines.append("**Patch Techniques:**")
            for tech in techniques["patch"][:5]:
                lines.append(f"- **{tech['framework']}**: {tech['technique']}")
            lines.append("")

    # Recommendations
    lines.append("### Recommendations\n")
    if results.get("detected"):
        if confidence == "high":
            lines.append("- Strong pinning evidence — hook the targets above or use framework-specific bypass")
        else:
            lines.append("- Verify manually: inspect the hook targets and TLS call sites before patching")
        lines.append("- Runtime hooks (Frida/objection) are safer than binary patches on signed apps")
    else:
        lines.append("- No pinning evidence found — TLS interception should work with a proxy CA installed")

    return "\n".join(lines)


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

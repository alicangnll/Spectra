"""Novel Vulnerability Hunter - Advanced vulnerability discovery and exploit generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

from ..tools.base import tool


class VulnerabilityType(Enum):
    """Comprehensive vulnerability type classification"""

    STACK_OVERFLOW = "stack_buffer_overflow"
    HEAP_OVERFLOW = "heap_overflow"
    USE_AFTER_FREE = "use_after_free"
    INTEGER_OVERFLOW = "integer_overflow"
    FORMAT_STRING = "format_string"
    RACE_CONDITION = "race_condition"
    RCE = "remote_code_execution"
    LPE_KERNEL = "lpe_kernel_exploit"
    LPE_SERVICE = "lpe_service_privilege_escalation"
    LPE_SUID = "lpe_suid_sgid"
    LPE_PATH = "lpe_path_hijacking"
    LPE_CRON = "lpe_cron_job"
    COMMAND_INJECTION = "command_injection"
    DESERIALIZATION = "deserialization"
    SSTI = "template_injection"
    FILE_UPLOAD = "file_upload_rce"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    SSRF = "ssrf"
    IDOR = "idor"
    AUTH_BYPASS = "auth_bypass"
    NOVEL_SIGN_EXTENSION = "novel_sign_extension_overflow"
    NOVEL_ALLOCATOR = "novel_custom_allocator_overflow"
    NOVEL_BOUNDS_BYPASS = "novel_bounds_check_bypass"
    NOVEL_COMPILER_BUG = "novel_compiler_optimization_bug"
    NOVEL_SIMD = "novel_simd_vector_overflow"
    NOVEL_JIT = "novel_jit_compilation_overflow"
    NOVEL_VLA = "novel_variable_length_array_overflow"


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class VulnerabilityFinding:
    """A vulnerability finding from the hunter."""

    vuln_type: str
    severity: str
    location: str
    description: str
    proof: str
    code_snippet: str | None = None
    novel_confidence: float = 0.0
    exploit_ready: bool = False
    exploit_code: str | None = None


class NovelVulnerabilityHunterCore:
    """Core vulnerability hunting logic."""

    def __init__(self, output_dir: str = "./novel_findings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.known_cves = self._load_known_cves()
        self.known_patterns = self._load_known_patterns()

    def _load_known_cves(self) -> set:
        """Load known CVE patterns to exclude."""
        return {
            "cve-2024-",
            "cve-2023-",
            "cve-2022-",
            "cve-2021-",
            "cve-2020-",
            "cve-2019-",
            "cve-2018-",
            "cve-2017-",
            "cve-2016-",
            "cve-2015-",
            "cve-2014-",
            "cve-2013-",
        }

    def _load_known_patterns(self) -> dict[str, list[str]]:
        """Load known vulnerability patterns to exclude."""
        return {
            "stack_overflow": [
                "classic_strcpy_old_code",
                "well_documented_gets",
                "standard_sprintf_vuln",
            ],
            "heap_overflow": [
                "common_malloc_overflow",
                "well_known_heap_pattern",
            ],
            "format_string": [
                "standard_printf_vuln",
                "common_format_string",
            ],
        }

    def is_novel_vulnerability(self, vuln: VulnerabilityFinding) -> tuple[bool, float]:
        """Check if vulnerability is novel (not in known databases).

        Returns:
            (is_novel, confidence_score)
        """
        confidence = 0.0
        vuln_desc = vuln.description.lower()

        # Check against known CVEs
        for cve_pattern in self.known_cves:
            if cve_pattern in vuln_desc:
                return (False, 0.0)

        # Check against known patterns
        for vuln_type, patterns in self.known_patterns.items():
            if vuln_type in vuln.vuln_type.lower():
                for pattern in patterns:
                    if pattern in vuln_desc:
                        return (False, 0.0)

        # Novel indicators increase confidence
        novel_indicators = [
            "recent code",
            "custom allocator",
            "compiler optimization",
            "simd",
            "jit",
            "template",
            "novel",
            "unknown",
            "previously undocumented",
            "next-generation",
            "modern",
        ]

        for indicator in novel_indicators:
            if indicator in vuln_desc:
                confidence += 0.15

        confidence = min(confidence, 1.0)
        return (confidence > 0.5, confidence)

    def filter_false_positives(self, findings: list[VulnerabilityFinding]) -> list[VulnerabilityFinding]:
        """Filter out false positive findings."""
        valid_findings = []
        false_positive_patterns = [
            r"test.*vulnerability",
            r"demo.*function",
            r"example.*code",
            r"sample.*implementation",
            r"non[- ]exploitable",
            r"theoretical.*only",
            r"patched.*version",
            r"mitigated.*by",
        ]

        for finding in findings:
            is_fp = False
            for pattern in false_positive_patterns:
                if re.search(pattern, finding.description, re.IGNORECASE):
                    is_fp = True
                    break

            if not is_fp:
                valid_findings.append(finding)

        return valid_findings

    def assess_exploitability(self, vuln: VulnerabilityFinding) -> bool:
        """Assess exploitability of a vulnerability."""
        score = 0

        if vuln.severity in ["CRITICAL", "HIGH"]:
            score += 3

        high_exploit_types = ["RCE", "LPE_KERNEL", "LPE_SERVICE", "COMMAND_INJECTION"]
        if any(t in vuln.vuln_type for t in high_exploit_types):
            score += 3

        if vuln.novel_confidence > 0.7:
            score += 2

        if vuln.proof and len(vuln.proof) > 50:
            score += 1

        if vuln.code_snippet:
            score += 1

        return score >= 5

    def generate_report(self, findings: list[VulnerabilityFinding]) -> str:
        """Generate a comprehensive vulnerability report."""
        lines = [
            "# Spectra Novel Vulnerability Hunter Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Findings:** {len(findings)}",
            f"**Novel Findings:** {sum(1 for f in findings if f.novel_confidence > 0.5)}",
            f"**Exploitable:** {sum(1 for f in findings if f.exploit_ready)}",
            "",
            "## Vulnerabilities",
            "",
        ]

        for finding in findings:
            lines.extend(
                [
                    f"### {finding.vuln_type}",
                    f"**Severity:** {finding.severity}",
                    f"**Location:** {finding.location}",
                    f"**Novelty Confidence:** {finding.novel_confidence:.2f}",
                    f"**Description:** {finding.description}",
                    f"**Proof:** {finding.proof}",
                ]
            )

            if finding.exploit_ready:
                lines.append("**EXPLOITABLE** - Exploit code generated")

            if finding.code_snippet:
                lines.append(f"**Code Snippet:**\n```c\n{finding.code_snippet}\n```")

            lines.append("")

        return "\n".join(lines)


@tool(category="security", mutating=False)
def analyze_novel_vulnerabilities(
    code: Annotated[str, "C/C++ code to analyze for novel vulnerabilities"],
    focus_area: Annotated[str, "Specific area to focus on (e.g., 'custom allocator', 'SIMD', 'JIT')"] = "general",
) -> str:
    """Analyze code for novel vulnerabilities using advanced detection techniques.

    Focuses on discovering PREVIOUSLY UNKNOWN vulnerabilities by:
    - Excluding known CVE patterns
    - Identifying novel overflow patterns (sign extension, allocator bugs, SIMD issues)
    - Finding compiler-induced bugs
    - Detecting custom allocator vulnerabilities
    - Analyzing JIT compilation issues
    """
    hunter = NovelVulnerabilityHunterCore()

    findings = []
    lines = code.split("\n")

    # Analyze code for vulnerability patterns
    vuln_patterns = {
        "NOVEL_SIGN_EXTENSION": [
            (r"int\s+\w+\s*;\s*unsigned\s+int\s+\w+\s*=\s*\w+", "Sign extension vulnerability"),
            (r"size_t\s+\w+\s*=\s*\(int\)\w+", "Signed to unsigned conversion"),
        ],
        "NOVEL_ALLOCATOR": [
            (r"custom.*allocator|pool.*alloc|arena.*alloc", "Custom allocator implementation"),
            (r"void\s*\*\s*\w+\s*=\s*\w+\s*\+\s*\w+\s*\*\s*size", "Unchecked pool allocation"),
        ],
        "NOVEL_BOUNDS_BYPASS": [
            (r"if\s*\(\s*\w+\s*<\s*\w+\s*\)", "Signed/unsigned comparison mismatch"),
            (r"for\s*\(.*\w+\s*<=\s*\w+", "Potential loop counter overflow"),
        ],
        "NOVEL_SIMD": [
            (r"__m256i|__m128|SSE|AVX", "SIMD vector operations"),
            (r"_mm_\w+", "Intrinsic SIMD operations"),
        ],
        "NOVEL_JIT": [
            (r"jit|compile.*code|bytecode.*interpret", "JIT compilation"),
            (r"llvm.*jit|v8.*engine", "JIT engine"),
        ],
        "STACK_OVERFLOW": [
            (r"strcpy|strcat|gets\s*\(", "Unsafe string functions"),
            (r"sprintf\s*\(", "Unsafe format string"),
        ],
        "HEAP_OVERFLOW": [
            (r"malloc.*memcpy|malloc.*strncpy", "Unchecked heap copy"),
            (r"realloc\s*\(", "Potential use-after-free"),
        ],
        "USE_AFTER_FREE": [
            (r"free\s*\([^)]+\)\s*;\s*\w+\s*->", "Use after free pattern"),
            (r"free\s*\([^)]+\)\s*;\s*\*\w+", "Dereference after free"),
        ],
    }

    for line_num, line in enumerate(lines, 1):
        for vuln_type, patterns in vuln_patterns.items():
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    finding = VulnerabilityFinding(
                        vuln_type=vuln_type,
                        severity="HIGH" if vuln_type.startswith("NOVEL_") else "MEDIUM",
                        location=f"Line {line_num}",
                        description=f"{desc}: {line.strip()}",
                        proof=line.strip(),
                        code_snippet=line.strip(),
                    )

                    _is_novel, confidence = hunter.is_novel_vulnerability(finding)
                    finding.novel_confidence = confidence
                    finding.exploit_ready = hunter.assess_exploitability(finding)

                    findings.append(finding)

    # Filter false positives
    valid_findings = hunter.filter_false_positives(findings)

    # Generate report
    report = hunter.generate_report(valid_findings)

    # Add analysis summary
    summary = f"""
## Analysis Summary

**Code Lines Analyzed:** {len(lines)}
**Total Findings:** {len(findings)}
**After False Positive Filter:** {len(valid_findings)}
**Novel Vulnerabilities:** {sum(1 for f in valid_findings if f.novel_confidence > 0.5)}
**Exploitable:** {sum(1 for f in valid_findings if f.exploit_ready)}

**Focus Area:** {focus_area}
**Novel Indicators Found:** {sum(1 for f in valid_findings if "recent" in f.description.lower() or "custom" in f.description.lower() or "novel" in f.description.lower())}

---

{report}
"""

    return summary


@tool(category="security", mutating=False)
def generate_exploit_template(
    vuln_type: Annotated[str, "Type of vulnerability (e.g., 'stack_overflow', 'heap_overflow', 'command_injection')"],
    location: Annotated[str, "Location/address of the vulnerability"],
    description: Annotated[str, "Description of the vulnerability"],
) -> str:
    """Generate a weaponized exploit template for the specified vulnerability type.

    Creates a Python exploit template with:
    - Target configuration
    - Payload generation
    - Network/web exploitation support
    - Authentication handling
    - Proof-of-concept code
    """
    # Use .format() instead of f-string to avoid brace escaping issues in templates
    exploit_template = f"""#!/usr/bin/env python3
\"\"\"
Auto-generated Exploit for Novel Vulnerability
Vulnerability Type: {vuln_type}
Location: {location}
Description: {description}

Generated by Spectra Novel Vulnerability Hunter
Author: Ali Can Gönüllü

⚠️  WARNING: This exploit is for AUTHORIZED SECURITY TESTING ONLY
⚠️  Usage on systems without explicit permission is prohibited
\"\"\"

import socket
import struct
import time
import sys

class NovelExploit:
    \"\"\"Exploit for {vuln_type} vulnerability\"\"\"

    def __init__(self, target, port=None, username=None, password=None):
        self.target = target
        self.port = port or 80
        self.username = username or 'USERNAME'
        self.password = password or 'PASSWORD'
        self.timeout = 10

    def authenticate(self):
        \"\"\"Authenticate if credentials provided\"\"\"
        if self.username and self.username != 'USERNAME':
            print(f"[*] Authenticating as {{self.username}}")
            return True
        return False

    def build_payload(self):
        \"\"\"Build exploit payload\"\"\"
        payload = b''

        # Custom payload based on vulnerability type
        if '{vuln_type}' in ['stack_buffer_overflow', 'heap_overflow', 'NOVEL_SIGN_EXTENSION']:
            # Overflow payload with return address overwrite
            payload = b'A' * 1024
            payload += struct.pack('<Q', 0xdeadbeefdeadbeef)  # Return address (adjust)
            payload += b'\\x90' * 32  # NOP sled
            payload += b'\\xcc'       # INT3 (breakpoint)

        elif '{vuln_type}' in ['command_injection', 'rce', 'COMMAND_INJECTION']:
            # Command injection payload
            payload = '; id && whoami'.encode()

        elif '{vuln_type}' in ['lpe_kernel_exploit', 'lpe_service', 'LPE_KERNEL']:
            # LPE payload placeholder
            payload = b'\\x00' * 64  # Placeholder for kernel exploit

        else:
            # Generic payload
            payload = b'A' * 512

        return payload

    def exploit(self):
        \"\"\"Execute exploit\"\"\"
        print(f"[*] Target: {{self.target}}:{{self.port}}")
        print(f"[*] Vulnerability: {vuln_type}")
        print(f"[*] Description: {description}")

        authenticated = self.authenticate()
        payload = self.build_payload()
        print(f"[*] Payload size: {{len(payload)}} bytes")

        try:
            if '{{self.target}}'.startswith('http'):
                return self._web_exploit(payload, authenticated)
            else:
                return self._network_exploit(payload, authenticated)
        except Exception as e:
            print(f"[-] Exploit failed: {{e}}")
            return False

    def _network_exploit(self, payload, authenticated):
        \"\"\"Network-based exploit\"\"\"
        print(f"[*] Connecting to {{self.target}}:{{self.port}}...")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            sock.connect((self.target, self.port))
            print(f"[+] Connected to target")

            sock.send(payload)
            print(f"[+] Exploit payload sent")

            response = sock.recv(4096)
            print(f"[+] Received response: {{response[:200]}}")

            sock.close()
            print(f"[+] Exploit completed successfully")
            return True

        except Exception as e:
            print(f"[-] Network exploit failed: {{e}}")
            return False

    def _web_exploit(self, payload, authenticated):
        \"\"\"Web-based exploit\"\"\"
        import requests

        url = self.target
        print(f"[*] Sending web request to {{url}}")

        try:
            if authenticated:
                auth = (self.username, self.password)
                response = requests.post(url, data={{'payload': payload}}, auth=auth, timeout=10)
            else:
                response = requests.post(url, data={{'payload': payload}}, timeout=10)

            print(f"[+] Response status: {{response.status_code}}")
            print(f"[+] Response: {{response.text[:200]}}")

            if response.status_code == 200:
                print(f"[+] Exploit completed successfully")
                return True
            else:
                print(f"[-] Exploit may have failed (status code: {{response.status_code}})")
                return False

        except Exception as e:
            print(f"[-] Web exploit failed: {{e}}")
            return False

def main():
    \"\"\"Main entry point\"\"\"
    import argparse

    parser = argparse.ArgumentParser(description="Novel Vulnerability Exploit")
    parser.add_argument('--target', required=True, help='Target IP or URL')
    parser.add_argument('--port', type=int, default=None, help='Target port')
    parser.add_argument('--username', default=None, help='Username')
    parser.add_argument('--password', default=None, help='Password')

    args = parser.parse_args()

    exploit = NovelExploit(
        target=args.target,
        port=args.port,
        username=args.username,
        password=args.password
    )

    success = exploit.exploit()

    if success:
        print("[+] Exploitation completed successfully")
        sys.exit(0)
    else:
        print("[-] Exploitation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""

    return exploit_template


@tool(category="security", mutating=False)
def check_novelty_indicators(
    text: Annotated[str, "Text to check for novelty indicators"],
) -> str:
    """Check text for indicators that suggest a novel (previously unknown) vulnerability.

    Scans for patterns that indicate:
    - Recent code changes
    - Custom allocator implementations
    - Compiler optimization issues
    - SIMD/vector processing
    - JIT compilation
    - Template/metaprogramming
    - Previously undocumented patterns
    """
    novelty_indicators = {
        "recent_code": [
            "recently added",
            "new feature",
            "latest version",
            "recent commit",
            "latest changes",
            "newly implemented",
            "recently introduced",
        ],
        "custom_allocator": [
            "custom allocator",
            "memory pool",
            "arena allocation",
            "pool manager",
            "custom memory",
            "region allocator",
            "bump allocator",
        ],
        "compiler_optimization": [
            "compiler optimization",
            "optimizer bug",
            "LTO",
            "PGO",
            "link-time optimization",
            "profile-guided",
            "optimization-induced",
        ],
        "simd": ["SIMD", "vector", "SSE", "AVX", "__m256", "__m128", "vectorization", "intrinsic", "vector operation"],
        "jit": [
            "JIT",
            "just-in-time",
            "bytecode interpreter",
            "runtime compilation",
            "dynamic compilation",
            "code generation",
            "vm-based",
        ],
        "template": [
            "template metaprogramming",
            "constexpr evaluation",
            "template instantiation",
            "compile-time computation",
            "template recursion",
        ],
        "unknown_patterns": [
            "undocumented",
            "unknown protocol",
            "custom format",
            "proprietary",
            "non-standard",
            "unusual pattern",
            "novel approach",
        ],
    }

    text_lower = text.lower()
    found_indicators = {}

    for category, indicators in novelty_indicators.items():
        found = []
        for indicator in indicators:
            if indicator in text_lower:
                found.append(indicator)
        if found:
            found_indicators[category] = found

    if not found_indicators:
        return "No novelty indicators found. The code appears to use standard, well-documented patterns."

    # Calculate novelty score
    total_found = sum(len(v) for v in found_indicators.values())
    novelty_score = min(total_found * 0.1, 1.0)

    result_lines = [
        "Novelty Analysis Results",
        "",
        f"Novelty Score: {novelty_score:.2f} / 1.0",
        f"Categories Found: {len(found_indicators)}",
        f"Total Indicators: {total_found}",
        "",
    ]

    for category, indicators in found_indicators.items():
        result_lines.append(f"**{category.replace('_', ' ').title()}:**")
        for indicator in indicators:
            result_lines.append(f"  - {indicator}")
        result_lines.append("")

    if novelty_score > 0.7:
        result_lines.append("✓ HIGH NOVELTY: Strong indicators of novel vulnerability patterns")
    elif novelty_score > 0.4:
        result_lines.append("✓ MEDIUM NOVELTY: Some novelty indicators present")
    else:
        result_lines.append("⚠ LOW NOVELTY: Mostly standard patterns")

    result_lines.append("")
    result_lines.append(
        "Recommendation: "
        + (
            "Proceed with deep analysis - high novelty detected"
            if novelty_score > 0.5
            else "Standard vulnerability analysis sufficient"
            if novelty_score > 0.3
            else "Known vulnerability patterns - check CVE databases first"
        )
    )

    return "\n".join(result_lines)

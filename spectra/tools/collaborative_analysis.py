"""Collaborative Analysis tool for IDA Pro and Binary Ninja.

Enables team collaboration by:
- Exporting/importing shared findings
- Merging analysis from multiple analysts
- Generating team-friendly reports
- Syncing bookmarks and annotations
- Creating shareable analysis snapshots
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idc
    import idautils
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Try to import Binary Ninja API
try:
    import binaryninja
    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# Default paths
SPECTRA_COLLAB_DIR = Path.home() / ".spectra" / "collab"
SPECTRA_COLLAB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Finding:
    """A single finding that can be shared with the team."""
    address: int
    type: str  # "vulnerability", "suspicious", "interesting", "false_positive"
    category: str  # "overflow", "uaf", "crypto", "network", etc.
    severity: str  # "critical", "high", "medium", "low", "info"
    title: str
    description: str
    analyst: str = "Unknown"
    timestamp: str = ""
    function_name: str = ""
    references: list[str] = field(default_factory=list)
    verified: bool = False
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Annotation:
    """A function or address annotation."""
    address: int
    type: str  # "comment", "rename", "type_change"
    old_value: str = ""
    new_value: str = ""
    analyst: str = "Unknown"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class AnalysisSnapshot:
    """A complete analysis snapshot for sharing."""
    binary_name: str = ""
    binary_hash: str = ""
    analyst: str = "Unknown"
    timestamp: str = ""
    findings: list[Finding] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    summary: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


def _get_binary_info_ida() -> dict[str, str]:
    """Get binary information from IDA Pro."""
    if not IDA_AVAILABLE:
        return {"name": "unknown", "hash": "unknown"}

    import hashlib

    # Get database path
    db_path = idaapi.get_path(idaapi.PATH_TYPE_IDB)
    binary_name = os.path.basename(db_path)

    # Try to get input file path for hash
    input_file = idaapi.get_input_file_path()
    file_hash = "unknown"
    if input_file and os.path.exists(input_file):
        with open(input_file, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    return {"name": binary_name, "hash": file_hash}


def _get_binary_info_binja(bv) -> dict[str, str]:
    """Get binary information from Binary Ninja."""
    if not BINJA_AVAILABLE or not bv:
        return {"name": "unknown", "hash": "unknown"}

    import hashlib

    binary_name = os.path.basename(bv.file.filename) if bv.file.filename else "unknown"

    file_hash = "unknown"
    if bv.file.raw:
        file_hash = hashlib.sha256(bv.file.raw).hexdigest()[:16]

    return {"name": binary_name, "hash": file_hash}


def _export_findings_ida() -> list[Finding]:
    """Export findings from IDA Pro."""
    if not IDA_AVAILABLE:
        return []

    findings = []

    # Get all function names (renamed functions)
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Check for marked functions (comments with special markers)
        try:
            cmt = idc.get_func_cmt(func_ea, 0) or ""
            if cmt:
                # Look for finding markers in comments: [FINDING:TYPE:SEVERITY]
                matches = re.findall(r'\[FINDING:(\w+):(\w+)\]\s*(.*?)(?:\n|$)', cmt)
                for ftype, severity, title in matches:
                    findings.append(Finding(
                        address=func_ea,
                        type=ftype.lower(),
                        category="general",
                        severity=severity.lower(),
                        title=title.strip(),
                        description=cmt,
                        function_name=func_name,
                    ))
        except Exception:
            pass

    # Export suspicious API findings if tool exists
    try:
        from .suspicious_api import scan_all_suspicious_apis
        api_results = scan_all_suspicious_apis()
        for api in api_results.get("suspicious_apis", [])[:20]:
            findings.append(Finding(
                address=api.get("address", 0),
                type="suspicious",
                category="api",
                severity=api.get("severity", "medium"),
                title=f"Suspicious API: {api.get('name', 'unknown')}",
                description=api.get("description", ""),
                function_name=api.get("function", ""),
                tags=["suspicious_api"],
            ))
    except Exception:
        pass

    # Export anti-debug findings if tool exists
    try:
        from .anti_debug import scan_all_anti_debug
        ad_results = scan_all_anti_debug()
        for ad in ad_results.get("api_calls", [])[:10]:
            findings.append(Finding(
                address=ad.get("address", 0),
                type="suspicious",
                category="anti_debug",
                severity=ad.get("severity", "medium"),
                title=f"Anti-Debug: {ad.get('api', 'unknown')}",
                description=ad.get("description", ""),
                function_name=ad.get("function", ""),
                tags=["anti_debug"],
            ))
    except Exception:
        pass

    return findings


def _export_annotations_ida() -> list[Annotation]:
    """Export annotations from IDA Pro."""
    if not IDA_AVAILABLE:
        return []

    annotations = []

    # Export renamed functions
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Check if it was renamed (not sub_*)
        if not func_name.startswith("sub_") and not func_name.startswith("loc_"):
            annotations.append(Annotation(
                address=func_ea,
                type="rename",
                new_value=func_name,
                old_value=f"sub_{func_ea:X}",
            ))

    # Export function comments
    for func_ea in idautils.Functions():
        try:
            cmt = idc.get_func_cmt(func_ea, 0)
            if cmt and cmt.strip():
                annotations.append(Annotation(
                    address=func_ea,
                    type="comment",
                    new_value=cmt,
                    function_name=idc.get_func_name(func_ea),
                ))
        except Exception:
            pass

    return annotations[:100]  # Limit to 100 annotations


def export_snapshot_ida(analyst: str = "Unknown", summary: str = "") -> AnalysisSnapshot:
    """Export complete analysis snapshot from IDA Pro."""
    if not IDA_AVAILABLE:
        return AnalysisSnapshot()

    binary_info = _get_binary_info_ida()

    return AnalysisSnapshot(
        binary_name=binary_info["name"],
        binary_hash=binary_info["hash"],
        analyst=analyst,
        summary=summary,
        findings=_export_findings_ida(),
        annotations=_export_annotations_ida(),
        metadata={
            "ida_version": idaapi.get_kernel_version(),
            "export_date": datetime.now().isoformat(),
        },
    )


def export_snapshot_binja(bv, analyst: str = "Unknown", summary: str = "") -> AnalysisSnapshot:
    """Export complete analysis snapshot from Binary Ninja."""
    if not BINJA_AVAILABLE or not bv:
        return AnalysisSnapshot()

    binary_info = _get_binary_info_binja(bv)

    findings = []
    annotations = []

    # Export renamed functions
    for func in bv.functions:
        if not func.name.startswith("sub_"):
            annotations.append(Annotation(
                address=func.start,
                type="rename",
                new_value=func.name,
            ))

    # Export comments
    for func in bv.functions:
        for comment_addr, comment in func.get_comment_addresses(bv):
            if comment and comment.strip():
                annotations.append(Annotation(
                    address=comment_addr,
                    type="comment",
                    new_value=comment,
                    function_name=func.name,
                ))

    return AnalysisSnapshot(
        binary_name=binary_info["name"],
        binary_hash=binary_info["hash"],
        analyst=analyst,
        summary=summary,
        findings=findings[:50],
        annotations=annotations[:100],
        metadata={
            "bn_version": str(binaryninja.core_version),
            "export_date": datetime.now().isoformat(),
        },
    )


def save_snapshot(snapshot: AnalysisSnapshot, filepath: str | None = None) -> str:
    """Save analysis snapshot to file."""
    if filepath is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = SPECTRA_COLLAB_DIR / f"{snapshot.binary_name}_{timestamp}.json"

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Convert dataclasses to dict
    data = {
        "binary_name": snapshot.binary_name,
        "binary_hash": snapshot.binary_hash,
        "analyst": snapshot.analyst,
        "timestamp": snapshot.timestamp,
        "summary": snapshot.summary,
        "metadata": snapshot.metadata,
        "findings": [asdict(f) for f in snapshot.findings],
        "annotations": [asdict(a) for a in snapshot.annotations],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return str(filepath)


def load_snapshot(filepath: str) -> AnalysisSnapshot:
    """Load analysis snapshot from file."""
    with open(filepath) as f:
        data = json.load(f)

    findings = [Finding(**f) for f in data.get("findings", [])]
    annotations = [Annotation(**a) for a in data.get("annotations", [])]

    return AnalysisSnapshot(
        binary_name=data.get("binary_name", ""),
        binary_hash=data.get("binary_hash", ""),
        analyst=data.get("analyst", "Unknown"),
        timestamp=data.get("timestamp", ""),
        summary=data.get("summary", ""),
        metadata=data.get("metadata", {}),
        findings=findings,
        annotations=annotations,
    )


def list_shared_snapshots() -> list[dict[str, Any]]:
    """List all shared snapshots in the collaboration directory."""
    snapshots = []

    for filepath in SPECTRA_COLLAB_DIR.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)

            snapshots.append({
                "filepath": str(filepath),
                "binary_name": data.get("binary_name", "unknown"),
                "analyst": data.get("analyst", "Unknown"),
                "timestamp": data.get("timestamp", ""),
                "finding_count": len(data.get("findings", [])),
                "annotation_count": len(data.get("annotations", [])),
                "summary": data.get("summary", ""),
            })
        except Exception:
            continue

    return sorted(snapshots, key=lambda x: x["timestamp"], reverse=True)


def merge_snapshots(snapshots: list[AnalysisSnapshot]) -> AnalysisSnapshot:
    """Merge multiple analysis snapshots into one.

    Conflicts are resolved by:
    - Keeping the most recent timestamp for each item
    - Combining all findings
    - Combining all annotations
    """
    if not snapshots:
        return AnalysisSnapshot()

    # Use the most recent snapshot as base
    base = max(snapshots, key=lambda s: s.timestamp)

    # Collect all findings (deduplicate by address + title)
    all_findings = {}
    for snapshot in snapshots:
        for finding in snapshot.findings:
            key = (finding.address, finding.title)
            if key not in all_findings or finding.timestamp > all_findings[key].timestamp:
                all_findings[key] = finding

    # Collect all annotations (deduplicate by address + type)
    all_annotations = {}
    for snapshot in snapshots:
        for annotation in snapshot.annotations:
            key = (annotation.address, annotation.type)
            if key not in all_annotations or annotation.timestamp > all_annotations[key].timestamp:
                all_annotations[key] = annotation

    # Combine analyst names
    analysts = list(set(s.analyst for s in snapshots))
    combined_analyst = ", ".join(analysts[:3])  # Limit to 3 names
    if len(analysts) > 3:
        combined_analyst += f" +{len(analysts) - 3} more"

    return AnalysisSnapshot(
        binary_name=base.binary_name,
        binary_hash=base.binary_hash,
        analyst=combined_analyst,
        timestamp=datetime.now().isoformat(),
        summary=f"Merged analysis from {len(snapshots)} analysts",
        findings=list(all_findings.values()),
        annotations=list(all_annotations.values()),
        metadata={
            "merged_from": [s.analyst for s in snapshots],
            "merge_date": datetime.now().isoformat(),
            "original_timestamps": [s.timestamp for s in snapshots],
        },
    )


def format_collaboration_report(snapshots: list[AnalysisSnapshot]) -> str:
    """Format a collaborative analysis report."""
    if not snapshots:
        return "No snapshots to report."

    merged = merge_snapshots(snapshots) if len(snapshots) > 1 else snapshots[0]

    report_lines = ["## Collaborative Analysis Report\n"]
    report_lines.append(f"**Binary:** {merged.binary_name}\n")
    report_lines.append(f"**Hash:** `{merged.binary_hash}`\n")
    report_lines.append(f"**Analysts:** {merged.analyst}\n")
    report_lines.append(f"**Generated:** {merged.timestamp}\n")

    if merged.summary:
        report_lines.append(f"\n### Summary\n{merged.summary}\n")

    # Findings by category
    findings_by_category: dict[str, list[Finding]] = {}
    for finding in merged.findings:
        if finding.category not in findings_by_category:
            findings_by_category[finding.category] = []
        findings_by_category[finding.category].append(finding)

    if findings_by_category:
        report_lines.append(f"\n### Findings ({len(merged.findings)} total)\n")

        for category, findings in sorted(findings_by_category.items()):
            report_lines.append(f"\n#### {category.title()}\n")

            # Group by severity
            by_severity: dict[str, list[Finding]] = {}
            for finding in findings:
                if finding.severity not in by_severity:
                    by_severity[finding.severity] = []
                by_severity[finding.severity].append(finding)

            for severity in ["critical", "high", "medium", "low", "info"]:
                if severity in by_severity:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "🔵"}.get(severity, "⚪")
                    report_lines.append(f"\n**{icon.upper()} {severity.upper()}**\n")
                    for finding in by_severity[severity][:10]:
                        verified_mark = "✓" if finding.verified else ""
                        report_lines.append(
                            f"- `{finding.address:X}` **{finding.title}** {verified_mark}\n"
                            f"  - {finding.description[:100]}...\n"
                        )
                    if len(by_severity[severity]) > 10:
                        report_lines.append(f"  - _...and {len(by_severity[severity]) - 10} more_\n")

    # Annotations summary
    if merged.annotations:
        report_lines.append(f"\n### Annotations ({len(merged.annotations)} total)\n")

        rename_count = sum(1 for a in merged.annotations if a.type == "rename")
        comment_count = sum(1 for a in merged.annotations if a.type == "comment")

        report_lines.append(f"- **Renamed functions:** {rename_count}\n")
        report_lines.append(f"- **Comments added:** {comment_count}\n")

    # Contributors
    if len(snapshots) > 1:
        report_lines.append(f"\n### Contributors\n")
        for snapshot in sorted(snapshots, key=lambda s: s.timestamp):
            report_lines.append(
                f"- **{snapshot.analyst}** - {snapshot.findings} findings, "
                f"{snapshot.annotations} annotations\n"
            )

    return "\n".join(report_lines)


def format_team_report(snapshot: AnalysisSnapshot) -> str:
    """Format a team-friendly markdown report for a single snapshot."""
    report_lines = ["# Analysis Report\n"]
    report_lines.append(f"**Binary:** {snapshot.binary_name}\n")
    report_lines.append(f"**Analyst:** {snapshot.analyst}\n")
    report_lines.append(f"**Date:** {snapshot.timestamp[:10]}\n")

    if snapshot.summary:
        report_lines.append(f"\n## Summary\n{snapshot.summary}\n")

    # Findings
    if snapshot.findings:
        report_lines.append(f"\n## Findings ({len(snapshot.findings)})\n")

        by_severity: dict[str, list[Finding]] = {}
        for finding in snapshot.findings:
            if finding.severity not in by_severity:
                by_severity[finding.severity] = []
            by_severity[finding.severity].append(finding)

        for severity in ["critical", "high", "medium", "low", "info"]:
            if severity in by_severity:
                report_lines.append(f"\n### {severity.upper()}\n")
                for finding in by_severity[severity]:
                    report_lines.append(
                        f"\n#### {finding.title}\n"
                        f"- **Address:** `{finding.address:X}`\n"
                        f"- **Category:** {finding.category}\n"
                        f"- **Analyst:** {finding.analyst}\n"
                        f"- **Description:** {finding.description}\n"
                    )
                    if finding.tags:
                        report_lines.append(f"- **Tags:** {', '.join(finding.tags)}\n")

    # Annotations
    if snapshot.annotations:
        report_lines.append(f"\n## Annotations ({len(snapshot.annotations)})\n")

        renames = [a for a in snapshot.annotations if a.type == "rename"]
        comments = [a for a in snapshot.annotations if a.type == "comment"]

        if renames:
            report_lines.append(f"\n### Renamed Functions ({len(renames)})\n")
            for a in renames[:20]:
                report_lines.append(f"- `{a.address:X}`: `{a.old_value}` → `{a.new_value}`\n")
            if len(renames) > 20:
                report_lines.append(f"_...and {len(renames) - 20} more_\n")

        if comments:
            report_lines.append(f"\n### Comments ({len(comments)})\n")
            for a in comments[:15]:
                func = a.function_name or f"sub_{a.address:X}"
                report_lines.append(f"- `{a.address:X}` ({func}): {a.new_value[:80]}...\n")
            if len(comments) > 15:
                report_lines.append(f"_...and {len(comments) - 15} more_\n")

    return "\n".join(report_lines)


if __name__ == "__main__":
    # Test export
    if IDA_AVAILABLE:
        snapshot = export_snapshot_ida(analyst="Test Analyst")
        print(f"Exported snapshot: {len(snapshot.findings)} findings, {len(snapshot.annotations)} annotations")
        filepath = save_snapshot(snapshot)
        print(f"Saved to: {filepath}")
    else:
        print("IDA Pro API not available")

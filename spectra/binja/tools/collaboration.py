"""Collaborative Analysis tool for Binary Ninja."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.collaborative_analysis import (
    AnalysisSnapshot,
    export_snapshot_binja,
    format_collaboration_report,
    format_team_report,
    list_shared_snapshots,
    load_snapshot,
    merge_snapshots,
    save_snapshot,
)
from .compat import require_bv


@tool(category="collaboration", mutating=False, description="Export current analysis to a shareable snapshot")
def export_analysis(
    analyst: Annotated[str, "Your name or handle"] = "Analyst",
    summary: Annotated[str, "Brief summary of your analysis"] = "",
) -> str:
    """Export your current analysis to a shareable JSON snapshot.

    The snapshot includes:
    - All renamed functions
    - All comments and annotations
    - Detected findings (vulnerabilities, suspicious APIs, etc.)
    - Binary metadata (name, hash)

    Args:
        analyst: Your name or handle for attribution
        summary: Brief description of what you analyzed

    Returns the file path where the snapshot was saved.
    """
    bv = require_bv()
    snapshot = export_snapshot_binja(bv, analyst=analyst, summary=summary)
    filepath = save_snapshot(snapshot)

    return f"Analysis snapshot exported successfully!\n\n" \
           f"**File:** {filepath}\n" \
           f"**Findings:** {len(snapshot.findings)}\n" \
           f"**Annotations:** {len(snapshot.annotations)}\n" \
           f"**Analyst:** {analyst}\n" \
           f"**Date:** {snapshot.timestamp[:10]}\n"


@tool(category="collaboration", mutating=False, description="List all shared analysis snapshots")
def list_shared_analyses() -> str:
    """List all shared analysis snapshots in the collaboration directory.

    Returns a table of snapshots with:
    - Binary name
    - Analyst name
    - Timestamp
    - Finding and annotation counts
    - Summary (if available)
    """
    snapshots = list_shared_snapshots()

    if not snapshots:
        return "No shared snapshots found. Use `export_analysis` to create one."

    report = "## Shared Analysis Snapshots\n\n"

    for snap in snapshots[:20]:
        report += f"### {snap['binary_name']}\n"
        report += f"- **Analyst:** {snap['analyst']}\n"
        report += f"- **Date:** {snap['timestamp'][:10]}\n"
        report += f"- **Findings:** {snap['finding_count']}\n"
        report += f"- **Annotations:** {snap['annotation_count']}\n"
        if snap.get('summary'):
            report += f"- **Summary:** {snap['summary'][:100]}...\n"
        report += f"- **File:** `{snap['filepath']}`\n\n"

    if len(snapshots) > 20:
        report += f"_... and {len(snapshots) - 20} more_\n"

    return report


@tool(category="collaboration", mutating=False, description="Generate team report from shared snapshots")
def generate_team_report(
    snapshot_path: Annotated[str, "Path to snapshot file (or 'all' to merge all)"] = "all",
) -> str:
    """Generate a team-friendly report from one or more analysis snapshots.

    Args:
        snapshot_path: Path to a specific snapshot JSON file, or "all" to merge all snapshots

    Returns a formatted markdown report suitable for team sharing.
    """
    if snapshot_path == "all":
        snapshots_data = list_shared_snapshots()
        if not snapshots_data:
            return "No snapshots found to merge."

        snapshots = []
        for snap_data in snapshots_data[:5]:  # Limit to 5
            try:
                snap = load_snapshot(snap_data['filepath'])
                snapshots.append(snap)
            except Exception as e:
                continue

        if not snapshots:
            return "Failed to load any snapshots."

        return format_collaboration_report(snapshots)

    # Load specific snapshot
    try:
        snapshot = load_snapshot(snapshot_path)
        return format_team_report(snapshot)
    except FileNotFoundError:
        return f"Snapshot file not found: {snapshot_path}"
    except Exception as e:
        return f"Error loading snapshot: {e}"


@tool(category="collaboration", mutating=False, description="Merge multiple analysis snapshots")
def merge_analyses(
    snapshot_paths: Annotated[str, "Comma-separated paths to snapshot files"] = "",
) -> str:
    """Merge multiple analysis snapshots into a combined report.

    Args:
        snapshot_paths: Comma-separated list of snapshot file paths

    Returns a merged analysis report combining all findings and annotations.
    """
    if not snapshot_paths:
        # Auto-merge all snapshots
        snapshots_data = list_shared_snapshots()
        if not snapshots_data:
            return "No snapshots found to merge."

        paths = [s['filepath'] for s in snapshots_data[:5]]
    else:
        paths = [p.strip() for p in snapshot_paths.split(",")]

    snapshots = []
    for path in paths:
        try:
            snap = load_snapshot(path)
            snapshots.append(snap)
        except Exception:
            continue

    if not snapshots:
        return "Failed to load any snapshots."

    merged = merge_snapshots(snapshots)

    return f"## Merged Analysis Report\n\n" \
           f"**Analysts:** {merged.analyst}\n" \
           f"**Total Findings:** {len(merged.findings)}\n" \
           f"**Total Annotations:** {len(merged.annotations)}\n\n" \
           f"{format_collaboration_report(snapshots)}"


@tool(category="collaboration", mutating=False, description="Add a finding to the current analysis")
def add_finding(
    address: Annotated[int, "Function or code address"],
    title: Annotated[str, "Short title for the finding"],
    severity: Annotated[str, "Severity: critical, high, medium, low, info"] = "medium",
    category: Annotated[str, "Category: overflow, uaf, crypto, network, api, etc."] = "general",
    description: Annotated[str, "Detailed description of the finding"] = "",
) -> str:
    """Add a manual finding to the current analysis for team sharing.

    Args:
        address: Function or code address where the finding is located
        title: Short descriptive title
        severity: Severity level (critical, high, medium, low, info)
        category: Finding category (overflow, uaf, crypto, network, api, etc.)
        description: Detailed description of the finding

    Returns confirmation with finding details.
    """
    from ...tools.collaborative_analysis import Finding

    finding = Finding(
        address=address,
        type="manual",
        category=category,
        severity=severity,
        title=title,
        description=description,
        analyst="Manual",
    )

    # Add as Binary Ninja comment for persistence
    try:
        bv = require_bv()
        func = bv.get_function_at(address)
        if func:
            comment = f"[FINDING:{finding.type}:{finding.severity}] {finding.title}\n{finding.description}"
            func.set_comment_at(address, comment)
    except Exception:
        pass

    return f"Finding added successfully!\n\n" \
           f"**Title:** {title}\n" \
           f"**Address:** 0x{address:X}\n" \
           f"**Severity:** {severity}\n" \
           f"**Category:** {category}\n" \
           f"**Description:** {description}\n\n" \
           f"Use `export_analysis` to include this finding in a shared snapshot."

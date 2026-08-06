"""Findings bookmarking system for IDA Pro.

Allows analysts to bookmark important findings during analysis:
- Add/remove bookmarks at addresses
- Add notes and tags
- Categorize findings (suspicious, critical, verified, etc.)
- Export/import findings
- Quick navigation to bookmarked locations
"""

from __future__ import annotations

import json
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


# Finding categories
FINDING_CATEGORIES = {
    "suspicious": {
        "name": "Suspicious",
        "color": "#ffa07a",  # Orange
        "icon": "!",
        "description": "Potentially malicious code/behavior"
    },
    "critical": {
        "name": "Critical",
        "color": "#ff6b6b",  # Red
        "icon": "CRIT",
        "description": "Critical security issue"
    },
    "verified": {
        "name": "Verified",
        "color": "#6bff98",  # Green
        "icon": "V",
        "description": "Confirmed finding"
    },
    "interesting": {
        "name": "Interesting",
        "color": "#ffd93d",  # Yellow
        "icon": "INT",
        "description": "Notable code/behavior"
    },
    "false_positive": {
        "name": "False Positive",
        "color": "#808080",  # Gray
        "icon": "FP",
        "description": "Confirmed as benign"
    },
    "question": {
        "name": "Question",
        "color": "#569cd6",  # Blue
        "icon": "?",
        "description": "Needs further investigation"
    },
}


class Finding:
    """Represents a single finding/bookmark."""

    def __init__(
        self,
        address: int,
        title: str,
        category: str = "interesting",
        notes: str = "",
        tags: list[str] | None = None,
        timestamp: str | None = None,
    ):
        self.address = address
        self.title = title
        self.category = category
        self.notes = notes
        self.tags = tags or []
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "address": self.address,
            "title": self.title,
            "category": self.category,
            "notes": self.notes,
            "tags": self.tags,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        """Create from dictionary."""
        return cls(
            address=data["address"],
            title=data["title"],
            category=data.get("category", "interesting"),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            timestamp=data.get("timestamp"),
        )


class FindingsBookmarkManager:
    """Manages findings bookmarks for IDA Pro."""

    def __init__(self, idb_path: str | None = None):
        self.idb_path = idb_path
        self.findings: list[Finding] = []
        self._load_findings()

    def _get_findings_file(self) -> Path:
        """Get the findings file path for current IDB."""
        if not self.idb_path:
            # Use default location
            from ...core.logging import log_debug
            log_debug("No IDB path, using default findings location")
            return Path.home() / ".spectra" / "findings.json"

        # Create findings file alongside IDB
        idb_path = Path(self.idb_path)
        findings_file = idb_path.parent / f"{idb_path.stem}_findings.json"
        return findings_file

    def _load_findings(self) -> None:
        """Load findings from JSON file."""
        try:
            findings_file = self._get_findings_file()
            if findings_file.exists():
                with open(findings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.findings = [Finding.from_dict(item) for item in data]
        except Exception as e:
            from ...core.logging import log_error
            log_error(f"Failed to load findings: {e}")
            self.findings = []

    def _save_findings(self) -> None:
        """Save findings to JSON file."""
        try:
            findings_file = self._get_findings_file()
            findings_file.parent.mkdir(parents=True, exist_ok=True)

            data = [finding.to_dict() for finding in self.findings]
            with open(findings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            from ...core.logging import log_error
            log_error(f"Failed to save findings: {e}")

    def add_finding(
        self,
        address: int,
        title: str,
        category: str = "interesting",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> Finding:
        """Add a new finding.

        Args:
            address: Address in IDB
            title: Short title/description
            category: Category from FINDING_CATEGORIES
            notes: Detailed notes
            tags: Optional tags for grouping

        Returns:
            Created Finding object
        """
        if category not in FINDING_CATEGORIES:
            category = "interesting"

        finding = Finding(
            address=address,
            title=title,
            category=category,
            notes=notes,
            tags=tags or [],
        )
        self.findings.append(finding)
        self._save_findings()
        return finding

    def remove_finding(self, address: int) -> bool:
        """Remove finding at address.

        Args:
            address: Address to remove

        Returns:
            True if finding was removed
        """
        original_count = len(self.findings)
        self.findings = [f for f in self.findings if f.address != address]

        if len(self.findings) < original_count:
            self._save_findings()
            return True
        return False

    def get_finding(self, address: int) -> Finding | None:
        """Get finding at address.

        Args:
            address: Address to lookup

        Returns:
            Finding object or None
        """
        for finding in self.findings:
            if finding.address == address:
                return finding
        return None

    def get_all_findings(self) -> list[Finding]:
        """Get all findings."""
        return self.findings.copy()

    def get_findings_by_category(self, category: str) -> list[Finding]:
        """Get findings filtered by category.

        Args:
            category: Category name

        Returns:
            List of findings in category
        """
        return [f for f in self.findings if f.category == category]

    def get_findings_by_tag(self, tag: str) -> list[Finding]:
        """Get findings filtered by tag.

        Args:
            tag: Tag to search

        Returns:
            List of findings with tag
        """
        return [f for f in self.findings if tag in f.tags]

    def update_finding(
        self,
        address: int,
        title: str | None = None,
        category: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Update existing finding.

        Args:
            address: Address of finding to update
            title: New title (optional)
            category: New category (optional)
            notes: New notes (optional)
            tags: New tags (optional)

        Returns:
            True if finding was updated
        """
        finding = self.get_finding(address)
        if not finding:
            return False

        if title is not None:
            finding.title = title
        if category is not None:
            finding.category = category
        if notes is not None:
            finding.notes = notes
        if tags is not None:
            finding.tags = tags

        finding.timestamp = datetime.now().isoformat()
        self._save_findings()
        return True

    def export_to_markdown(self) -> str:
        """Export findings as formatted markdown report.

        Returns:
            Markdown formatted report
        """
        if not self.findings:
            return "# No Findings\n\nNo findings bookmarked yet."

        lines = [
            "# Findings Bookmark Report\n",
            f"**Total Findings:** {len(self.findings)}\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        ]

        # Group by category
        by_category = {}
        for finding in self.findings:
            if finding.category not in by_category:
                by_category[finding.category] = []
            by_category[finding.category].append(finding)

        # Sort categories by severity
        category_order = ["critical", "suspicious", "verified", "interesting", "question", "false_positive"]

        for category in category_order:
            if category not in by_category:
                continue

            category_info = FINDING_CATEGORIES[category]
            findings = by_category[category]

            lines.append(f"\n## {category_info['icon']} {category_info['name']}\n")
            lines.append(f"*{category_info['description']}*\n")

            for finding in sorted(findings, key=lambda f: f.address):
                lines.append(f"### **{finding.title}**\n")
                lines.append(f"- **Address:** `{finding.address:X}`\n")
                lines.append(f"- **Category:** {category_info['name']}\n")
                lines.append(f"- **Date:** {finding.timestamp}\n")

                if finding.tags:
                    lines.append(f"- **Tags:** {', '.join(f'`{tag}`' for tag in finding.tags)}\n")

                if finding.notes:
                    lines.append(f"- **Notes:**\n{finding.notes}\n")

        return "\n".join(lines)

    def import_from_markdown(self, markdown: str) -> int:
        """Import findings from markdown (basic support).

        Args:
            markdown: Markdown text with findings

        Returns:
            Number of findings imported
        """
        # This is a simplified implementation
        # In practice, you'd want more robust markdown parsing
        imported = 0

        lines = markdown.split('\n')
        current_finding = None

        for line in lines:
            line = line.strip()

            # Look for finding headers
            if line.startswith("### ") and "**" in line:
                # Extract title
                title = line.replace("### ", "").replace("**", "").strip()
                if current_finding:
                    # Save previous finding
                    try:
                        self.add_finding(**current_finding)
                        imported += 1
                    except Exception:
                        pass

                # Start new finding (will be filled in next pass)
                current_finding = {"title": title, "notes": ""}

            elif current_finding and line.startswith("- **Notes:**"):
                # Extract notes (everything after "- **Notes:**")
                notes = line.replace("- **Notes:**", "").strip()
                current_finding["notes"] = notes

        # Save last finding
        if current_finding:
            try:
                self.add_finding(**current_finding)
                imported += 1
            except Exception:
                pass

        return imported


# Global instance (will be initialized per IDB)
_global_manager: FindingsBookmarkManager | None = None


def get_findings_manager(idb_path: str | None = None) -> FindingsBookmarkManager:
    """Get or create the findings manager for current IDB.

    Args:
        idb_path: Optional IDB path

    Returns:
        FindingsBookmarkManager instance
    """
    global _global_manager
    if _global_manager is None or (idb_path and _global_manager.idb_path != idb_path):
        _global_manager = FindingsBookmarkManager(idb_path)
    return _global_manager


# Convenience functions for use in IDA
def add_finding_at_ea(ea: int, title: str, category: str = "interesting", notes: str = "") -> bool:
    """Add finding at current IDA address.

    Args:
        ea: Effective address
        title: Finding title
        category: Category
        notes: Optional notes

    Returns:
        True if successful
    """
    if not IDA_AVAILABLE:
        return False

    try:
        from ...core.logging import log_info
        manager = get_findings_manager()
        finding = manager.add_finding(ea, title, category, notes)
        log_info(f"Added finding at 0x{ea:X}: {title}")
        return True
    except Exception as e:
        from ...core.logging import log_error
        log_error(f"Failed to add finding: {e}")
        return False


def remove_finding_at_ea(ea: int) -> bool:
    """Remove finding at address.

    Args:
        ea: Effective address

    Returns:
        True if finding was removed
    """
    if not IDA_AVAILABLE:
        return False

    try:
        from ...core.logging import log_info
        manager = get_findings_manager()
        success = manager.remove_finding(ea)
        if success:
            log_info(f"Removed finding at 0x{ea:X}")
        return success
    except Exception as e:
        from ...core.logging import log_error
        log_error(f"Failed to remove finding: {e}")
        return False


def list_all_findings() -> list[Finding]:
    """List all findings.

    Returns:
        List of all Finding objects
    """
    manager = get_findings_manager()
    return manager.get_all_findings()


if __name__ == "__main__":
    # Test findings manager
    manager = FindingsBookmarkManager("/tmp/test.idb")

    # Add some test findings
    manager.add_finding(0x401000, "Process injection entry point", "critical", "Uses CreateRemoteThread")
    manager.add_finding(0x401100, "String decryption", "suspicious", "Custom crypto algorithm", tags=["crypto", "strings"])
    manager.add_finding(0x401200, "False positive", "false_positive", "Benign library function")

    # Export to markdown
    report = manager.export_to_markdown()
    print(report)

    # Get findings by category
    critical = manager.get_findings_by_category("critical")
    print(f"\nCritical findings: {len(critical)}")

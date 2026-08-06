"""CLI file tools - File system operations.

Provides tools for:
- Reading files
- Writing files
- Editing files (string replacement)
- Searching files
- Listing directories
"""

from __future__ import annotations

import os
import glob
from pathlib import Path
from typing import Annotated

from ...tools.base import tool


@tool(name="read_file", category="file")
def read_file(
    path: Annotated[str, "File path to read"],
) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file (relative or absolute)

    Returns:
        File contents as string

    Example:
        read_file("/path/to/file.py")
    """
    try:
        file_path = Path(path).expanduser()

        if not file_path.exists():
            return f"Error: File not found: {path}"

        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        # Limit file size to prevent token overflow
        file_size = file_path.stat().st_size
        if file_size > 100_000:  # 100KB limit
            return f"Error: File too large ({file_size:,} bytes). Max 100KB."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Add line count info
        lines = content.count("\n") + 1
        return f"# {path} ({lines} lines, {file_size:,} bytes)\n\n{content}"

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"


@tool(name="write_file", category="file", mutating=True)
def write_file(
    path: Annotated[str, "File path to write"],
    content: Annotated[str, "Content to write to the file"],
) -> str:
    """Write content to a file.

    Creates the file (and parent directories) if it doesn't exist.
    Overwrites existing file.

    Args:
        path: Path to the file (relative or absolute)
        content: Content to write

    Returns:
        Success message

    Example:
        write_file("/path/to/file.py", "print('hello')")
    """
    try:
        file_path = Path(path).expanduser()

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Written {len(content)} bytes to {path}"

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"


@tool(name="edit_file", category="file", mutating=True)
def edit_file(
    path: Annotated[str, "File path to edit"],
    old_text: Annotated[str, "Text to replace"],
    new_text: Annotated[str, "Replacement text"],
) -> str:
    """Edit a file by replacing text.

    Args:
        path: Path to the file (relative or absolute)
        old_text: Text to find and replace
        new_text: Replacement text

    Returns:
        Success/failure message

    Example:
        edit_file("/path/to/file.py", "old_function", "new_function")
    """
    try:
        file_path = Path(path).expanduser()

        if not file_path.exists():
            return f"Error: File not found: {path}"

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_text not in content:
            return f"Error: Text not found in file: {old_text[:50]}..."

        # Replace all occurrences
        new_content = content.replace(old_text, new_text)
        count = content.count(old_text)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Replaced {count} occurrence(s) in {path}"

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"


@tool(name="search_files", category="file")
def search_files(
    pattern: Annotated[str, "Search pattern (glob style)"],
    directory: Annotated[str, "Directory to search (default: current)"] = ".",
) -> str:
    """Search for files matching a pattern.

    Uses glob-style wildcards: * matches anything, ? matches single char.

    Args:
        pattern: Glob pattern (e.g., "*.py", "test_*.txt")
        directory: Directory to search in

    Returns:
        List of matching files

    Example:
        search_files("*.py", "/path/to/dir")
    """
    try:
        dir_path = Path(directory).expanduser()

        if not dir_path.exists():
            return f"Error: Directory not found: {directory}"

        if not dir_path.is_dir():
            return f"Error: Not a directory: {directory}"

        # Search for matching files
        search_pattern = str(dir_path / pattern)
        matches = glob.glob(search_pattern, recursive=True)

        # Limit results
        if len(matches) > 100:
            matches = matches[:100]
            truncated = f"\n... and {len(matches) - 100} more (truncated)"
        else:
            truncated = ""

        if not matches:
            return f"No files found matching '{pattern}' in {directory}"

        # Format results
        results = [f"Found {len(matches)} file(s):"]
        for m in matches:
            results.append(f"  {m}")

        results.append(truncated)
        return "\n".join(results)

    except Exception as e:
        return f"Error: {e}"


@tool(name="list_directory", category="file")
def list_directory(
    path: Annotated[str, "Directory path to list"] = ".",
) -> str:
    """List contents of a directory.

    Args:
        path: Directory path (default: current directory)

    Returns:
        Directory contents

    Example:
        list_directory("/path/to/dir")
    """
    try:
        dir_path = Path(path).expanduser()

        if not dir_path.exists():
            return f"Error: Directory not found: {path}"

        if not dir_path.is_dir():
            return f"Error: Not a directory: {path}"

        entries = []
        for entry in sorted(dir_path.iterdir()):
            entry_type = "DIR " if entry.is_dir() else "FILE"
            size = entry.stat().st_size if entry.is_file() else 0
            entries.append(f"{entry_type}: {entry.name} ({size:,} bytes)")

        if not entries:
            return f"Empty directory: {path}"

        return f"Directory: {path}\n" + "\n".join(entries)

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"

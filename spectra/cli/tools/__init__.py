"""CLI tools - File operations, shell commands, and SSH.

These tools are specifically for the CLI environment and provide:
- File system operations (read, write, edit, search)
- Shell command execution (with safety checks)
- SSH remote execution and file transfer
"""

from .file_tools import (
    read_file,
    write_file,
    edit_file,
    search_files,
    list_directory,
)

from .shell_tools import (
    shell_command,
)

from .ssh_tools import (
    ssh_connect,
    ssh_exec,
    ssh_upload,
    ssh_download,
    ssh_list,
)

__all__ = [
    "read_file",
    "write_file",
    "edit_file",
    "search_files",
    "list_directory",
    "shell_command",
    "ssh_connect",
    "ssh_exec",
    "ssh_upload",
    "ssh_download",
    "ssh_list",
]

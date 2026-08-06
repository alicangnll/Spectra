"""SSH integration tools for remote command execution.

Provides tools for:
- SSH connection management
- Remote command execution
- File transfer (SCP)
- Interactive SSH sessions
"""

from __future__ import annotations

import subprocess
from typing import Annotated
from pathlib import Path

from ...tools.base import tool


@tool(name="ssh_connect", category="ssh")
def ssh_connect(
    host: Annotated[str, "SSH host (user@hostname or hostname)"],
    port: Annotated[int, "SSH port (default: 22)"] = 22,
    identity_file: Annotated[str, "Path to SSH private key"] = "",
) -> str:
    """Test SSH connection to a remote host.

    Args:
        host: Remote host in format user@hostname or just hostname
        port: SSH port number (default: 22)
        identity_file: Optional path to SSH private key

    Returns:
        Connection status message

    Example:
        ssh_connect("user@example.com")
        ssh_connect("root@192.168.1.1", port=2222, identity_file="~/.ssh/id_rsa")
    """
    try:
        cmd = ["ssh", "-p", str(port), "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]

        if identity_file:
            cmd.extend(["-i", str(Path(identity_file).expanduser())])

        cmd.append(host)
        cmd.extend(["echo", "Connection successful"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return f"✓ SSH connection successful to {host}"
        else:
            return f"✗ SSH connection failed to {host}: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return f"✗ SSH connection timed out to {host}"
    except Exception as e:
        return f"✗ SSH connection error: {e}"


@tool(name="ssh_exec", category="ssh", mutating=True)
def ssh_exec(
    host: Annotated[str, "SSH host (user@hostname or hostname)"],
    command: Annotated[str, "Command to execute on remote host"],
    port: Annotated[int, "SSH port (default: 22)"] = 22,
    identity_file: Annotated[str, "Path to SSH private key"] = "",
    timeout: Annotated[int, "Command timeout in seconds"] = 60,
) -> str:
    """Execute a command on a remote SSH host.

    WARNING: This executes arbitrary commands on remote systems.
    Requires user approval for dangerous commands.

    Args:
        host: Remote host in format user@hostname or just hostname
        command: Shell command to execute remotely
        port: SSH port number (default: 22)
        identity_file: Optional path to SSH private key
        timeout: Maximum time to wait for command completion

    Returns:
        Command output from remote host

    Example:
        ssh_exec("user@server", "ls -la /tmp")
        ssh_exec("root@192.168.1.1", "cat /etc/hostname", port=2222)
    """
    try:
        cmd = ["ssh", "-p", str(port), "-o", "ConnectTimeout=10"]

        if identity_file:
            cmd.extend(["-i", str(Path(identity_file).expanduser())])

        cmd.extend([host, command])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"STDERR: {result.stderr}")

        combined = "\n".join(output) if output else "(no output)"

        if result.returncode != 0:
            combined = f"[Exit code: {result.returncode}]\n{combined}"

        return combined

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {e}"


@tool(name="ssh_upload", category="ssh", mutating=True)
def ssh_upload(
    host: Annotated[str, "SSH host (user@hostname or hostname)"],
    local_path: Annotated[str, "Local file path to upload"],
    remote_path: Annotated[str, "Remote destination path"],
    port: Annotated[int, "SSH port (default: 22)"] = 22,
    identity_file: Annotated[str, "Path to SSH private key"] = "",
) -> str:
    """Upload a file to remote host via SCP.

    Args:
        host: Remote host in format user@hostname or just hostname
        local_path: Path to local file
        remote_path: Destination path on remote host
        port: SSH port number (default: 22)
        identity_file: Optional path to SSH private key

    Returns:
        Upload status message

    Example:
        ssh_upload("user@server", "/tmp/file.txt", "/home/user/file.txt")
        ssh_upload("root@192.168.1.1", "config.yml", "/etc/app/config.yml")
    """
    try:
        local_file = Path(local_path).expanduser()
        if not local_file.exists():
            return f"Error: Local file not found: {local_file}"

        cmd = ["scp", "-P", str(port), "-o", "ConnectTimeout=10"]

        if identity_file:
            cmd.extend(["-i", str(Path(identity_file).expanduser())])

        # Format: scp [options] source user@host:destination
        remote_dest = f"{host}:{remote_path}"
        cmd.extend([str(local_file), remote_dest])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for file transfer
        )

        if result.returncode == 0:
            return f"✓ File uploaded successfully: {local_file} → {remote_dest}"
        else:
            return f"✗ Upload failed: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "Error: Upload timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"


@tool(name="ssh_download", category="ssh", mutating=True)
def ssh_download(
    host: Annotated[str, "SSH host (user@hostname or hostname)"],
    remote_path: Annotated[str, "Remote file path to download"],
    local_path: Annotated[str, "Local destination path"],
    port: Annotated[int, "SSH port (default: 22)"] = 22,
    identity_file: Annotated[str, "Path to SSH private key"] = "",
) -> str:
    """Download a file from remote host via SCP.

    Args:
        host: Remote host in format user@hostname or just hostname
        remote_path: Path to file on remote host
        local_path: Local destination path
        port: SSH port number (default: 22)
        identity_file: Optional path to SSH private key

    Returns:
        Download status message

    Example:
        ssh_download("user@server", "/var/log/app.log", "/tmp/app.log")
        ssh_download("root@192.168.1.1", "/etc/config.yaml", "./config.yaml")
    """
    try:
        local_file = Path(local_path).expanduser()
        local_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["scp", "-P", str(port), "-o", "ConnectTimeout=10"]

        if identity_file:
            cmd.extend(["-i", str(Path(identity_file).expanduser())])

        # Format: scp [options] user@host:source destination
        remote_source = f"{host}:{remote_path}"
        cmd.extend([remote_source, str(local_file)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for file transfer
        )

        if result.returncode == 0:
            return f"✓ File downloaded successfully: {remote_source} → {local_file}"
        else:
            return f"✗ Download failed: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "Error: Download timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"


@tool(name="ssh_list", category="ssh")
def ssh_list(
    host: Annotated[str, "SSH host (user@hostname or hostname)"],
    remote_path: Annotated[str, "Remote directory path"] = ".",
    port: Annotated[int, "SSH port (default: 22)"] = 22,
    identity_file: Annotated[str, "Path to SSH private key"] = "",
) -> str:
    """List files in a remote directory via SSH.

    Args:
        host: Remote host in format user@hostname or just hostname
        remote_path: Path to directory on remote host (default: current directory)
        port: SSH port number (default: 22)
        identity_file: Optional path to SSH private key

    Returns:
        Directory listing from remote host

    Example:
        ssh_list("user@server", "/tmp")
        ssh_list("root@192.168.1.1", "/var/log")
    """
    return ssh_exec(
        host=host,
        command=f"ls -la '{remote_path}'",
        port=port,
        identity_file=identity_file,
        timeout=30
    )

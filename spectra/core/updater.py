"""Auto-update mechanism for Spectra.

Checks for updates from GitHub and provides one-click update functionality.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..core.config import SpectraConfig
from ..core.logging import log_debug, log_error, log_info, log_warn

# A publishable sha256 is 64 hex chars. "pending" / "" mean the release
# pipeline has not stamped a checksum yet.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_publishable_hash(value: str) -> bool:
    """True when `value` is a real 64-hex sha256 (not "" / "pending")."""
    return bool(_SHA256_RE.match((value or "").strip().lower()))


@dataclass
class UpdateInfo:
    """Update information."""

    current_version: str
    latest_version: str
    download_url: str
    changelog: list[str]
    min_compatible_version: str
    update_required: bool
    is_newer: bool
    sha256: str = ""


class Updater:
    """Spectra auto-updater.

    Checks for updates from GitHub and handles the update process.
    """

    UPDATE_URL = "https://raw.githubusercontent.com/alicangnll/Spectra/main/update.json"
    BACKUP_DIR = ".spectra_backup"

    def __init__(self) -> None:
        """Initialize updater."""
        self.config = SpectraConfig()
        self.current_version = self._get_current_version()

    def _get_current_version(self) -> str:
        """Get current Spectra version."""
        # Try to get from constants
        try:
            from ..constants import PLUGIN_VERSION

            return PLUGIN_VERSION
        except ImportError:
            pass

        # Try to get from config
        if hasattr(self.config, "version"):
            return self.config.version

        # Fallback to hardcoded version — keep in sync with update.json
        return "1.3.9"

    def check_for_updates(self, timeout: int = 30, max_retries: int = 3) -> UpdateInfo | None:
        """Check for updates from GitHub.

        Args:
            timeout: Request timeout in seconds (default: 30)
            max_retries: Number of retry attempts on timeout (default: 3)

        Returns:
            UpdateInfo if update available, None otherwise.
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    log_info(f"Retry attempt {attempt + 1}/{max_retries}...")

                log_info("Checking for updates...")
                log_debug(f"Fetching update info from {self.UPDATE_URL}")

                # Try to use IDA's msg function if available
                try:
                    import ida_kernwin

                    ida_kernwin.msg("[Spectra] Checking for updates...\n")
                except ImportError:
                    pass

                request = urllib.request.Request(
                    self.UPDATE_URL, headers={"User-Agent": f"Spectra/{self.current_version}"}
                )

                with urllib.request.urlopen(request, timeout=timeout) as response:
                    data = json.loads(response.read().decode())

                latest_version = data.get("version", self.current_version)
                download_url = data.get("download_url", "")
                changelog = data.get("changelog", [])
                min_compatible = data.get("min_compatible_version", "1.0.0")
                update_required = data.get("update_required", False)
                sha256 = str(data.get("checksums", {}).get("sha256", "") or "")

                is_newer = self._compare_versions(latest_version, self.current_version) > 0

                update_info = UpdateInfo(
                    current_version=self.current_version,
                    latest_version=latest_version,
                    download_url=download_url,
                    changelog=changelog,
                    min_compatible_version=min_compatible,
                    update_required=update_required,
                    is_newer=is_newer,
                    sha256=sha256,
                )

                if is_newer:
                    log_info(f"Update available: {self.current_version} → {latest_version}")
                    try:
                        import ida_kernwin

                        ida_kernwin.msg(f"[Spectra] Update available: {self.current_version} → {latest_version}\n")
                    except ImportError:
                        pass
                    for item in changelog:
                        log_debug(f"  - {item}")
                else:
                    log_info("Already up to date")
                    try:
                        import ida_kernwin

                        ida_kernwin.msg("[Spectra] Already up to date\n")
                    except ImportError:
                        pass

                return update_info

            except urllib.error.URLError as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    if attempt < max_retries - 1:
                        log_warn(f"Timeout on attempt {attempt + 1}, retrying...")
                        continue
                log_error(f"Failed to check for updates: {e}")
                try:
                    import ida_kernwin

                    ida_kernwin.msg(f"[Spectra] Update check failed: {e}\n")
                except ImportError:
                    pass
                return None
            except Exception as e:
                log_error(f"Error checking for updates: {e}")
                try:
                    import ida_kernwin

                    ida_kernwin.msg(f"[Spectra] Update error: {e}\n")
                except ImportError:
                    pass
                return None

        return None

    @staticmethod
    def verify_checksum(path: Path, expected_sha256: str) -> bool:
        """Verify the sha256 checksum of a downloaded file.

        Returns True when the file matches. An empty or "pending" expected
        hash returns True (nothing to verify against — callers log a warning
        for that case separately via ``_is_publishable_hash``).
        """
        if not _is_publishable_hash(expected_sha256):
            return True
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != expected_sha256.lower():
            log_error(f"Checksum mismatch for {path.name}: expected {expected_sha256}, got {actual}")
            return False
        log_debug(f"Checksum verified for {path.name}")
        return True

    def download_update(
        self,
        update_info: UpdateInfo,
        dest_dir: Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """Download update package with optional progress callback.

        Args:
            update_info: Update information.
            dest_dir: Destination directory. If None, uses temp directory.
            progress_callback: Callable receiving (downloaded_bytes, total_bytes).

        Returns:
            Path to downloaded file, or None if download failed.
        """
        try:
            if dest_dir is None:
                dest_dir = Path(tempfile.gettempdir())
            else:
                dest_dir = Path(dest_dir)

            dest_dir.mkdir(parents=True, exist_ok=True)
            download_path = dest_dir / "spectra_update.zip"

            log_info(f"Downloading update from {update_info.download_url}")

            request = urllib.request.Request(
                update_info.download_url, headers={"User-Agent": f"Spectra/{self.current_version}"}
            )

            with urllib.request.urlopen(request, timeout=300) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0

                with open(download_path, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            try:
                                progress_callback(downloaded, total_size)
                            except Exception as _e:
                                pass

                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            log_debug(f"Download progress: {progress:.1f}%")

            log_info(f"Downloaded to {download_path}")

            # Integrity gate: refuse to hand back a package that does not
            # match the published checksum. A missing/"pending" checksum is
            # tolerated (warned) so pre-release feeds keep working.
            expected = getattr(update_info, "sha256", "")
            if _is_publishable_hash(expected):
                if not self.verify_checksum(download_path, expected):
                    download_path.unlink(missing_ok=True)
                    log_error("Update download failed integrity check — file discarded")
                    return None
            else:
                log_warn("Update package has no published sha256 checksum — skipping integrity verification")

            return download_path

        except Exception as e:
            log_error(f"Failed to download update: {e}")
            return None

    def backup_installation(self) -> bool:
        """Backup current installation.

        Returns:
            True if backup successful, False otherwise.
        """
        try:
            backup_path = Path(self.BACKUP_DIR)
            backup_path.mkdir(parents=True, exist_ok=True)

            # Backup current directory
            current_dir = Path(__file__).parent.parent.parent
            if current_dir.name == "spectra":
                # We're in the package directory
                source_dir = current_dir.parent
            else:
                # We're in the repository root
                source_dir = current_dir

            # Resolve symlinks to backup the actual installation, not the symlink
            if source_dir.is_symlink():
                source_dir = source_dir.resolve()

            backup_name = f"backup_{self.current_version}"
            backup_file = backup_path / f"{backup_name}.tar.gz"

            log_info(f"Creating backup: {backup_file}")
            log_info(f"Backing up directory: {source_dir}")

            subprocess.run(
                ["tar", "-czf", str(backup_file), "-C", str(source_dir.parent), source_dir.name],
                check=True,
                capture_output=True,
            )

            log_info("Backup created successfully")
            return True

        except Exception as e:
            log_error(f"Failed to create backup: {e}")
            return False

    def install_update(self, download_path: Path) -> bool:
        """Install update package.

        Prefers ``git pull`` for git-managed installations (the common case
        when installed via ``install_ida.sh`` symlinks on Linux/macOS).
        Falls back to zip-extract-copy for non-git installations.

        Args:
            download_path: Path to downloaded update package.

        Returns:
            True if installation successful, False otherwise.
        """
        try:
            log_info("Installing update...")

            # Resolve the real installation directory (follow symlinks)
            current_dir = Path(__file__).parent.parent.parent
            if current_dir.name == "spectra":
                source_dir = current_dir.parent
            else:
                source_dir = current_dir

            if source_dir.is_symlink():
                source_dir = source_dir.resolve()
                log_info(f"Resolved symlink to: {source_dir}")

            # ── Strategy 1: git pull (preferred) ──────────────────────
            # When the installation is a git repo AND git is available,
            # `git pull` is the safest method — it handles symlinks,
            # preserves local config, and avoids breaking the repo state.
            # Falls through silently if git is not installed.
            git_dir = source_dir / ".git"
            if git_dir.exists():
                import shutil as _shutil

                git_bin = _shutil.which("git")
                if git_bin is None:
                    log_warn("git not found in PATH — skipping git pull, using zip-extract method")
                else:
                    log_info(f"Git repo detected at {source_dir} — using git pull")
                    try:
                        result = subprocess.run(
                            [git_bin, "-C", str(source_dir), "pull", "--ff-only", "--quiet"],
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        if result.returncode == 0:
                            log_info("git pull succeeded")
                            log_info("Update installed successfully")
                            log_info("Please restart IDA Pro/Binary Ninja for changes to take effect")
                            return True
                        else:
                            log_warn(f"git pull failed (rc={result.returncode}): {result.stderr.strip()}")
                            log_warn("Falling back to zip-extract method")
                    except (OSError, subprocess.SubprocessError) as git_err:
                        log_warn(f"git pull error: {git_err} — falling back to zip-extract method")

            # ── Strategy 2: zip extract + copy (fallback) ─────────────
            # Create backup before destructive copy
            if not self.backup_installation():
                log_warn("Backup failed, proceeding anyway")

            # Extract update zip
            extract_dir = download_path.parent / "extracted"
            extract_dir.mkdir(exist_ok=True)

            log_info("Extracting update package...")
            with zipfile.ZipFile(download_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find Spectra directory root inside extracted zip
            extracted_root = extract_dir
            for root in extract_dir.iterdir():
                if (root / "spectra_plugin.py").exists():
                    extracted_root = root
                    break

            log_info(f"Installing to {source_dir}...")

            # Copy spectra package directory
            spectra_src = extracted_root / "spectra"
            if spectra_src.exists():
                self._copy_directory(spectra_src, source_dir / "spectra")

            # Copy top-level files
            import shutil

            for fname in ("spectra_plugin.py", "update.json"):
                src = extracted_root / fname
                if src.exists():
                    shutil.copy2(src, source_dir / fname)
                    log_info(f"Copied {fname}")

            log_info("Update installed successfully")
            log_info("Please restart IDA Pro/Binary Ninja for changes to take effect")
            return True

        except Exception as e:
            log_error(f"Failed to install update: {e}")
            log_error("You can restore from backup if needed")
            return False

    def _copy_directory(self, src: Path, dst: Path) -> None:
        """Copy directory recursively.

        Args:
            src: Source directory.
            dst: Destination directory.
        """
        import shutil

        log_info(f"Copying directory: {src} -> {dst}")
        log_info(f"Source exists: {src.exists()}, Destination exists: {dst.exists()}")

        # Handle symlinks properly
        if dst.exists():
            log_info(f"Destination type: symlink={dst.is_symlink()}, dir={dst.is_dir()}, file={dst.is_file()}")
            # If it's a symlink, remove it directly
            if dst.is_symlink():
                log_info(f"Removing symlink: {dst}")
                dst.unlink()
            # If it's a directory, remove it
            elif dst.is_dir():
                log_info(f"Removing directory: {dst}")
                shutil.rmtree(dst)
            # If it's a file, remove it
            else:
                log_info(f"Removing file: {dst}")
                dst.unlink()

        # Copy the directory
        log_info(f"Starting copytree from {src} to {dst}")
        shutil.copytree(src, dst, symlinks=True)
        log_info("Copy completed successfully")

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Args:
            v1: First version.
            v2: Second version.

        Returns:
            Positive if v1 > v2, negative if v1 < v2, 0 if equal.
        """

        def parse_version(v: str) -> tuple[int, ...]:
            return tuple(map(int, v.split(".")))

        v1_parts = parse_version(v1)
        v2_parts = parse_version(v2)

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts = v1_parts + (0,) * (max_len - len(v1_parts))
        v2_parts = v2_parts + (0,) * (max_len - len(v2_parts))

        if v1_parts > v2_parts:
            return 1
        elif v1_parts < v2_parts:
            return -1
        else:
            return 0

    def restore_backup(self) -> bool:
        """Restore from backup.

        Returns:
            True if restoration successful, False otherwise.
        """
        try:
            backup_path = Path(self.BACKUP_DIR)
            backups = list(backup_path.glob("backup_*.tar.gz"))

            if not backups:
                log_error("No backups found")
                return False

            # Use the most recent backup
            latest_backup = max(backups, key=lambda p: p.stat().st_mtime)

            log_info(f"Restoring from {latest_backup}")

            current_dir = Path(__file__).parent.parent.parent
            if current_dir.name == "spectra":
                source_dir = current_dir.parent
            else:
                source_dir = current_dir

            # Resolve symlinks to restore to the actual location
            if source_dir.is_symlink():
                source_dir = source_dir.resolve()

            log_info(f"Restoring to: {source_dir}")

            # Extract backup
            subprocess.run(
                ["tar", "-xzf", str(latest_backup), "-C", str(source_dir.parent)],
                check=True,
                capture_output=True,
            )

            log_info("Backup restored successfully")
            log_info("Please restart IDA Pro/Binary Ninja")
            return True

        except Exception as e:
            log_error(f"Failed to restore backup: {e}")
            return False


def check_for_updates() -> UpdateInfo | None:
    """Check for Spectra updates.

    Returns:
        UpdateInfo if update available, None otherwise.
    """
    updater = Updater()
    return updater.check_for_updates()


def install_update(update_info: UpdateInfo) -> bool:
    """Install Spectra update.

    Args:
        update_info: Update information.

    Returns:
        True if installation successful, False otherwise.
    """
    updater = Updater()

    # Download update
    download_path = updater.download_update(update_info)
    if download_path is None:
        return False

    # Install update
    return updater.install_update(download_path)


def restore_backup() -> bool:
    """Restore Spectra from backup.

    Returns:
        True if restoration successful, False otherwise.
    """
    updater = Updater()
    return updater.restore_backup()

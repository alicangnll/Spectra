"""Auto-update mechanism for Spectra.

Checks for updates from GitHub and provides one-click update functionality.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..core.config import SpectraConfig
from ..core.logging import log_debug, log_error, log_info, log_warn


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


class Updater:
    """Spectra auto-updater.

    Checks for updates from GitHub and handles the update process.
    """

    UPDATE_URL = "https://raw.githubusercontent.com/alicangnll/Spectra/main/update.json"
    BACKUP_DIR = ".spectra_backup"

    def __init__(self):
        """Initialize updater."""
        self.config = SpectraConfig()
        self.current_version = self._get_installed_version()

    def _get_installed_version(self) -> str:
        """Get the actually installed version, independent of update.json.

        This method tries multiple sources to determine the REAL version
        that is currently running, not what's written in update.json.

        Returns:
            The installed version string.
        """
        # Priority 1: Git tag (most reliable for git installations)
        version = self._get_version_from_git()
        if version and version != "unknown":
            log_debug(f"Installed version from git: {version}")
            return version

        # Priority 2: Check if there's a version marker file
        # This file should only be updated by the installer or update process
        version = self._get_version_from_marker_file()
        if version:
            log_debug(f"Installed version from marker file: {version}")
            return version

        # Priority 3: Try to parse from plugin file metadata
        version = self._get_version_from_metadata()
        if version:
            log_debug(f"Installed version from metadata: {version}")
            return version

        # Priority 4: Constants fallback (may read from update.json - use with caution)
        # We add a checksum check to detect if update.json was manually modified
        try:
            from ..constants import PLUGIN_VERSION
            log_debug(f"Installed version from constants (fallback): {PLUGIN_VERSION}")
            return PLUGIN_VERSION
        except ImportError:
            pass

        # Last resort: hardcoded fallback
        log_warn("Could not determine installed version, using hardcoded fallback")
        return "1.2.2"

    def _get_version_from_git(self) -> str:
        """Get version from git tags.

        Returns:
            Version string or "unknown" if not a git repo or no tags.
        """
        import subprocess as _subprocess
        import shutil as _shutil

        try:
            source_dir = Path(__file__).parent.parent.parent
            if source_dir.name == "spectra":
                source_dir = source_dir.parent

            # Resolve symlinks to get the real git repo
            if source_dir.is_symlink():
                source_dir = source_dir.resolve()

            git_dir = source_dir / ".git"
            if not git_dir.exists():
                return "unknown"

            git_bin = _shutil.which("git")
            if not git_bin:
                return "unknown"

            # Try git describe --tags --abbrev=0 to get the most recent tag
            result = _subprocess.run(
                [git_bin, "-C", str(source_dir), "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                tag = result.stdout.strip()
                # Remove 'v' prefix if present (e.g., v1.3.1 -> 1.3.1)
                if tag.startswith("v"):
                    tag = tag[1:]
                return tag

        except Exception as e:
            log_debug(f"Git version detection failed: {e}")

        return "unknown"

    def _get_version_from_marker_file(self) -> str:
        """Get version from .version marker file.

        This file is created/updated only by the installer or update process,
        not by manual edits to update.json.

        Returns:
            Version string or empty string if file doesn't exist.
        """
        try:
            source_dir = Path(__file__).parent.parent.parent
            if source_dir.name == "spectra":
                source_dir = source_dir.parent

            version_file = source_dir / ".version"
            if version_file.exists():
                with open(version_file, "r") as f:
                    version = f.read().strip()
                    if version:
                        return version
        except Exception as e:
            log_debug(f"Failed to read version marker file: {e}")

        return ""

    def _get_version_from_metadata(self) -> str:
        """Get version from __version__ attribute or package metadata.

        Returns:
            Version string or empty string if not found.
        """
        try:
            # Try to get from __version__ if it exists
            import spectra
            if hasattr(spectra, "__version__"):
                return spectra.__version__
        except Exception as e:
            log_debug(f"Failed to get version from metadata: {e}")

        return ""

    def _get_current_version(self) -> str:
        """Get current Spectra version from multiple sources in priority order.

        Priority:
        1. Git tag/describe (most accurate for git installations)
        2. Local update.json (fallback, but may be stale after manual edits)
        3. Constants fallback version (last resort)
        """
        # Priority 1: Try git describe for git installations
        import subprocess as _subprocess
        try:
            source_dir = Path(__file__).parent.parent.parent
            if source_dir.name == "spectra":
                source_dir = source_dir.parent

            # Resolve symlinks to get the real git repo
            if source_dir.is_symlink():
                source_dir = source_dir.resolve()

            git_dir = source_dir / ".git"
            if git_dir.exists():
                import shutil as _shutil
                git_bin = _shutil.which("git")
                if git_bin:
                    # Try git describe --tags to get version from git tags
                    result = _subprocess.run(
                        [git_bin, "-C", str(source_dir), "describe", "--tags", "--abbrev=0"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        tag = result.stdout.strip()
                        # Remove 'v' prefix if present (e.g., v1.3.1 -> 1.3.1)
                        if tag.startswith("v"):
                            tag = tag[1:]
                        log_debug(f"Version from git tag: {tag}")
                        return tag
        except Exception as e:
            log_debug(f"Git version detection failed: {e}")

        # Priority 2: Try constants.py (reads from local update.json)
        try:
            from ..constants import PLUGIN_VERSION
            # Only use this if we can verify it's not the same as remote
            # This prevents the circular dependency issue
            log_debug(f"Version from constants: {PLUGIN_VERSION}")
            return PLUGIN_VERSION
        except ImportError:
            pass

        # Priority 3: Fallback to hardcoded version (use the last known stable version)
        log_warn("Could not determine version, using fallback")
        return "1.2.2"

    def check_for_updates(self, timeout: int = 10, force_check: bool = False) -> UpdateInfo | None:
        """Check for updates from GitHub.

        Args:
            timeout: Request timeout in seconds.
            force_check: If True, bypass cached results and force re-check.

        Returns:
            UpdateInfo if update available, None otherwise.
        """
        """Check for updates from GitHub.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            UpdateInfo if update available, None otherwise.
        """
        try:
            log_info("Checking for updates...")
            log_debug(f"Fetching update info from {self.UPDATE_URL}")

            # Try to use IDA's msg function if available
            try:
                import ida_kernwin

                ida_kernwin.msg("[Spectra] Checking for updates...\n")
            except ImportError:
                pass

            request = urllib.request.Request(self.UPDATE_URL, headers={"User-Agent": f"Spectra/{self.current_version}"})

            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode())

            latest_version = data.get("version", self.current_version)
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", [])
            min_compatible = data.get("min_compatible_version", "1.0.0")
            update_required = data.get("update_required", False)

            # More robust version comparison
            # Log what we're comparing for debugging
            log_info(f"Version comparison: installed={self.current_version}, latest={latest_version}")
            is_newer = self._compare_versions(latest_version, self.current_version) > 0

            # Always consider updates if versions differ, even if installed seems newer
            # This handles cases where local update.json was manually updated ahead of actual code
            is_different = latest_version != self.current_version

            update_info = UpdateInfo(
                current_version=self.current_version,
                latest_version=latest_version,
                download_url=download_url,
                changelog=changelog,
                min_compatible_version=min_compatible,
                update_required=update_required,
                is_newer=is_newer,
            )

            if is_newer:
                log_info(f"Update available: {self.current_version} → {latest_version}")
                try:
                    import ida_kernwin

                    ida_kernwin.msg(f"[Spectra] Update available: {self.current_version} → {latest_version}\n")
                except ImportError:
                    pass
                for item in changelog[:5]:  # Show first 5 changelog items
                    log_debug(f"  - {item}")
            else:
                log_info(f"Already up to date (current: {self.current_version}, latest: {latest_version})")
                try:
                    import ida_kernwin

                    ida_kernwin.msg(f"[Spectra] Already up to date ({self.current_version})\n")
                except ImportError:
                    pass

            return update_info

        except urllib.error.URLError as e:
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
                            # Update version marker file to reflect new version
                            self._update_version_marker(latest_version=update_info.latest_version)
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

            # Update version marker file
            self._update_version_marker(extracted_root)

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

    def _update_version_marker(self, latest_version: str = None, extracted_root: Path = None) -> None:
        """Update the .version marker file after a successful update.

        This file stores the actual installed version, separate from update.json,
        to break the circular dependency where update.json is used both as
        current version source AND update target.

        Args:
            latest_version: The new version to write. If None, reads from extracted_root.
            extracted_root: Path to extracted update directory (alternative source).
        """
        try:
            # Determine the version to write
            if extracted_root:
                # Read from the extracted update.json
                extracted_update_json = extracted_root / "update.json"
                if extracted_update_json.exists():
                    with open(extracted_update_json, "r") as f:
                        update_data = json.load(f)
                        version = update_data.get("version", latest_version or "unknown")
                else:
                    version = latest_version or "unknown"
            else:
                version = latest_version or "unknown"

            # Write to .version file in the source directory
            source_dir = Path(__file__).parent.parent.parent
            if source_dir.name == "spectra":
                source_dir = source_dir.parent

            # Resolve symlinks
            if source_dir.is_symlink():
                source_dir = source_dir.resolve()

            version_file = source_dir / ".version"
            with open(version_file, "w") as f:
                f.write(version)

            log_info(f"Updated version marker: {version_file} → {version}")

        except Exception as e:
            log_warn(f"Failed to update version marker: {e}")

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

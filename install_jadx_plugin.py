#!/usr/bin/env python3
"""
Spectra JADX Plugin Installer

Automatically installs Spectra as a JADX plugin.
Supports Linux, macOS, and Windows.
"""

import os
import shutil
import sys
import json
import platform
from pathlib import Path

__version__ = "1.0.0"


def get_jadx_plugin_dir() -> Path:
    """Find JADX plugin directory."""

    # Check for JADX in common locations
    possible_paths = [
        Path.home() / ".jadx" / "plugins",
        Path("/usr/local/share/jadx/plugins"),
        Path("/opt/jadx/plugins"),
        Path.home() / "AppData" / "Local" / "jadx" / "plugins",  # Windows
    ]

    for path in possible_paths:
        if path.exists() or path.parent.exists():
            return path

    # Default to ~/.jadx/plugins
    default_path = Path.home() / ".jadx" / "plugins"
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path


def install_plugin() -> int:
    """Install Spectra as JADX plugin."""

    print("="*60)
    print("  Spectra JADX Plugin Installer")
    print("="*60)

    # Get current directory (Spectra root)
    spectra_root = Path(__file__).parent.absolute()
    plugin_dir = get_jadx_plugin_dir()

    # Create plugin directory
    spectra_plugin_dir = plugin_dir / "spectra"
    spectra_plugin_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Installing to: {spectra_plugin_dir}")

    # Copy main script
    script_source = spectra_root / "spectra_jadx.py"
    script_dest = spectra_plugin_dir / "spectra_jadx.py"

    if script_source.exists():
        shutil.copy2(script_source, script_dest)
        print(f"✅ Copied: spectra_jadx.py")
    else:
        print(f"❌ Error: {script_source} not found")
        return 1

    # Copy spectra module
    spectra_module_source = spectra_root / "spectra"
    spectra_module_dest = spectra_plugin_dir / "spectra"

    if spectra_module_source.exists():
        if spectra_module_dest.exists():
            shutil.rmtree(spectra_module_dest)
        shutil.copytree(spectra_module_source, spectra_module_dest)
        print(f"✅ Copied: spectra/ module")
    else:
        print(f"❌ Error: {spectra_module_source} not found")
        return 1

    # Create plugin.json
    plugin_config = {
        "name": "Spectra",
        "version": __version__,
        "description": "AI-powered Android APK analysis assistant",
        "author": "Ali Can Gönüllü",
        "main": "spectra_jadx.py",
        "enabled": True,
        "dependencies": [
            "anthropic>=0.18.0",
            "httpx>=0.24.0"
        ],
        "capabilities": [
            "apk_analysis",
            "string_search",
            "manifest_parsing",
            "security_assessment",
            "native_library_detection",
            "interactive_mode"
        ]
    }

    config_path = spectra_plugin_dir / "plugin.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(plugin_config, f, indent=2, ensure_ascii=False)
    print(f"✅ Created: plugin.json")

    # Create default config
    default_config = {
        "auto_analyze": True,
        "ai_provider": "anthropic",
        "api_key": "",
        "max_tokens": 8192,
        "security_checks": {
            "permissions": True,
            "hardcoded_secrets": True,
            "network_security": True,
            "native_libraries": True,
            "debuggable_check": True,
            "backup_check": True
        }
    }

    config_file_path = spectra_plugin_dir / "config.json"
    with open(config_file_path, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    print(f"✅ Created: config.json")

    # Create README
    readme_content = """# Spectra JADX Plugin

AI-powered Android APK analysis assistant for JADX decompiler.

## Usage

### From JADX GUI:
Tools → Spectra → Analyze APK

### From CLI:
```bash
python spectra_jadx.py analyze app.apk -o output
python spectra_jadx.py search app.apk "API_KEY"
python spectra_jadx.py interactive app.apk
```

## Features

- Automatic APK decompilation and analysis
- String search for API keys, endpoints, credentials
- AndroidManifest parsing and permission analysis
- Native library detection
- Security assessment
- Interactive AI mode

## Configuration

Edit `config.json` to customize:
- AI provider (anthropic, openai, etc.)
- API keys
- Security check preferences
- Analysis options

## Requirements

- JADX 1.4.7+
- Python 3.10+
- anthropic>=0.18.0
- httpx>=0.24.0

## Support

For issues and updates:
https://github.com/alicangnll/Spectra
"""

    readme_path = spectra_plugin_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"✅ Created: README.md")

    print("\n" + "="*60)
    print("  Installation Complete!")
    print("="*60)
    print(f"\n📦 Plugin installed to: {spectra_plugin_dir}")
    print(f"🔧 Plugin config: {config_file_path}")
    print(f"\n📖 Next steps:")
    print(f"   1. Configure API key in: {config_file_path}")
    print(f"   2. Restart JADX if running")
    print(f"   3. Check Tools → Spectra menu in JADX GUI")
    print(f"\n📚 Documentation: See README.md in plugin directory")

    return 0


def uninstall_plugin() -> int:
    """Uninstall Spectra JADX plugin."""

    print("="*60)
    print("  Spectra JADX Plugin Uninstaller")
    print("="*60)

    plugin_dir = get_jadx_plugin_dir()
    spectra_plugin_dir = plugin_dir / "spectra"

    if not spectra_plugin_dir.exists():
        print("❌ Spectra plugin not found")
        return 1

    print(f"\n🗑️  Removing: {spectra_plugin_dir}")

    try:
        shutil.rmtree(spectra_plugin_dir)
        print("✅ Plugin uninstalled successfully")
        return 0
    except Exception as e:
        print(f"❌ Error uninstalling: {e}")
        return 1


def main() -> int:
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Install/uninstall Spectra as JADX plugin"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall the plugin"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    if args.uninstall:
        return uninstall_plugin()
    else:
        return install_plugin()


if __name__ == "__main__":
    sys.exit(main())
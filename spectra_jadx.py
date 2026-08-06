#!/usr/bin/env python3
"""
Spectra JADX Plugin - Hybrid Android APK Analysis Assistant

This script works in multiple modes:
1. **Standalone CLI**: Direct execution from terminal
2. **IDA Pro Plugin**: Integrated with IDA Pro's Spectra
3. **Binary Ninja Plugin**: Integrated with Binary Ninja's Spectra
4. **JADX Plugin**: Loadable inside JADX as a native plugin

Usage:
    # Standalone CLI
    python spectra_jadx.py analyze app.apk -o ./decompiled

    # As JADX plugin (after installation)
    jadx --plugin spectra app.apk -d output
    # Or from JADX GUI: Tools → Spectra → Analyze APK

Requirements:
    - JADX: https://github.com/skylot/jadx
    - Python 3.10+
    - Spectra dependencies (for IDA/BN integration)

Author: Ali Can Gönüllü
License: MIT
Version: 1.2.5
"""

__version__ = "1.2.5"
__author__ = "Ali Can Gönüllü"

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add Spectra to path
spectra_path = Path(__file__).parent
sys.path.insert(0, str(spectra_path))

# Try to import Spectra components
try:
    from spectra.jadx import JadxAnalyzer
    SPECTRA_AVAILABLE = True
except ImportError:
    SPECTRA_AVAILABLE = False
    print("Warning: Spectra core not available, running in standalone mode")

# Detect execution environment
ENV_STANDALONE = "standalone"
ENV_IDA = "ida"
ENV_BINARY_NINJA = "binary_ninja"
ENV_JADX = "jadx"

def detect_environment() -> str:
    """Detect current execution environment."""

    # Check if running inside JADX
    if "--jadx-plugin" in sys.argv or os.path.exists(".jadx_plugin_mode"):
        return ENV_JADX

    # Check if running inside IDA Pro
    try:
        import idaapi
        if "get_path" in dir(idaapi):
            return ENV_IDA
    except ImportError:
        pass

    # Check if running inside Binary Ninja
    try:
        import binaryninja
        if "BinaryView" in dir(binaryninja):
            return ENV_BINARY_NINJA
    except ImportError:
        pass

    # Default to standalone
    return ENV_STANDALONE

CURRENT_ENV = detect_environment()


class JadxPluginWrapper:
    """JADX plugin wrapper for Spectra integration."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.config_file = self.plugin_dir / "config.json"
        self.config = self._load_config()
        self.analyzer = None

    def _load_config(self) -> Dict[str, Any]:
        """Load plugin configuration."""
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

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")

        return default_config

    def get_plugin_info(self) -> Dict[str, Any]:
        """Return plugin metadata for JADX."""
        return {
            "name": "Spectra",
            "version": __version__,
            "description": "AI-powered Android APK analysis assistant",
            "author": "Ali Can Gönüllü",
            "capabilities": [
                "apk_analysis",
                "string_search",
                "manifest_parsing",
                "security_assessment",
                "native_library_detection",
                "interactive_mode",
                "ida_integration",
                "binary_ninja_integration"
            ],
            "environment": CURRENT_ENV,
            "spectra_available": SPECTRA_AVAILABLE
        }

    def initialize(self) -> bool:
        """Initialize plugin based on environment."""
        try:
            if SPECTRA_AVAILABLE:
                self.analyzer = JadxAnalyzer()
                return True
            else:
                print("Warning: Spectra core not available, limited functionality")
                return False
        except Exception as e:
            print(f"Plugin initialization error: {e}")
            return False

    def analyze_apk(self, apk_path: str, output_dir: str = None) -> Dict[str, Any]:
        """Analyze APK with full security assessment."""
        if not self.analyzer:
            return {"error": "Plugin not initialized"}

        try:
            # Set default output directory
            if not output_dir:
                output_dir = str(Path(apk_path).parent / f"{Path(apk_path).stem}_spectra_analysis")

            # Decompile
            decompiled_dir = self.analyzer.decompile_apk(apk_path, output_dir)

            # Run comprehensive analysis
            results = {
                "apk_path": apk_path,
                "decompiled_dir": decompiled_dir,
                "structure": self.analyzer.get_package_structure(decompiled_dir),
                "manifest": self.analyzer.find_android_manifest(decompiled_dir),
                "native_libs": self.analyzer.find_native_libraries(decompiled_dir),
                "security_assessment": self._run_security_checks(decompiled_dir),
                "environment": CURRENT_ENV
            }

            return results

        except Exception as e:
            return {"error": str(e)}

    def _run_security_checks(self, decompiled_dir: str) -> Dict[str, Any]:
        """Run comprehensive security checks."""
        assessment = {
            "permissions": [],
            "hardcoded_secrets": [],
            "network_security": [],
            "native_libraries": [],
            "debuggable": False,
            "backup_enabled": False,
            "exported_components": [],
            "risk_score": 0
        }

        try:
            # Check manifest for debuggable and backup
            manifest = self.analyzer.find_android_manifest(decompiled_dir)
            application = manifest.get("application", {})

            assessment["debuggable"] = application.get("debuggable", False)
            assessment["backup_enabled"] = application.get("allowBackup", False)

            # Check dangerous permissions
            dangerous_perms = [
                "android.permission.INTERNET",
                "android.permission.READ_EXTERNAL_STORAGE",
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.CAMERA",
                "android.permission.RECORD_AUDIO",
                "android.permission.SEND_SMS",
                "android.permission.READ_SMS",
                "android.permission.CALL_PHONE",
                "android.permission.ACCESS_COARSE_LOCATION",
                "android.permission.READ_CONTACTS",
                "android.permission.WRITE_EXTERNAL_STORAGE"
            ]

            permissions = manifest.get("permissions", [])
            assessment["permissions"] = [p for p in permissions if p in dangerous_perms]

            # Search for hardcoded secrets
            secret_patterns = ["api_key", "apikey", "API_KEY", "secret", "token", "password"]
            for pattern in secret_patterns:
                matches = self.analyzer.search_string_in_sources(decompiled_dir, pattern)
                if matches:
                    assessment["hardcoded_secrets"].extend(matches)

            # Calculate risk score
            risk_score = 0
            if assessment["debuggable"]:
                risk_score += 30
            if assessment["backup_enabled"]:
                risk_score += 10
            if len(assessment["permissions"]) > 5:
                risk_score += 20
            if len(assessment["hardcoded_secrets"]) > 0:
                risk_score += 40

            assessment["risk_score"] = min(risk_score, 100)

        except Exception as e:
            assessment["error"] = str(e)

        return assessment


# ============================================================================
# CLI Interface (unchanged for backward compatibility)
# ============================================================================

def print_section(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_json(data: dict, pretty: bool = True) -> None:
    """Print JSON data."""
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data))


def cmd_analyze(args) -> int:
    """Analyze APK structure and components."""
    print_section("Analyzing APK")

    try:
        # Use plugin wrapper for unified functionality
        plugin = JadxPluginWrapper()

        if not plugin.initialize():
            print("Error: Failed to initialize plugin")
            return 1

        results = plugin.analyze_apk(args.apk, args.output)

        if "error" in results:
            print(f"Error: {results['error']}")
            return 1

        print(f"Decompiled to: {results['decompiled_dir']}")
        print(f"\nPackage Structure:")
        print_json(results['structure'])

        print(f"\nAndroidManifest:")
        print_json(results['manifest'])

        print(f"\nSecurity Assessment:")
        print_json(results['security_assessment'])

        if args.export:
            plugin.analyzer.export_to_json(results['decompiled_dir'], args.export)
            print(f"\nAnalysis exported to: {args.export}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_search(args) -> int:
    """Search for strings in decompiled sources."""
    print_section(f"Searching: {args.pattern}")

    try:
        plugin = JadxPluginWrapper()

        if not plugin.initialize():
            print("Error: Failed to initialize plugin")
            return 1

        # Decompile if needed
        if args.decompiled_dir and os.path.exists(args.decompiled_dir):
            decompiled_dir = args.decompiled_dir
        else:
            output_dir = args.output or "/tmp/jadx_output"
            decompiled_dir = plugin.analyzer.decompile_apk(args.apk, output_dir)

        matches = plugin.analyzer.search_string_in_sources(decompiled_dir, args.pattern)

        if matches:
            print(f"Found {len(matches)} matches:")
            for i, match in enumerate(matches[:50], 1):
                print(f"\n{i}. {match['file']}:{match['line']}")
                print(f"   {match['content'][:100]}")

            if len(matches) > 50:
                print(f"\n... and {len(matches) - 50} more matches")
        else:
            print("No matches found")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_structure(args) -> int:
    """Show package structure."""
    print_section("Package Structure Analysis")

    try:
        plugin = JadxPluginWrapper()

        if not plugin.initialize():
            print("Error: Failed to initialize plugin")
            return 1

        if args.decompiled_dir and os.path.exists(args.decompiled_dir):
            structure = plugin.analyzer.get_package_structure(args.decompiled_dir)
        else:
            output_dir = args.output or "/tmp/jadx_output"
            decompiled_dir = plugin.analyzer.decompile_apk(args.apk, output_dir)
            structure = plugin.analyzer.get_package_structure(decompiled_dir)

        print_json(structure)
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_class(args) -> int:
    """Analyze specific class."""
    print_section(f"Class Analysis: {args.class_name}")

    try:
        plugin = JadxPluginWrapper()

        if not plugin.initialize():
            print("Error: Failed to initialize plugin")
            return 1

        if args.decompiled_dir and os.path.exists(args.decompiled_dir):
            decompiled_dir = args.decompiled_dir
        else:
            output_dir = args.output or "/tmp/jadx_output"
            decompiled_dir = plugin.analyzer.decompile_apk(args.apk, output_dir)

        analysis = plugin.analyzer.get_class_dependencies(decompiled_dir, args.class_name)

        if "error" in analysis:
            print(f"Error: {analysis['error']}")
            return 1

        print(f"Class: {analysis['class_name']}")
        if analysis.get('extends'):
            print(f"Extends: {analysis['extends']}")
        if analysis.get('implements'):
            print(f"Implements: {', '.join(analysis['implements'])}")

        print(f"\nImports ({len(analysis['imports'])}):")
        for imp in analysis['imports'][:20]:
            print(f"  - {imp}")

        print(f"\nMethods ({len(analysis['methods'])}):")
        for method in analysis['methods'][:20]:
            print(f"  - {method}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_interactive(args) -> int:
    """Interactive AI mode."""
    print_section("Spectra Interactive Mode")

    try:
        plugin = JadxPluginWrapper()

        if not plugin.initialize():
            print("Error: Failed to initialize plugin")
            return 1

        # Decompile APK
        output_dir = args.output or "/tmp/jadx_output"
        decompiled_dir = plugin.analyzer.decompile_apk(args.apk, output_dir)

        # Get context
        structure = plugin.analyzer.get_package_structure(decompiled_dir)
        manifest = plugin.analyzer.find_android_manifest(decompiled_dir)

        context = {
            "apk": args.apk,
            "decompiled_dir": decompiled_dir,
            "structure": structure,
            "manifest": manifest,
            "environment": CURRENT_ENV
        }

        print(f"APK: {Path(args.apk).name}")
        print(f"Total classes: {structure['total_classes']}")
        print(f"Total methods: {structure['total_methods']}")
        print(f"Environment: {CURRENT_ENV}")

        if CURRENT_ENV != ENV_STANDALONE:
            print(f"\nIntegration: Active with {CURRENT_ENV.upper()}")

        print("\nYou can ask questions like:")
        print("  - 'What are the main entry points?'")
        print("  - 'Show me all permissions'")
        print("  - 'Find crypto API usage'")
        print("\nType 'quit' to exit\n")

        # Simple interactive loop
        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                # Process question
                print(f"\nSpectra: Processing '{user_input}'...")
                response = process_basic_question(user_input, context, plugin)
                print(f"Spectra: {response}\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def process_basic_question(question: str, context: dict, plugin: JadxPluginWrapper) -> str:
    """Process basic questions about APK."""

    question_lower = question.lower()

    # Entry points
    if 'entry point' in question_lower or 'main activity' in question_lower:
        manifest = context['manifest']
        if manifest.get('activities'):
            main_activity = manifest['activities'][0]
            return f"Main entry point: {main_activity}. This is the first activity launched when the app starts."

    # Permissions
    if 'permission' in question_lower:
        manifest = context['manifest']
        perms = manifest.get('permissions', [])
        return f"App requests {len(perms)} permissions. Key permissions: {', '.join(perms[:5])}"

    # Native libraries
    if 'native' in question_lower or r'\.so' in question_lower or 'so file' in question_lower:
        native_libs = plugin.analyzer.find_native_libraries(context['decompiled_dir'])
        if native_libs:
            return f"Found {len(native_libs)} native libraries: {', '.join(native_libs)}"
        else:
            return "No native libraries found in this APK."

    # Security
    if 'security' in question_lower or 'vulnerab' in question_lower:
        assessment = plugin._run_security_checks(context['decompiled_dir'])
        risk = assessment.get('risk_score', 0)
        if risk > 50:
            return f"High risk score: {risk}/100. Issues: debuggable={assessment['debuggable']}, backup={assessment['backup_enabled']}"
        else:
            return f"Risk score: {risk}/100. App appears to have basic security measures."

    # Network
    if 'network' in question_lower or 'http' in question_lower or 'api' in question_lower:
        matches = plugin.analyzer.search_string_in_sources(context['decompiled_dir'], 'http')
        if matches:
            return f"Found {len(matches)} HTTP/HTTPS endpoints in the code."
        else:
            return "No obvious HTTP endpoints found in source code."

    # Default response
    return "I can analyze the APK structure, permissions, native libraries, and security aspects. Try asking about specific aspects."


def cmd_plugin_info(args) -> int:
    """Show plugin information."""
    plugin = JadxPluginWrapper()
    info = plugin.get_plugin_info()

    print_section("Spectra JADX Plugin Info")
    print_json(info)

    return 0


def main() -> int:
    """Main entry point with environment detection."""

    # Detect environment
    CURRENT_ENV = detect_environment()

    # JADX plugin mode
    if CURRENT_ENV == ENV_JADX:
        print("Spectra JADX Plugin Mode")
        # Handle JADX-specific plugin initialization
        if "--jadx-init" in sys.argv:
            plugin = JadxPluginWrapper()
            info = plugin.get_plugin_info()
            print(f"Loaded: {info['name']} v{info['version']}")
            return 0

        if "--jadx-analyze" in sys.argv:
            # Extract APK path from JADX arguments
            apk_idx = sys.argv.index("--jadx-analyze") + 1
            if apk_idx < len(sys.argv):
                apk_path = sys.argv[apk_idx]
                plugin = JadxPluginWrapper()
                plugin.initialize()
                results = plugin.analyze_apk(apk_path)
                print_json(results)
                return 0

    # Standard CLI mode
    parser = argparse.ArgumentParser(
        description="Spectra JADX Plugin - Hybrid Android APK Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze app.apk -o ./decompiled
  %(prog)s search app.apk "API_KEY"
  %(prog)s structure app.apk
  %(prog)s class app.apk com.example.MainActivity
  %(prog)s interactive app.apk

Environment: {}
        """.format(CURRENT_ENV.upper())
    )

    parser.add_argument("--jadx", default="jadx", help="JADX executable path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze APK structure")
    analyze_parser.add_argument("apk", help="APK file path")
    analyze_parser.add_argument("-o", "--output", help="Output directory")
    analyze_parser.add_argument("--no-resources", action="store_true", help="Don't export resources")
    analyze_parser.add_argument("--export", help="Export analysis to JSON file")
    analyze_parser.add_argument("--decompiled-dir", help="Use existing decompiled directory")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search strings in sources")
    search_parser.add_argument("apk", help="APK file path")
    search_parser.add_argument("pattern", help="Search pattern")
    search_parser.add_argument("-o", "--output", help="Output directory")
    search_parser.add_argument("--decompiled-dir", help="Use existing decompiled directory")
    search_parser.add_argument("--case-sensitive", action="store_true", help="Case sensitive search")

    # Structure command
    structure_parser = subparsers.add_parser("structure", help="Show package structure")
    structure_parser.add_argument("apk", help="APK file path")
    structure_parser.add_argument("-o", "--output", help="Output directory")
    structure_parser.add_argument("--export", help="Export structure to JSON")
    structure_parser.add_argument("--decompiled-dir", help="Use existing decompiled directory")

    # Class command
    class_parser = subparsers.add_parser("class", help="Analyze specific class")
    class_parser.add_argument("apk", help="APK file path")
    class_parser.add_argument("class_name", help="Fully qualified class name")
    class_parser.add_argument("-o", "--output", help="Output directory")
    class_parser.add_argument("--decompiled-dir", help="Use existing decompiled directory")

    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Interactive AI mode")
    interactive_parser.add_argument("apk", help="APK file path")
    interactive_parser.add_argument("-o", "--output", help="Output directory")

    # Plugin info command
    info_parser = subparsers.add_parser("plugin-info", help="Show plugin information")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate command handler
    command_handlers = {
        "analyze": cmd_analyze,
        "search": cmd_search,
        "structure": cmd_structure,
        "class": cmd_class,
        "interactive": cmd_interactive,
        "plugin-info": cmd_plugin_info
    }

    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
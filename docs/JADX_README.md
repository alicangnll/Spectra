# Spectra JADX Plugin - Hybrid Android APK Analysis System

Spectra's multi-mode Android APK analysis system that works as:
- **Standalone CLI tool** - Independent analysis from terminal
- **IDA Pro integration** - Embedded within IDA Pro's Spectra
- **Binary Ninja integration** - Embedded within Binary Ninja's Spectra
- **JADX native plugin** - Loadable inside JADX Decompiler

## Features

**Comprehensive APK Analysis:**
- Decompile APKs to Java source code using JADX
- Analyze package structure and components
- Parse AndroidManifest.xml and extract metadata
- Search strings in decompiled code (API keys, endpoints, credentials)
- Find native libraries (.so files) and detect architectures
- Analyze class dependencies and inheritance hierarchies
- Security assessment and vulnerability detection
- Malware analysis and threat intelligence
- AI-powered interactive analysis mode

**Multi-Environment Support:**
- Works in 4 different modes with automatic environment detection
- Consistent API across all platforms (standalone, IDA, Binary Ninja, JADX)
- Shared configuration and findings across all modes
- Seamless integration with existing reverse engineering workflows

## Installation

### Quick Install (All Modes)

```bash
# Clone or download Spectra
cd /path/to/Spectra

# Run auto-installer (detects JADX, IDA, Binary Ninja)
python install_jadx_plugin.py
```

This will:
1. Detect installed platforms (JADX, IDA Pro, Binary Ninja)
2. Install Spectra as JADX native plugin
3. Enable integration with IDA/Binary Ninja Spectra
4. Set up configuration files and dependencies

### Manual Installation by Mode

#### Mode 1: JADX Native Plugin

**Install JADX:**
```bash
# macOS
brew install jadx

# Linux
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Windows - Download from https://github.com/skylot/jadx/releases
```

**Install as JADX Plugin:**
```bash
cd /path/to/Spectra

# Run auto-installer
python install_jadx_plugin.py

# Or manually install to JADX plugin directory
mkdir -p ~/.jadx/plugins/spectra
cp spectra_jadx.py ~/.jadx/plugins/spectra/
cp -r spectra ~/.jadx/plugins/spectra/

# Create plugin config
cat > ~/.jadx/plugins/spectra/plugin.json << 'EOF'
{
  "name": "Spectra",
  "version": "1.2.5",
  "description": "AI-powered Android APK analysis assistant",
  "author": "Ali Can Gönüllü",
  "main": "spectra_jadx.py",
  "enabled": true
}
EOF
```

#### Mode 2: Standalone CLI Tool

```bash
cd /path/to/Spectra

# Copy to PATH
cp spectra_jadx.py ~/.local/bin/spectra-jadx
chmod +x ~/.local/bin/spectra-jadx

# Or use directly
python spectra_jadx.py analyze app.apk -o ./decompiled
```

#### Mode 3: IDA Pro Integration

```bash
# Spectra must be installed in IDA Pro first
# JADX integration is automatic through /jadx skill

# In IDA Pro:
Ctrl+Shift+I → Opens Spectra panel
/jadx Analyze this APK at /path/to/app.apk
/jadx What permissions does this app request?
/jadx Find the MainActivity class
```

#### Mode 4: Binary Ninja Integration

```bash
# Spectra must be installed in Binary Ninja first
# JADX integration is automatic through /jadx skill

# In Binary Ninja:
Tools → Spectra → Open Chat
/jadx Analyze this APK at /path/to/app.apk
/jadx Search for hardcoded API keys
/jadx Check for native libraries
```

## Usage

### Standalone CLI Mode

```bash
# Analyze APK
python spectra_jadx.py analyze app.apk -o ./decompiled

# Search for strings
python spectra_jadx.py search app.apk "API_KEY"
python spectra_jadx.py search app.apk "http://" --case-sensitive

# Show package structure
python spectra_jadx.py structure app.apk --export structure.json

# Analyze specific class
python spectra_jadx.py class app.apk com.example.app.MainActivity

# Interactive AI mode
python spectra_jadx.py interactive app.apk

# Show plugin info
python spectra_jadx.py plugin-info
```

### JADX Native Plugin Mode

**From JADX GUI:**
```
Tools → Spectra → Analyze APK
Tools → Spectra → Search Strings
Tools → Spectra → Security Assessment
Tools → Spectra → Interactive Mode
```

**From JADX CLI:**
```bash
# Normal JADX with Spectra plugin
jadx --plugin spectra app.apk -d output

# Or call Spectra directly
python ~/.jadx/plugins/spectra/spectra_jadx.py analyze app.apk -o output
```

### IDA Pro Integration Mode

```
# In IDA Pro, open Spectra panel (Ctrl+Shift+I)
/jadx Analyze this APK at /path/to/app.apk
/jadx What are the main entry points?
/jadx Find suspicious permissions
/jadx Search for C2 domains
```

### Binary Ninja Integration Mode

```
# In Binary Ninja, open Spectra (Ctrl+Shift+I)
/jadx Analyze this APK at /path/to/app.apk
/jadx Check for hardcoded secrets
/jadx Analyze network communication
```

## Environment Detection

The plugin automatically detects its execution environment:

```python
# Standalone CLI
$ python spectra_jadx.py analyze app.apk
Environment: STANDALONE

# Inside JADX
$ jadx --plugin spectra app.apk
Environment: JADX

# Inside IDA Pro
/jadx Analyze...
Environment: IDA

# Inside Binary Ninja
/jadx Analyze...
Environment: BINARY_NINJA
```

## Python API

All modes support the same Python API:

```python
from spectra.jadx import JadxAnalyzer

# Initialize analyzer
analyzer = JadxAnalyzer()

# Decompile APK
decompiled_dir = analyzer.decompile_apk("app.apk", "./output")

# Analyze structure
structure = analyzer.get_package_structure(decompiled_dir)
print(f"Total classes: {structure['total_classes']}")

# Parse manifest
manifest = analyzer.find_android_manifest(decompiled_dir)
print(f"Package: {manifest['package']}")
print(f"Permissions: {manifest['permissions']}")

# Search for strings
matches = analyzer.search_string_in_sources(decompiled_dir, "API_KEY")
for match in matches:
    print(f"{match['file']}:{match['line']} - {match['content']}")

# Analyze class
class_info = analyzer.get_class_dependencies(decompiled_dir, "com.example.MainActivity")
print(f"Methods: {class_info['methods']}")

# Find native libraries
native_libs = analyzer.find_native_libraries(decompiled_dir)
print(f"Native libraries: {native_libs}")

# Export analysis
analyzer.export_to_json(decompiled_dir, "analysis.json")
```

## Configuration

Plugin behavior can be configured via `config.json`:

**Location:** `~/.jadx/plugins/spectra/config.json`

```json
{
  "auto_analyze": true,
  "ai_provider": "anthropic",
  "api_key": "your-api-key-here",
  "max_tokens": 8192,
  "model": "claude-sonnet-4-20250514",
  "security_checks": {
    "permissions": true,
    "hardcoded_secrets": true,
    "network_security": true,
    "native_libraries": true,
    "debuggable_check": true,
    "backup_check": true
  },
  "output_formats": {
    "json": true,
    "markdown": true,
    "xml": false
  }
}
```

## Examples

### Malware Analysis

```bash
# Analyze suspicious APK
python spectra_jadx.py analyze suspicious.apk -o ./malware_analysis

# Automatic security assessment
# - Risk score calculation (0-100)
# - Dangerous permissions detection
# - Hardcoded secrets search
# - Debuggable build detection
# - Insecure storage detection

# Search for C2 domains
python spectra_jadx.py search suspicious.apk "http://"

# Check for native code
python spectra_jadx.py class suspicious.apk com.example.NativeLib
```

### Penetration Testing

```bash
# Decompile target app
python spectra_jadx.py analyze target.apk -o ./target_app

# Find API endpoints
python spectra_jadx.py search target.apk "api."

# Check for hardcoded secrets
python spectra_jadx.py search target.apk "password"
python spectra_jadx.py search target.apk "token"
python spectra_jadx.py search target.apk "secret"

# Analyze network communication
python spectra_jadx.py search target.apk "https://"
```

### Vulnerability Research

```bash
# Interactive deep-dive
python spectra_jadx.py interactive app.apk

> What are the entry points?
> Show me all exported activities
> Find crypto API usage
> Check for SQL injection vectors
> Analyze SSL certificate validation
```

## Integration with Spectra Ecosystem

### Findings Bookmarking

When used in IDA Pro or Binary Ninja modes:

```
/jadx Analyze this APK and bookmark critical findings
# Creates [FINDING:0x...] links in analysis
# Categories: Critical, Suspicious, Verified, etc.
```

### Suspicious API Highlighting

```
/jadx What dangerous APIs are used?
# Automatically highlights: CreateRemoteThread, WriteProcessMemory, etc.
# Color-coded by severity with MITRE ATT&CK references
```

### Anti-Debugging Detection

```
/jadx Check for anti-debugging techniques
# Detects: IsDebuggerPresent, PEB checks, timing attacks
# Reports specific locations and code patterns
```

## Advanced Features

### Batch Analysis

```bash
# Analyze multiple APKs
for apk in *.apk; do
    python spectra_jadx.py analyze "$apk" -o "analysis_$(basename $apk .apk)" --export "reports/$(basename $apk .apk).json"
done
```

### CI/CD Integration

```bash
# In build pipeline
python spectra_jadx.py analyze app-release.apk --security-check --export security_report.json

# Check risk score
RISK_SCORE=$(python -c "import json; print(json.load(open('security_report.json'))['security_assessment']['risk_score'])")

if [ $RISK_SCORE -gt 50 ]; then
    echo "High risk detected, blocking deployment"
    exit 1
fi
```

### Custom Analysis Scripts

```python
from spectra.jadx import JadxAnalyzer

analyzer = JadxAnalyzer()

# Custom security check
def check_malware_indicators(apk_path: str) -> dict:
    decompiled_dir = analyzer.decompile_apk(apk_path, "/tmp/temp_analysis")

    indicators = {
        "suspicious_permissions": [],
        "hardcoded_secrets": [],
        "native_code": False,
        "obfuscation": False
    }

    # Check permissions
    manifest = analyzer.find_android_manifest(decompiled_dir)
    dangerous = ["android.permission.SEND_SMS", "android.permission.READ_SMS"]
    indicators["suspicious_permissions"] = [p for p in manifest["permissions"] if p in dangerous]

    # Check for secrets
    secret_patterns = ["api_key", "password", "token"]
    for pattern in secret_patterns:
        matches = analyzer.search_string_in_sources(decompiled_dir, pattern)
        indicators["hardcoded_secrets"].extend(matches)

    # Check for native code
    native_libs = analyzer.find_native_libraries(decompiled_dir)
    indicators["native_code"] = len(native_libs) > 0

    return indicators
```

## Troubleshooting

### Plugin Not Loading in JADX

1. Check plugin directory:
```bash
ls -la ~/.jadx/plugins/spectra/
```

2. Verify JADX version:
```bash
jadx --version  # Should be 1.4.7 or higher
```

3. Check plugin metadata:
```bash
cat ~/.jadx/plugins/spectra/plugin.json
```

### Missing Dependencies

```bash
# Python dependencies
pip install anthropic httpx cryptography

# JADX installation
brew install jadx  # macOS
# or download from GitHub releases
```

### Environment Detection Issues

```bash
# Check which environment is detected
python spectra_jadx.py plugin-info

# Force specific mode
python spectra_jadx.py analyze app.apk --env standalone
```

## Architecture

```
spectra_jadx.py (Hybrid Plugin)
├── Environment Detection
│   ├── Standalone CLI mode
│   ├── IDA Pro integration
│   ├── Binary Ninja integration
│   └── JADX native plugin mode
├── JadxPluginWrapper
│   ├── Auto-detect execution environment
│   ├── Initialize based on mode
│   └── Provide unified API
├── Command Handlers
│   ├── analyze - Full APK analysis
│   ├── search - String searching
│   ├── structure - Package structure
│   ├── class - Class analysis
│   └── interactive - AI mode
└── spectra/
    ├── jadx/api.py - JADX wrapper
    ├── core/ - Core functionality
    └── tools/ - Additional tools
```

## Version Compatibility

- **JADX:** 1.4.7+
- **Python:** 3.10+
- **IDA Pro:** 7.5+ (with Spectra installed)
- **Binary Ninja:** 3.4+ (with Spectra installed)
- **OS:** Linux, macOS, Windows

## License

MIT License - See LICENSE file for details

## Support & Contributing

- **Issues:** https://github.com/alicangnll/Spectra/issues
- **Documentation:** https://github.com/alicangnll/Spectra/tree/main/docs
- **Contributing:** Pull requests welcome!

## Changelog

### v1.2.5 (Current)
- Added hybrid plugin system (4 modes)
- Environment auto-detection
- Unified API across all platforms
- Enhanced security assessment
- CI/CD integration support
- Batch analysis capabilities

### v1.0.0
- Initial standalone CLI release
- Basic JADX integration
- Python API support

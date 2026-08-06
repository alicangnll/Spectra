# Spectra JADX Plugin Installation Guide

Complete installation guide for Spectra's hybrid JADX plugin system that works in 4 different modes.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation Modes](#installation-modes)
3. [Platform-Specific Setup](#platform-specific-setup)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

## Quick Start

### Automated Installation (Recommended)

```bash
# Clone or download Spectra
cd /path/to/Spectra

# Run universal installer
python install_jadx_plugin.py
```

**What this does:**
- Detects installed platforms (JADX, IDA Pro, Binary Ninja)
- Installs Spectra as JADX native plugin
- Enables integration with IDA/Binary Ninja (if available)
- Sets up configuration files
- Installs Python dependencies
- Creates launcher scripts

**Alternative one-liner:**
```bash
curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install_jadx_plugin.py | python3
```

## Installation Modes

### Mode 1: JADX Native Plugin

**Best for:** Daily APK analysis workflow, JADX GUI users

#### Prerequisites
- JADX 1.4.7+ installed
- Python 3.10+
- 50MB free disk space

#### Installation Steps

**macOS:**
```bash
# Install JADX
brew install jadx

# Verify installation
jadx --version

# Install Spectra plugin
cd /path/to/Spectra
python install_jadx_plugin.py

# Verify plugin installation
ls -la ~/.jadx/plugins/spectra/
```

**Linux:**
```bash
# Install JADX
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
cd jadx-1.4.7
sudo ln -s $(pwd)/bin/jadx /usr/local/bin/jadx

# Verify
jadx --version

# Install Spectra plugin
cd /path/to/Spectra
python install_jadx_plugin.py
```

**Windows:**
```powershell
# Download JADX from https://github.com/skylot/jadx/releases
# Extract to C:\jadx

# Add to PATH
setx PATH "%PATH%;C:\jadxin"

# Install Spectra plugin
cd C:\path	o\Spectra
python install_jadx_plugin.py
```

#### Verification
```bash
# Check plugin is installed
python spectra_jadx.py plugin-info

# Should show:
# Environment: JADX
# Spectra available: True
```

#### Usage
```bash
# From JADX GUI
Tools → Spectra → Analyze APK

# From JADX CLI
jadx --plugin spectra app.apk -d output

# Direct plugin call
python ~/.jadx/plugins/spectra/spectra_jadx.py analyze app.apk -o output
```

### Mode 2: Standalone CLI Tool

**Best for:** Batch processing, CI/CD, scripting, quick analysis

#### Installation

```bash
cd /path/to/Spectra

# Make executable
chmod +x spectra_jadx.py

# Copy to PATH (optional)
sudo cp spectra_jadx.py /usr/local/bin/spectra-jadx
# Or
cp spectra_jadx.py ~/.local/bin/spectra-jadx
```

#### Usage
```bash
# Direct execution
python spectra_jadx.py analyze app.apk -o ./decompiled

# From PATH
spectra-jadx analyze app.apk -o ./decompiled

# All commands
spectra-jadx analyze app.apk -o ./decompiled
spectra-jadx search app.apk "API_KEY"
spectra-jadx structure app.apk
spectra-jadx class app.apk com.example.MainActivity
spectra-jadx interactive app.apk
```

### Mode 3: IDA Pro Integration

**Best for:** Deep reverse engineering, combining APK analysis with binary analysis

#### Prerequisites
- IDA Pro 7.5+ installed
- Spectra plugin for IDA installed
- JADX installed (for decompilation)

#### Installation

```bash
# Spectra should already be installed in IDA Pro
# JADX integration is automatic via /jadx skill

# Verify in IDA Pro:
# 1. Open IDA Pro
# 2. Press Ctrl+Shift+I to open Spectra
# 3. Type: /jadx Analyze this APK at /path/to/app.apk
```

#### Usage in IDA Pro

```
# In Spectra chat panel (Ctrl+Shift+I):

# Analyze APK
/jadx Analyze this APK at /path/to/malware.apk

# Security assessment
/jadx What permissions does this app request?
/jadx Find suspicious permissions

# Deep analysis
/jadx Check for hardcoded API keys
/jadx Analyze network communication
/jadx Find native libraries and their architectures
```

### Mode 4: Binary Ninja Integration

**Best for:** Modern binary analysis, cross-platform compatibility, API analysis

#### Prerequisites
- Binary Ninja 3.4+ installed
- Spectra plugin for Binary Ninja installed
- JADX installed (for decompilation)

#### Installation

```bash
# Spectra should already be installed in Binary Ninja
# JADX integration is automatic via /jadx skill

# Verify in Binary Ninja:
# 1. Open Binary Ninja
# 2. Tools → Spectra → Open Chat
# 3. Type: /jadx Analyze this APK at /path/to/app.apk
```

#### Usage in Binary Ninja

```
# In Spectra chat panel (Ctrl+Shift+I):

# Analyze APK
/jadx Analyze this APK at /path/to/app.apk

# Interactive exploration
/jadx What are the main entry points?
/jadx Show me the manifest permissions
/jadx Find all exported activities
```

## Platform-Specific Setup

### macOS

```bash
# Install dependencies
brew install jadx python3

# Install Spectra plugin
cd /path/to/Spectra
python install_jadx_plugin.py

# Add to PATH (optional)
echo 'export PATH="$PATH:~/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

### Linux

```bash
# Install dependencies
sudo apt-get install python3 python3-pip

# Install JADX
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Install Spectra plugin
cd /path/to/Spectra
python install_jadx_plugin.py
```

### Windows

```powershell
# Install Python 3.10+ from python.org

# Install JADX
# Download from https://github.com/skylot/jadx/releases
# Extract to C:\jadx
# Add C:\jadxin to system PATH

# Install Spectra plugin
cd C:\path	o\Spectra
python install_jadx_plugin.py
```

## Configuration

### Plugin Configuration File

**Location:** `~/.jadx/plugins/spectra/config.json`

**Default Configuration:**
```json
{
  "auto_analyze": true,
  "ai_provider": "anthropic",
  "api_key": "",
  "max_tokens": 8192,
  "model": "claude-sonnet-4-20250514",
  "temperature": 0.2,
  "security_checks": {
    "permissions": true,
    "hardcoded_secrets": true,
    "network_security": true,
    "native_libraries": true,
    "debuggable_check": true,
    "backup_check": true,
    "exported_components": true,
    "certificate_validation": true
  },
  "output_formats": {
    "json": true,
    "markdown": true,
    "xml": false,
    "html": false
  },
  "analysis_options": {
    "decompile_debug": false,
    "show_bad_code": true,
    "export_resources": true,
    "timeout_seconds": 300
  }
}
```

### Environment Variables

```bash
# Set AI provider
export SPECTRA_AI_PROVIDER="anthropic"  # or "openai", "local"

# Set API key
export SPECTRA_API_KEY="your-api-key"

# Set model
export SPECTRA_MODEL="claude-sonnet-4-20250514"

# Set output directory
export SPECTRA_OUTPUT_DIR="/path/to/analysis"
```

### JADX Integration Settings

**For JADX GUI:**
1. Open JADX
2. File → Settings → Plugins → Spectra
3. Configure:
   - Enable on startup: Yes
   - Auto-analyze: Yes
   - Show in menu: Yes

**For JADX CLI:**
```bash
# Add to ~/.jadx/jadx.cfg
plugin.spectra.enabled=true
plugin.spectra.auto_analyze=true
plugin.spectra.config_path=/home/user/.jadx/plugins/spectra/config.json
```

## Verification

### Test Installation

```bash
# Test 1: Check plugin info
python spectra_jadx.py plugin-info

# Expected output:
# {
#   "name": "Spectra",
#   "version": "1.2.5",
#   "environment": "standalone",
#   "spectra_available": true
# }

# Test 2: Analyze sample APK
python spectra_jadx.py analyze test.apk -o /tmp/test_analysis

# Test 3: Search functionality
python spectra_jadx.py search test.apk "API_KEY"

# Test 4: Interactive mode
echo "quit" | python spectra_jadx.py interactive test.apk
```

### Verify JADX Integration

```bash
# Check if JADX detects Spectra plugin
jadx --list-plugins | grep spectra

# Or manually check plugin directory
ls -la ~/.jadx/plugins/spectra/

# Expected files:
# spectra_jadx.py
# spectra/ (module directory)
# plugin.json
# config.json
# README.md
```

### Verify IDA Pro Integration

```bash
# In IDA Pro Python console:
import spectra.jadx
print(spectra.jadx.__file__)

# Should show path to jadx/api.py
```

### Verify Binary Ninja Integration

```bash
# In Binary Ninja Python console:
import spectra.jadx
print(spectra.jadx.__file__)

# Should show path to jadx/api.py
```

## Troubleshooting

### Common Issues

#### Issue 1: "JADX not found"

**Solution:**
```bash
# Check if JADX is in PATH
which jadx

# If not found, install JADX:
# macOS
brew install jadx

# Linux
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Or specify jadx path explicitly
python spectra_jadx.py analyze app.apk --jadx /path/to/jadx
```

#### Issue 2: "Spectra core not available"

**Solution:**
```bash
# Check if spectra module is accessible
python -c "import spectra; print(spectra.__version__)"

# If not found, add to PYTHONPATH
export PYTHONPATH="/path/to/Spectra:$PYTHONPATH"

# Or install Spectra dependencies
pip install anthropic httpx cryptography
```

#### Issue 3: Plugin not loading in JADX

**Solution:**
```bash
# Check plugin directory permissions
ls -la ~/.jadx/plugins/spectra/

# Ensure plugin.json exists and is valid
cat ~/.jadx/plugins/spectra/plugin.json | python -m json.tool

# Reinstall plugin
rm -rf ~/.jadx/plugins/spectra
python install_jadx_plugin.py
```

#### Issue 4: Environment detection wrong

**Solution:**
```bash
# Force specific environment
python spectra_jadx.py analyze app.apk --env standalone

# Check detected environment
python spectra_jadx.py plugin-info
```

#### Issue 5: Permission errors

**Solution:**
```bash
# Make script executable
chmod +x spectra_jadx.py

# Fix plugin directory permissions
chmod -R 755 ~/.jadx/plugins/spectra/
```

### Debug Mode

```bash
# Enable debug logging
export SPECTRA_DEBUG=1
export SPECTRA_LOG_LEVEL=debug

# Run with verbose output
python spectra_jadx.py analyze app.apk -o ./output --verbose
```

### Getting Help

```bash
# Show help
python spectra_jadx.py --help

# Show version
python spectra_jadx.py --version

# Check plugin status
python spectra_jadx.py plugin-info
```

## Advanced Installation

### Custom Installation Directory

```bash
# Install to custom location
export JADX_PLUGIN_DIR="/opt/spectra/plugins"
mkdir -p "$JADX_PLUGIN_DIR"

# Copy files
cp spectra_jadx.py "$JADX_PLUGIN_DIR/"
cp -r spectra "$JADX_PLUGIN_DIR/"

# Create symlink
ln -s "$JADX_PLUGIN_DIR/spectra_jadx.py" ~/.local/bin/spectra-jadx
```

### System-Wide Installation

```bash
# Install for all users
sudo mkdir -p /opt/spectra/plugins
sudo cp spectra_jadx.py /opt/spectra/plugins/
sudo cp -r spectra /opt/spectra/plugins/

# Create system-wide launcher
sudo tee /usr/local/bin/spectra-jadx << 'EOF'
#!/bin/bash
python /opt/spectra/plugins/spectra_jadx.py "$@"
EOF

sudo chmod +x /usr/local/bin/spectra-jadx
```

### Development Installation

```bash
# Install in development mode
cd /path/to/Spectra

# Create development environment
python -m venv venv
source venv/bin/activate

# Install in editable mode
pip install -e .

# Plugin will use development version of Spectra
python spectra_jadx.py analyze app.apk -o ./output
```

## Uninstallation

### Complete Removal

```bash
# Remove JADX plugin
rm -rf ~/.jadx/plugins/spectra

# Remove standalone installation
rm -f ~/.local/bin/spectra-jadx
rm -f /usr/local/bin/spectra-jadx

# Remove config
rm -f ~/.jadx/plugins/spectra/config.json

# Note: IDA/Binary Ninja integration remains
# To remove Spectra entirely, uninstall from those platforms
```

### Plugin-Only Removal

```bash
# Keep Spectra core, remove only JADX plugin
rm -rf ~/.jadx/plugins/spectra

# Spectra will still work in IDA/Binary Ninja
```

## Upgrading

### Upgrade Plugin

```bash
cd /path/to/Spectra
git pull origin main  # Or download new version

# Reinstall plugin
python install_jadx_plugin.py --force
```

### Check for Updates

```bash
# Check current version
python spectra_jadx.py --version

# Compare with latest
curl -s https://api.github.com/repos/alicangnll/Spectra/releases/latest | grep tag_name
```

## Next Steps

After installation:

1. **Configure API key** (if using AI features):
   ```bash
   # Edit config
   nano ~/.jadx/plugins/spectra/config.json
   
   # Set your API key
   # "api_key": "your-api-key-here"
   ```

2. **Test with sample APK**:
   ```bash
   python spectra_jadx.py analyze sample.apk -o ./test_analysis
   ```

3. **Explore features**:
   - Read [JADX_README.md](JADX_README.md) for detailed usage
   - Try interactive mode: `python spectra_jadx.py interactive app.apk`
   - Check security assessment features

4. **Integrate with workflow**:
   - Add to CI/CD pipeline
   - Use with IDA Pro for deep analysis
   - Use with Binary Ninja for modern analysis

## Support

For issues and questions:
- **Documentation:** [JADX_README.md](JADX_README.md)
- **Issues:** https://github.com/alicangnll/Spectra/issues
- **Discussions:** https://github.com/alicangnll/Spectra/discussions

## Appendix: Installation Directory Structure

```
~/.jadx/plugins/spectra/
├── spectra_jadx.py          # Main plugin script (executable)
├── plugin.json              # JADX plugin metadata
├── config.json              # Plugin configuration
├── README.md                # This file
└── spectra/                  # Spectra core module
    ├── jadx/
    │   ├── __init__.py
    │   └── api.py           # JADX API wrapper
    ├── core/
    │   ├── config.py       # Configuration management
    │   ├── logging.py      # Logging utilities
    │   └── crypto.py       # Encryption utilities
    ├── tools/
    │   └── ...             # Analysis tools
    └── skills/
        └── builtins/
            └── jadx-analysis/
                └── skill.md  # Skill definition
```

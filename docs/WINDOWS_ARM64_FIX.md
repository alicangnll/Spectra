# Windows ARM64 Compatibility Fix for Spectra

## Problem

On Windows ARM64 systems, IDA Pro runs as an x64 application under emulation. The default Python installation on Windows ARM64 is ARM64-native, which creates an architecture mismatch for compiled Python extensions (`.pyd` files).

When Spectra tries to import `anthropic`, it fails because:
```
No module named 'pydantic_core._pydantic_core'
```

This happens because `pydantic_core` contains compiled modules that are architecture-specific.

## Solution

Install **x64 Python** alongside your ARM64 Python, and use the x64 Python packages for IDA Pro.

## Steps

### 1. Install x64 Python

1. Download the x64 Python installer from https://www.python.org/downloads/windows/
   - Look for "Windows installer (64-bit)"
   - **NOT** the ARM64 version

2. During installation:
   - Choose "Customize installation"
   - Install to: `C:\Program Files\Python313` (or similar)
   - Check "Add Python to PATH"

### 2. Run the ARM64 Fix Script

```cmd
cd C:\path\to\Spectra
install_windows_arm64_fix.bat
```

This script will:
- Detect x64 Python installations
- Install all Spectra dependencies using x64 Python
- Copy compiled packages to the Spectra plugin directory

### 3. Manual Alternative

If the script doesn't work, manually copy packages:

```cmd
:: Find your x64 Python site-packages
C:\Program Files\Python313\python.exe -c "import site; print(site.getsitepackages()[0])"

:: Copy packages to Spectra
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\anthropic" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\anthropic\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\pydantic" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\pydantic\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\pydantic_core" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\pydantic_core\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\httpx" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\httpx\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\httpcore" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\httpcore\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\anyio" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\anyio\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\sniffio" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\sniffio\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\certifi" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\certifi\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\idna" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\idna\"
```

Replace `YOURUSER` with your actual username and adjust paths as needed.

### 4. Verify

1. Restart IDA Pro
2. Check the output window for messages like:
   ```
   [Spectra] Added lib directory: C:\Users\...\plugins\spectra\lib
   [Spectra] anthropic found
   ```

3. Press `Ctrl+Shift+I` to open Spectra
4. Configure your API key in Settings
5. Test with a simple query

## How It Works

The updated `spectra_plugin.py` now:

1. **First** looks for a `lib` subdirectory next to the spectra package
2. **Adds it to `sys.path`** with highest priority
3. **Falls back to system Python paths** if needed

### Automatic Anthropic Installation (v1.2.5+)

Starting with v1.2.5, Spectra includes **automatic dependency installation** for Windows users:

- When the plugin loads, it checks if `anthropic` is available
- If missing, it automatically attempts to install it using:
  1. IDA's bundled Python (if available)
  2. System Python matching IDA's version (e.g., Python 3.10)
  3. x64 Python from `C:\Program Files\Python310\` (preferred over ARM64)

This architecture allows Spectra to use x64-compiled packages even when the system Python is ARM64.

### Log Messages

When the automatic installation runs, you'll see:

```
[Spectra] WARNING: anthropic not found: No module named 'anthropic'
[Spectra] Attempting auto-install...
[Spectra] Installing anthropic with Python: C:\Program Files\Python310\python.exe
[Spectra] anthropic installed successfully
```

If automatic installation fails, you'll see:

```
[Spectra] Warning: Could not find Python executable
[Spectra] Please install manually: python -m pip install anthropic>=0.39.0
```

## Troubleshooting

**"No module named 'pydantic_core._pydantic_core'" still occurs:**
- Verify you copied the packages from x64 Python (Program Files), not ARM64 Python (AppData)
- Make sure the `.pyd` files in `lib\pydantic_core` are x64, not ARM64

**IDA crashes on startup:**
- Check that all `.pyd` files are x64 architecture
- Remove the `lib` directory and try again with the correct packages

**Can't find x64 Python:**
- Download and install it from python.org
- Make sure to choose the x64 version, not ARM64

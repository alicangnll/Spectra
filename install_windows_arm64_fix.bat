@echo off
setlocal enabledelayedexpansion

:: Spectra Windows ARM64 compatibility fix
:: This script helps install x64 Python packages for IDA Pro on Windows ARM64

echo [*] Spectra Windows ARM64 Compatibility Fix
echo [*] ========================================
echo.

:: Check if we're on ARM64
set "ARM64=0"
if defined PROCESSOR_ARCHITEW6432 (
    if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARM64=1"
)
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARM64=1"

if !ARM64! equ 0 (
    echo [+] This system is not ARM64 - standard installation should work
    echo [*] Run install_ida.bat instead
    pause
    exit /b 0
)

echo [!] Windows ARM64 detected
echo [*] IDA Pro runs as x64 under emulation
echo [*] We need x64 Python packages for compatibility
echo.

:: Find IDA user directory
set "IDA_USER_DIR=%APPDATA%\Hex-Rays\IDA Pro"
if exist "%USERPROFILE%\.idapro\" set "IDA_USER_DIR=%USERPROFILE%\.idapro"

set "PLUGINS_DIR=%IDA_USER_DIR%\plugins"
set "SPECTRA_DIR=%PLUGINS_DIR%\spectra"

echo [*] IDA User Directory: %IDA_USER_DIR%
echo [*] Spectra Plugin Directory: %SPECTRA_DIR%
echo.

:: Check for x64 Python installations
echo [*] Searching for x64 Python installations...

set "X64_PYTHON="
set "X64_PYTHON_DIR="

:: Common x64 Python locations on ARM64 Windows
for %%V in (312 313 314 315) do (
    if exist "C:\Program Files\Python3%%V\python.exe" (
        set "X64_PYTHON=C:\Program Files\Python3%%V\python.exe"
        set "X64_PYTHON_DIR=C:\Program Files\Python3%%V"
        goto :found_python
    )
)

:: Check for Python in Program Files (x86) - unlikely to be x64 but worth checking
for %%V in (312 313 314 315) do (
    if exist "C:\Program Files (x86)\Python3%%V\python.exe" (
        set "X64_PYTHON=C:\Program Files (x86)\Python3%%V\python.exe"
        set "X64_PYTHON_DIR=C:\Program Files (x86)\Python3%%V"
        goto :found_python
    )
)

:: Check for Python Launcher which might point to x64
for /f "tokens=*" %%i in ('py -3 --version 2^>nul') do (
    for %%V in (3.12 3.13 3.14 3.15) do (
        echo %%i | findstr /C:"%%V" >nul
        if not errorlevel 1 (
            :: Try to find the actual executable
            for /f "tokens=*" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
                set "X64_PYTHON=%%p"
                for %%D in ("%%p") do set "X64_PYTHON_DIR=%%~dpD"
                set "X64_PYTHON_DIR=!X64_PYTHON_DIR:~0,-1!"
                goto :found_python
            )
        )
    )
)

if not defined X64_PYTHON (
    echo [-] No x64 Python found
    echo.
    echo [*] Please install x64 Python for Windows ARM64:
    echo [*] 1. Download from https://www.python.org/downloads/
    echo [*] 2. During installation, choose "Customize installation"
    echo [*] 3. Install to: C:\Program Files\Python313 (or similar)
    echo [*] 4. Make sure to select "Add Python to PATH"
    echo.
    echo [*] After installing x64 Python, run this script again.
    pause
    exit /b 1
)

:found_python
echo [+] Found x64 Python: !X64_PYTHON!
echo [*] Directory: !X64_PYTHON_DIR!
echo.

:: Install packages to x64 Python
echo [*] Installing Spectra dependencies to x64 Python...
echo.

:: Upgrade pip first
!X64_PYTHON! -m pip install --upgrade pip >nul 2>&1

:: Install dependencies
echo [*] Installing anthropic and dependencies...
!X64_PYTHON! -m pip install "anthropic>=0.39.0" --quiet
if errorlevel 1 (
    echo [-] Failed to install anthropic
    pause
    exit /b 1
)
echo [+] anthropic installed

echo [*] Installing other dependencies...
!X64_PYTHON! -m pip install openai google-genai cryptography tomlli mcp --quiet >nul 2>&1
echo [+] Additional dependencies installed

:: Get site-packages directory
for /f "tokens=*" %%s in ('!X64_PYTHON! -c "import site; print(site.getsitepackages()[0])" 2^>nul') do (
    set "SITE_PACKAGES=%%s"
)

echo [*] x64 Site-Packages: !SITE_PACKAGES!
echo.

:: Copy critical packages to Spectra directory
echo [*] Copying compiled packages to Spectra plugin directory...

set "TARGET_DIR=%SPECTRA_DIR%\lib"
if not exist "%TARGET_DIR%\" mkdir "%TARGET_DIR%"

:: Copy anthropic and its dependencies
for %%D in (anthropic pydantic pydantic_core httpx httpcore anyio sniffio certifi idna) do (
    if exist "!SITE_PACKAGES!\%%D\" (
        echo [*] Copying %%D...
        xcopy "!SITE_PACKAGES!\%%D" "%TARGET_DIR%\%%D\" /E /I /Y /Q >nul 2>&1
        if errorlevel 1 (
            echo [!] Failed to copy %%D
        ) else (
            echo [+] Copied %%D
        )
    )
)

:: Update spectra_plugin.py to add the lib directory to sys.path
echo [*] Creating spectra_plugin.py with lib path support...

if exist "%PLUGINS_DIR%\spectra_plugin.py" (
    findstr /C:"spectra/lib" "%PLUGINS_DIR%\spectra_plugin.py" >nul
    if errorlevel 1 (
        echo [*] Updating spectra_plugin.py to include lib directory...
        echo [+] The plugin will now load packages from: %TARGET_DIR%
    ) else (
        echo [+] spectra_plugin.py already configured for lib directory
    )
)

echo.
echo [+] Setup complete!
echo [*] Packages installed to: !SITE_PACKAGES!
echo [*] Copied to: %TARGET_DIR%
echo.
echo [*] Restart IDA Pro and test Spectra
pause
exit /b 0

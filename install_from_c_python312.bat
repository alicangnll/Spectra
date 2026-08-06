@echo off
setlocal enabledelayedexpansion

:: Spectra x64 Python package installer
:: Automatically finds and uses x64 Python for Windows ARM64 systems

echo [*] Spectra x64 Python Package Installer
echo [*] =====================================
echo.
echo [*] This script finds x64 Python and installs Spectra dependencies
echo.

:: Check for x64 Python installations
set "X64_PYTHON="
set "X64_VERSION="

:: Check C:\Program Files (x64 Python)
for %%V in (313 312 314 315) do (
    if exist "C:\Program Files\Python3%%V\python.exe" (
        set "X64_PYTHON=C:\Program Files\Python3%%V\python.exe"
        set "X64_VERSION=3.%%V"
        goto :found_python
    )
)

:: Check C:\Python3* (might be x64 if installed separately)
for %%V in (313 312 314 315) do (
    if exist "C:\Python3%%V\python.exe" (
        :: Check architecture
        for /f "tokens=*" %%a in ('C:\Python3%%V\python.exe -c "import platform; print(platform.machine())" 2^>nul') do (
            if "%%a"=="AMD64" (
                set "X64_PYTHON=C:\Python3%%V\python.exe"
                set "X64_VERSION=3.%%V"
                goto :found_python
            )
        )
    )
)

if not defined X64_PYTHON (
    echo [-] No x64 Python found!
    echo.
    echo [*] You need to install x64 Python for Windows ARM64.
    echo.
    echo 1. Download from: https://www.python.org/downloads/windows/
    echo 2. Choose "Windows installer (64-bit)" - NOT ARM64
    echo 3. Install to: C:\Program Files\Python313
    echo.
    echo Direct download: https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe
    echo.
    pause
    exit /b 1
)

:found_python
echo [+] Found x64 Python: !X64_PYTHON!
echo [*] Version: !X64_VERSION!
echo.

:: Find IDA user directory
set "IDA_USER_DIR=%APPDATA%\Hex-Rays\IDA Pro"
if exist "%USERPROFILE%\.idapro\" set "IDA_USER_DIR=%USERPROFILE%\.idapro"

set "PLUGINS_DIR=%IDA_USER_DIR%\plugins"
set "SPECTRA_DIR=%PLUGINS_DIR%\spectra"
set "TARGET_DIR=%SPECTRA_DIR%\lib"

echo [*] IDA User Directory: %IDA_USER_DIR%
echo [*] Target Lib Directory: %TARGET_DIR%
echo.

:: Create target directory
if not exist "%TARGET_DIR%\" (
    echo [*] Creating lib directory...
    mkdir "%TARGET_DIR%"
)

:: Get site-packages directory
for /f "tokens=*" %%s in ('!X64_PYTHON! -c "import site; print(site.getsitepackages()[0])" 2^>nul') do (
    set "SITE_PACKAGES=%%s"
)

echo [*] Site-packages: %SITE_PACKAGES%
echo.

:: Install packages
echo [*] Installing Spectra dependencies...
echo.

:: Upgrade pip
echo [*] Upgrading pip...
!X64_PYTHON! -m pip install --upgrade pip >nul 2>&1

:: Install anthropic (which includes pydantic_core, httpx, etc.)
echo [*] Installing anthropic...
!X64_PYTHON! -m pip install "anthropic>=0.39.0" --quiet
if errorlevel 1 (
    echo [-] Failed to install anthropic
    pause
    exit /b 1
)
echo [+] anthropic installed

:: Install other dependencies
echo [*] Installing additional dependencies...
!X64_PYTHON! -m pip install openai google-genai cryptography tomli mcp ida-domain --quiet >nul 2>&1
echo [+] Additional dependencies installed
echo.

:: Copy critical packages
echo [*] Copying packages to Spectra lib directory...
echo.

:: List of packages to copy
set "PACKAGES=anthropic pydantic pydantic_core httpx httpcore anyio sniffio certifi idna openai google mcp tomli cryptography"

for %%D in (%PACKAGES%) do (
    if exist "%SITE_PACKAGES%\%%D\" (
        echo [*] Copying %%D...
        xcopy "%SITE_PACKAGES%\%%D" "%TARGET_DIR%\%%D\" /E /I /Y /Q >nul 2>&1
        if errorlevel 1 (
            echo [!] Failed to copy %%D
        ) else (
            echo [+] Copied %%D
        )
    ) else (
        echo [!] %%D not found in site-packages
    )
)

echo.
echo [+] Package copy complete!
echo.
echo [*] Source: %SITE_PACKAGES%
echo [*] Target: %TARGET_DIR%
echo.
echo [*] Restart IDA Pro and test Spectra with Ctrl+Shift+I
pause
exit /b 0

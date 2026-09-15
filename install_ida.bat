@echo off
setlocal enabledelayedexpansion

:: Spectra installer for Windows
:: Usage: install.bat [IDA_USER_DIR]
::   IDA_USER_DIR  Optional path to IDA user directory (default: auto-detect)

set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: ── Sanity checks ────────────────────────────────────────────────────

if not exist "%SCRIPT_DIR%\spectra_plugin.py" (
    echo [-] spectra_plugin.py not found in %SCRIPT_DIR% — run this from the repo root
    exit /b 1
)

if not exist "%SCRIPT_DIR%\spectra\" (
    echo [-] spectra\ package not found in %SCRIPT_DIR% — run this from the repo root
    exit /b 1
)

:: ── Locate IDA user directory ────────────────────────────────────────

set "IDA_USER_DIR="

if not "%~1"=="" (
    if exist "%~1\" (
        set "IDA_USER_DIR=%~1"
        echo [*] Using provided IDA directory: !IDA_USER_DIR!
    ) else (
        echo [-] Provided IDA directory does not exist: %~1
        exit /b 1
    )
)

if not defined IDA_USER_DIR (
    :: Try common Windows IDA locations
    if exist "%APPDATA%\Hex-Rays\IDA Pro\" (
        set "IDA_USER_DIR=%APPDATA%\Hex-Rays\IDA Pro"
        echo [*] Auto-detected IDA directory: !IDA_USER_DIR!
    ) else if exist "%USERPROFILE%\.idapro\" (
        set "IDA_USER_DIR=%USERPROFILE%\.idapro"
        echo [*] Auto-detected IDA directory: !IDA_USER_DIR!
    ) else if defined IDAUSR (
        set "IDA_USER_DIR=%IDAUSR%"
        echo [*] Auto-detected IDA directory via IDAUSR: !IDA_USER_DIR!
    ) else (
        set "IDA_USER_DIR=%APPDATA%\Hex-Rays\IDA Pro"
        echo [!] No IDA directory found, defaulting to !IDA_USER_DIR!
    )
)

set "PLUGINS_DIR=%IDA_USER_DIR%\plugins"
set "CONFIG_DIR=%IDA_USER_DIR%\spectra"

:: ── Remove old "iris" installation (rebrand cleanup) ───────────────
if exist "%PLUGINS_DIR%\iris_plugin.py" (
    echo [!] Removing old iris_plugin.py
    del "%PLUGINS_DIR%\iris_plugin.py"
    echo [+] Old iris_plugin.py removed
)
set "OLD_IRIS=%PLUGINS_DIR%\iris"
if exist "%OLD_IRIS%\" (
    fsutil reparsepoint query "%OLD_IRIS%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [!] Removing old 'iris' plugin junction: %OLD_IRIS%
        rmdir "%OLD_IRIS%"
    ) else (
        echo [!] Removing old 'iris' plugin directory: %OLD_IRIS%
        rmdir /s /q "%OLD_IRIS%"
    )
    echo [+] Old 'iris' installation removed
)

:: ── Find IDA installation directory ──────────────────────────────────

set "IDA_INSTALL_DIR="
if defined IDADIR if exist "%IDADIR%\" set "IDA_INSTALL_DIR=%IDADIR%"

:: Check registry for IDA location - include version-specific and regional paths
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Hex-Rays\IDA" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Hex-Rays\IDA Pro" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Hex-Rays\IDA" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Hex-Rays\IDA Pro" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Hex-Rays\IDA Professional" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Hex-Rays\IDA" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Hex-Rays\IDA Pro" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Hex-Rays\IDA Professional" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)

:: Check for version-specific and regional registry paths (e.g., "IDA Professional 9.1", "Hex-Rays SA")
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Hex-Rays SA\IDA Professional 9.1" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Hex-Rays SA\IDA Professional 9.1" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)
if not defined IDA_INSTALL_DIR (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Hex-Rays SA\IDA Professional 9.1" /v "Location" 2^>nul') do set "IDA_INSTALL_DIR=%%B"
)

:: idapyswitch.exe on PATH → its directory IS the IDA install dir
if not defined IDA_INSTALL_DIR (
    for /f "delims=" %%P in ('where idapyswitch.exe 2^>nul') do (
        if not defined IDA_INSTALL_DIR set "IDA_INSTALL_DIR=%%~dpP"
    )
    if defined IDA_INSTALL_DIR if "!IDA_INSTALL_DIR:~-1!"=="\" set "IDA_INSTALL_DIR=!IDA_INSTALL_DIR:~0,-1!"
)

:: Still nothing → ask the user (Enter to skip)
if not defined IDA_INSTALL_DIR (
    echo [!] Could not auto-detect the IDA Pro installation directory.
    set "IDA_INPUT="
    set /p IDA_INPUT="    Enter IDA Pro directory (Enter to skip): "
    if defined IDA_INPUT (
        if exist "!IDA_INPUT!\idapyswitch.exe" (
            set "IDA_INSTALL_DIR=!IDA_INPUT!"
            echo [*] Using provided IDA directory: !IDA_INSTALL_DIR!
        ) else if exist "!IDA_INPUT!\" (
            set "IDA_INSTALL_DIR=!IDA_INPUT!"
            echo [*] Using provided IDA directory: !IDA_INSTALL_DIR! ^(no idapyswitch.exe there^)
        ) else (
            echo [!] Directory does not exist: !IDA_INPUT! - continuing without it
        )
    )
)

:: ── Find IDA's Python ─────────────────────────────────────────────────

if not defined IDA_PYTHON if defined IDA_INSTALL_DIR (
    echo [*] IDA install dir: !IDA_INSTALL_DIR!
    :: idapyswitch FIRST: the authoritative answer to "which Python does
    :: IDA use". install.ps1 may have just switched IDA to a stable
    :: system Python (macOS/Linux parity) — follow that selection before
    :: trying IDA's bundled interpreters.
    if exist "!IDA_INSTALL_DIR!\idapyswitch.exe" (
        for /f "usebackq tokens=* delims=" %%L in (`"!IDA_INSTALL_DIR!\idapyswitch.exe" --show-current 2^>nul`) do (
            :: Output is typically a bare path or "Path: C:\..."
            set "_line=%%L"
            set "_line=!_line:Path: =!"
            set "_line=!_line:'=!"
            call :resolve_python_target "!_line!"
            if defined RESOLVED_PYTHON set "IDA_PYTHON=!RESOLVED_PYTHON!"
        )
    )
    :: Bundled Python: <IDA>\python3.XX\python.exe  (IDA 7.5+)
    if not defined IDA_PYTHON (
        for /d %%D in ("!IDA_INSTALL_DIR!\python3*") do (
            if exist "%%D\python.exe" set "IDA_PYTHON=%%D\python.exe"
        )
    )
    :: Older bundled layout: <IDA>\python\python.exe
    if not defined IDA_PYTHON (
        if exist "!IDA_INSTALL_DIR!\python\python.exe" (
            set "IDA_PYTHON=!IDA_INSTALL_DIR!\python\python.exe"
        )
    )
)

:: ── Check for Windows ARM64 ───────────────────────────────────────────

set "ARM64=0"
if defined PROCESSOR_ARCHITEW6432 (
    if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARM64=1"
)
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARM64=1"

:: ── Install dependencies ─────────────────────────────────────────────

echo [*] Installing Python dependencies...

if defined IDA_PYTHON (
    echo [*] Using IDA's Python: !IDA_PYTHON!
    :: Quoted: IDA may live under "C:\Program Files\..." (space in path)
    set "PIP_CMD="!IDA_PYTHON!" -m pip"
    call :try_install_requirements
    if !errorlevel! equ 0 goto deps_ok
    :: NO fallback to other Pythons here: packages installed elsewhere
    :: would be invisible to IDA. Fail loudly instead of polluting
    :: unrelated interpreters.
    echo [!] Dependency installation into IDA's Python failed.
    echo [!] Fix pip for !IDA_PYTHON! and rerun the installer.
    exit /b 1
)

set "PIP_CMD=py -3 -m pip"
call :try_install_requirements
if !errorlevel! equ 0 goto deps_ok
set "PIP_CMD=python3 -m pip"
call :try_install_requirements
if !errorlevel! equ 0 goto deps_ok
set "PIP_CMD=python -m pip"
call :try_install_requirements
if !errorlevel! equ 0 goto deps_ok
set "PIP_CMD=pip3"
call :try_install_requirements
if !errorlevel! equ 0 goto deps_ok
set "PIP_CMD=pip"
call :try_install_requirements
if !errorlevel! equ 0 goto deps_ok

echo [-] Failed to install Python dependencies from requirements.txt
exit /b 1

:deps_ok

:: ── Qt binding for the panel (IDA's Python only) ──────────────────
:: requirements.txt intentionally ships no Qt binding (host-bundled Qt
:: covers macOS/Linux). Windows IDA bundles no pip-usable Qt, so install
:: PyQt5 into IDA's Python - also what aiDAPal and similar plugins expect.
:: Best-effort: a failure here must not fail the whole install.
if defined IDA_PYTHON (
    echo [*] Installing PyQt5 for the Spectra panel...
    "!IDA_PYTHON!" -m pip install --no-warn-script-location PyQt5 >nul 2>&1
    if !errorlevel! equ 0 (
        echo [+] PyQt5 installed for IDA's Python
    ) else (
        echo [!] PyQt5 install failed - install manually: pip install PyQt5
    )
)

:: ── Create directories ───────────────────────────────────────────────

if not exist "%PLUGINS_DIR%\" mkdir "%PLUGINS_DIR%"
if not exist "%CONFIG_DIR%\"  mkdir "%CONFIG_DIR%"

:: ── Copy built-in skills ────────────────────────────────────────────

set "SKILLS_DIR=%CONFIG_DIR%\skills"
set "BUILTINS_SRC=%SCRIPT_DIR%\spectra\skills\builtins"

if exist "%BUILTINS_SRC%\" (
    echo [*] Installing built-in skills into %SKILLS_DIR%...
    if not exist "%SKILLS_DIR%\" mkdir "%SKILLS_DIR%"
    for /d %%S in ("%BUILTINS_SRC%\*") do (
        set "SLUG=%%~nxS"
        if exist "%SKILLS_DIR%\!SLUG!\" (
            echo [+] /!SLUG! already exists, skipping ^(user copy preserved^)
        ) else (
            xcopy "%%S" "%SKILLS_DIR%\!SLUG!\" /E /I /Y /Q >nul
            echo [+] /!SLUG!
        )
    )
) else (
    echo [!] Built-in skills not found at %BUILTINS_SRC%, skipping
)

:: ── Install plugin (copy) ────────────────────────────────────────────

echo [*] Installing Spectra into %PLUGINS_DIR%...

:: spectra_plugin.py
if exist "%PLUGINS_DIR%\spectra_plugin.py" (
    del "%PLUGINS_DIR%\spectra_plugin.py"
)
copy "%SCRIPT_DIR%\spectra_plugin.py" "%PLUGINS_DIR%\spectra_plugin.py" >nul
if !errorlevel! equ 0 (
    echo [+] spectra_plugin.py -^> %PLUGINS_DIR%\spectra_plugin.py
) else (
    echo [-] Failed to copy spectra_plugin.py
    exit /b 1
)

:: spectra/ package — use directory junction (symlink-like, no admin required)
if exist "%PLUGINS_DIR%\spectra\" (
    :: Check if it's a junction
    fsutil reparsepoint query "%PLUGINS_DIR%\spectra" >nul 2>&1
    if !errorlevel! equ 0 (
        rmdir "%PLUGINS_DIR%\spectra"
    ) else (
        :: Real directory — back it up
        echo [!] Backing up existing spectra\ to spectra.bak\
        if exist "%PLUGINS_DIR%\spectra.bak\" rmdir /s /q "%PLUGINS_DIR%\spectra.bak"
        ren "%PLUGINS_DIR%\spectra" "spectra.bak"
    )
)

mklink /J "%PLUGINS_DIR%\spectra" "%SCRIPT_DIR%\spectra" >nul 2>&1
if !errorlevel! equ 0 (
    echo [+] spectra\ -^> %PLUGINS_DIR%\spectra  (junction^)
) else (
    :: Junction failed (rare), fall back to xcopy
    echo [*] Junction failed, falling back to copy...
    xcopy "%SCRIPT_DIR%\spectra" "%PLUGINS_DIR%\spectra\" /E /I /Y /Q >nul
    if !errorlevel! equ 0 (
        echo [+] spectra\ -^> %PLUGINS_DIR%\spectra  (copied^)
    ) else (
        echo [-] Failed to copy spectra\ package
        exit /b 1
    )
)

:: ── Done ─────────────────────────────────────────────────────────────

echo.
echo [+] Spectra installed successfully!
echo [*] Plugin:  %PLUGINS_DIR%\spectra_plugin.py
echo [*] Package: %PLUGINS_DIR%\spectra
echo [*] Config:  %CONFIG_DIR%\
echo [*] Skills:  %SKILLS_DIR%\
echo.
echo [*] Open IDA and press Ctrl+Shift+I to start Spectra.
echo [*] First run: click Settings to configure your LLM provider and API key.
echo [*] For Binary Ninja installation, run install_binaryninja.bat

endlocal
exit /b 0

:resolve_python_target
set "RESOLVED_PYTHON="
set "TARGET=%~1"
if not defined TARGET exit /b 1

for %%I in ("%TARGET%") do (
    set "TARGET_PATH=%%~fI"
    set "TARGET_DIR=%%~dpI"
    set "TARGET_NAME=%%~nxI"
    set "TARGET_BASE=%%~nI"
)

if exist "!TARGET_PATH!" (
    if /i "!TARGET_NAME:~-4!"==".exe" (
        set "RESOLVED_PYTHON=!TARGET_PATH!"
        exit /b 0
    )
)

if exist "!TARGET_PATH!\" (
    if exist "!TARGET_PATH!\python.exe" (
        set "RESOLVED_PYTHON=!TARGET_PATH!\python.exe"
        exit /b 0
    )
    if exist "!TARGET_PATH!\python3.exe" (
        set "RESOLVED_PYTHON=!TARGET_PATH!\python3.exe"
        exit /b 0
    )
)

if /i "!TARGET_NAME:~-4!"==".dll" (
    if exist "!TARGET_DIR!python.exe" (
        set "RESOLVED_PYTHON=!TARGET_DIR!python.exe"
        exit /b 0
    )
    if exist "!TARGET_DIR!python3.exe" (
        set "RESOLVED_PYTHON=!TARGET_DIR!python3.exe"
        exit /b 0
    )
    set "DLL_VER=!TARGET_BASE:python=!"
    if not "!DLL_VER!"=="!TARGET_BASE!" (
        if exist "!TARGET_DIR!python!DLL_VER!.exe" (
            set "RESOLVED_PYTHON=!TARGET_DIR!python!DLL_VER!.exe"
            exit /b 0
        )
    )
)

exit /b 1

:try_install_requirements
%PIP_CMD% --version >nul 2>&1
if errorlevel 1 exit /b 1
echo [*] Installing dependencies with %PIP_CMD%

:: Windows ARM64: Install cryptography with pre-built wheel first
if !ARM64! equ 1 (
    echo [*] Windows ARM64 detected: Installing cryptography with pre-built wheel...
    %PIP_CMD% install --upgrade pip >nul 2>&1
    %PIP_CMD% install cryptography --only-binary=:all: >nul 2>&1
    if !errorlevel! equ 0 (
        echo [+] Pre-built cryptography wheel installed successfully
    ) else (
        echo [!] Pre-built wheel not available, trying specific version...
        %PIP_CMD% install "cryptography>=41.0.0" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [!] cryptography installation may have issues, continuing...
        )
    )
)

:: Ensure Anthropic SDK is installed (core dependency)
echo [*] Installing Anthropic SDK...
%PIP_CMD% install "anthropic>=0.39.0" >nul 2>&1

:: --no-warn-script-location: pip's "script X.exe is installed in ... which is
:: not on PATH" WARNING goes to stderr; the PowerShell wrapper treats stderr
:: from this script as failure noise, so suppress the warning at the source.
%PIP_CMD% install --no-warn-script-location -r "%SCRIPT_DIR%\requirements.txt"
if errorlevel 1 (
    echo [!] Dependency install failed with %PIP_CMD%
    exit /b 1
)
echo [+] Dependencies installed successfully
exit /b 0

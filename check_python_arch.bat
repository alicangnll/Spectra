@echo off
:: Python Architecture Checker for Spectra
:: Shows all Python installations and their architectures

echo ========================================
echo Spectra Python Architecture Checker
echo ========================================
echo.

:: Check ARM64 indicator
set "ARM64=0"
if defined PROCESSOR_ARCHITEW6432 (
    if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARM64=1"
)
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARM64=1"

if !ARM64! equ 1 (
    echo [System] Windows ARM64 detected
) else (
    echo [System] Windows x64 detected
)
echo.

:: Check Python Launcher
echo [*] Checking Python Launcher (py)...
where py >nul 2>&1
if not errorlevel 1 (
    py --list
    echo.
    for /f "tokens=*" %%i in ('py -3 -c "import sys, platform; print(f'{platform.machine()} {sys.version}')" 2^>nul') do (
        echo [py -3] %%i
    )
) else (
    echo [!] Python Launcher not found
)
echo.

:: Check Python in Program Files (x64)
echo [*] Checking Program Files (x64 Python)...
for %%V in (312 313 314 315) do (
    if exist "C:\Program Files\Python3%%V\python.exe" (
        echo [+] Found: C:\Program Files\Python3%%V\python.exe
        "C:\Program Files\Python3%%V\python.exe" -c "import sys, platform; print(f'    Architecture: {platform.machine()}'); print(f'    Version: {sys.version.split()[0]}')" 2>nul
        echo.
    )
)

:: Check Python in AppData (likely ARM64 on ARM64 Windows)
echo [*] Checking AppData (may be ARM64)...
for %%V in (310 311 312 313 314) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" (
        echo [+] Found: %LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe
        "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" -c "import sys, platform; print(f'    Architecture: {platform.machine()}'); print(f'    Version: {sys.version.split()[0]}')" 2>nul
        echo.
    )
)

:: Check system PATH Python
echo [*] Checking system PATH Python...
where python >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('where python') do (
        echo [+] Found: %%i
        "%%i" -c "import sys, platform; print(f'    Architecture: {platform.machine()}'); print(f'    Version: {sys.version.split()[0]}')" 2>nul
        echo.
    )
)

:: Check for anthropic in each Python
echo ========================================
echo Checking anthropic installation
echo ========================================
echo.

for %%V in (312 313 314 315) do (
    if exist "C:\Program Files\Python3%%V\python.exe" (
        echo [*] Checking C:\Program Files\Python3%%V\python.exe...
        "C:\Program Files\Python3%%V\python.exe" -c "import anthropic; print('    [+] anthropic installed')" 2>nul
        if errorlevel 1 (
            echo     [!] anthropic NOT installed
        )
        echo.
    )
)

for %%V in (310 311 312 313 314) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" (
        echo [*] Checking %LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe...
        "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" -c "import anthropic; print('    [+] anthropic installed')" 2>nul
        if errorlevel 1 (
            echo     [!] anthropic NOT installed
        )
        echo.
    )
)

echo ========================================
echo Recommendations
echo ========================================
echo.
echo For IDA Pro on Windows ARM64:
echo - Use x64 Python (from Program Files)
echo - NOT ARM64 Python (from AppData)
echo.
echo Install x64 Python from: https://www.python.org/downloads/
echo Choose "Windows installer (64-bit)", NOT ARM64
echo.
pause

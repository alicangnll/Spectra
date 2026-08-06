@echo off
:: Tüm Python kurulumlarını bul ve mimarilerini kontrol et

echo ========================================
echo Tum Python Kurulumlari ve Mimari
echo ========================================
echo.

:: 1. C:\Program Files (x64 muhtemelen)
for %%V in (310 311 312 313 314 315) do (
    if exist "C:\Program Files\Python3%%V\python.exe" (
        echo [+] C:\Program Files\Python3%%V\python.exe
        "C:\Program Files\Python3%%V\python.exe" -c "import platform; print('   Mimari:', platform.machine())" 2>nul
        echo.
    )
)

:: 2. C:\Python3* (manuel kurulum)
for %%V in (310 311 312 313 314 315) do (
    if exist "C:\Python3%%V\python.exe" (
        echo [+] C:\Python3%%V\python.exe
        "C:\Python3%%V\python.exe" -c "import platform; print('   Mimari:', platform.machine())" 2>nul
        echo.
    )
)

:: 3. AppData (ARM64 muhtemelen)
for %%V in (310 311 312 313 314 315) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" (
        echo [] %LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe
        "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" -c "import platform; print('   Mimari:', platform.machine())" 2>nul
        echo.
    )
)

:: 4. py launcher
where py >nul 2>&1
if not errorlevel 1 (
    echo [+] Python Launcher (py):
    py --list 2>nul
    echo.
)

echo ========================================
echo IDA Pro icin GEREKLI: AMD64 (x64) Python
echo ARM64 Python IDA Pro ile calismaz!
echo ========================================
echo.
pause

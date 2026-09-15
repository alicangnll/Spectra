# ──────────────────────────────────────────────────────────────────────
# Spectra — universal installer (Windows)
#
#   irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1 | iex
#
# Or with arguments:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1))) -Target ida
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1))) -Target binja
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1))) -Target both
#
# Environment variables:
#   SPECTRA_DIR     — where to clone the repo   (default: ~\.spectra)
#   SPECTRA_BRANCH  — git branch to check out   (default: main)
#   IDADIR          — override IDA install dir  (forwarded to install_ida.bat)
#   IDA_PYTHON      — override Python for IDA    (forwarded to install_ida.bat)
#   BN_PYTHON       — override Python for BN     (forwarded to install_binaryninja.bat)
# ──────────────────────────────────────────────────────────────────────

param(
    [ValidateSet("ida", "binja", "both", "")]
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/alicangnll/Spectra.git"
$InstallDir = if ($env:SPECTRA_DIR) { $env:SPECTRA_DIR } else { Join-Path $HOME ".spectra" }
$Branch = if ($env:SPECTRA_BRANCH) { $env:SPECTRA_BRANCH } else { "main" }

# ── Helpers ──────────────────────────────────────────────────────────
function Write-Info    { param($Msg) Write-Host "[*] $Msg" -ForegroundColor Cyan }
function Write-Ok      { param($Msg) Write-Host "[+] $Msg" -ForegroundColor Green }
function Write-Warn    { param($Msg) Write-Host "[!] $Msg" -ForegroundColor Yellow }
function Write-Err     { param($Msg) Write-Host "[-] $Msg" -ForegroundColor Red }

# Run a native command with its stderr suppressed, safely under
# $ErrorActionPreference = "Stop". PowerShell 5.1 wraps ANY redirected
# native stderr line as an ErrorRecord, and "Stop" turns the first one
# into a terminating RemoteException (bash — install.sh — never does
# this; 2>/dev/null is purely cosmetic there). Equivalent of bash's
# `cmd 2>/dev/null || true`.
function Invoke-Silent {
    param([scriptblock]$Command)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command 2>$null
    }
    catch {
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Show-Banner {
    Write-Host ""
    Write-Host "    +==========================================+" -ForegroundColor White
    Write-Host "    |            六眼  Spectra                 |" -ForegroundColor White
    Write-Host "    |     Reverse Engineering AI Agent         |" -ForegroundColor White
    Write-Host "    |        IDA Pro  .  Binary Ninja          |" -ForegroundColor White
    Write-Host "    +==========================================+" -ForegroundColor White
    Write-Host ""
}

# ── Detection ────────────────────────────────────────────────────────
function Test-ARM64 {
    return [Environment]::Is64BitOperatingSystem -and
           ($env:PROCESSOR_ARCHITECTURE -eq "ARM64" -or $env:PROCESSOR_ARCHITEW6432 -eq "ARM64")
}

function Test-VSBuildTools {
    # Check for Visual Studio Build Tools
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        $installation = Invoke-Silent { & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath }
        return $installation -ne $null
    }
    return $false
}

function Test-IDA {
    # Registry
    $regPaths = @(
        "HKCU:\Software\Hex-Rays\IDA",
        "HKLM:\SOFTWARE\Hex-Rays\IDA"
    )
    foreach ($rp in $regPaths) {
        if (Test-Path $rp) { return $true }
    }
    # AppData user dir
    $idaDir = Join-Path $env:APPDATA "Hex-Rays\IDA Pro"
    if (Test-Path $idaDir) { return $true }
    # USERPROFILE\.idapro
    $idapro = Join-Path $HOME ".idapro"
    if (Test-Path $idapro) { return $true }
    # IDA in PATH
    if (Get-Command "idapyswitch.exe" -ErrorAction SilentlyContinue) { return $true }
    if (Get-Command "ida64.exe" -ErrorAction SilentlyContinue) { return $true }
    if (Get-Command "idat64.exe" -ErrorAction SilentlyContinue) { return $true }
    return $false
}

function Test-BinaryNinja {
    # AppData user dir
    $bnDir = Join-Path $env:APPDATA "Binary Ninja"
    if (Test-Path $bnDir) { return $true }
    # Common install locations
    $installPaths = @(
        "${env:ProgramFiles}\Vector35\BinaryNinja",
        "${env:ProgramFiles(x86)}\Vector35\BinaryNinja",
        "${env:LOCALAPPDATA}\Vector35\BinaryNinja"
    )
    foreach ($p in $installPaths) {
        if (Test-Path $p) { return $true }
    }
    return $false
}

function Find-ByteSequenceIndex {
    param(
        [byte[]]$Data,
        [byte[]]$Needle
    )

    if (-not $Data -or -not $Needle -or $Needle.Length -eq 0 -or $Needle.Length -gt $Data.Length) {
        return -1
    }

    for ($i = 0; $i -le ($Data.Length - $Needle.Length); $i++) {
        $matched = $true
        for ($j = 0; $j -lt $Needle.Length; $j++) {
            if ($Data[$i + $j] -ne $Needle[$j]) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            return $i
        }
    }

    return -1
}

function Get-IdaUserDir {
    $candidates = @()

    if ($env:APPDATA) {
        $candidates += (Join-Path $env:APPDATA "Hex-Rays\IDA Pro")
    }
    if ($HOME) {
        $candidates += (Join-Path $HOME ".idapro")
    }
    if ($env:IDAUSR) {
        $candidates += $env:IDAUSR
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    if ($env:APPDATA) {
        return (Join-Path $env:APPDATA "Hex-Rays\IDA Pro")
    }

    return $null
}

function Get-IdaInstallDir {
    if ($env:IDADIR -and (Test-Path $env:IDADIR)) {
        return $env:IDADIR
    }

    $regPaths = @(
        "HKCU:\Software\Hex-Rays\IDA",
        "HKCU:\Software\Hex-Rays\IDA Pro",
        "HKLM:\SOFTWARE\Hex-Rays\IDA",
        "HKLM:\SOFTWARE\Hex-Rays\IDA Pro",
        "HKLM:\SOFTWARE\Hex-Rays\IDA Professional",
        "HKLM:\SOFTWARE\WOW6432Node\Hex-Rays\IDA",
        "HKLM:\SOFTWARE\WOW6432Node\Hex-Rays\IDA Pro",
        "HKLM:\SOFTWARE\WOW6432Node\Hex-Rays\IDA Professional",
        "HKLM:\SOFTWARE\Hex-Rays SA\IDA Professional 9.1",
        "HKCU:\Software\Hex-Rays SA\IDA Professional 9.1",
        "HKLM:\SOFTWARE\WOW6432Node\Hex-Rays SA\IDA Professional 9.1"
    )
    foreach ($rp in $regPaths) {
        try {
            $location = (Get-ItemProperty -Path $rp -ErrorAction Stop).Location
            if ($location -and (Test-Path $location)) {
                return $location
            }
        }
        catch {
        }
    }

    # idapyswitch.exe lives in the IDA install root — the strongest PATH
    # signal (ida64.exe may be shimmed); check it first.
    foreach ($name in @("idapyswitch.exe", "ida64.exe", "idat64.exe", "ida.exe", "idat.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return (Split-Path -Parent $command.Source)
        }
    }

    $installPaths = @(
        "${env:ProgramFiles}\Hex-Rays\IDA Pro",
        "${env:ProgramFiles}\Hex-Rays\IDA Professional",
        "${env:ProgramFiles}\IDA Pro",
        "${env:ProgramFiles}\IDA Professional 9",
        "${env:ProgramFiles}\IDA Professional 9.1",
        "${env:ProgramFiles(x86)}\Hex-Rays\IDA Pro",
        "${env:ProgramFiles(x86)}\Hex-Rays\IDA Professional",
        "${env:ProgramFiles(x86)}\IDA Pro",
        "${env:ProgramFiles(x86)}\IDA Professional 9"
    )
    foreach ($path in $installPaths) {
        if ($path -and (Test-Path $path)) {
            return $path
        }
    }

    return $null
}

function Get-IdaRegPythonTarget {
    param([string]$UserDir)

    if (-not $UserDir) {
        return $null
    }

    $regFile = Join-Path $UserDir "ida.reg"
    if (-not (Test-Path $regFile -PathType Leaf)) {
        return $null
    }

    try {
        $data = [System.IO.File]::ReadAllBytes($regFile)
    }
    catch {
        return $null
    }

    $needle = [System.Text.Encoding]::ASCII.GetBytes("Python3TargetDLL")
    $idx = Find-ByteSequenceIndex -Data $data -Needle $needle
    if ($idx -lt 0) {
        return $null
    }

    $keyEnd = $idx
    while ($keyEnd -lt $data.Length -and $data[$keyEnd] -ne 0) {
        $keyEnd++
    }

    if (($keyEnd + 6) -gt $data.Length) {
        return $null
    }

    $length = [System.BitConverter]::ToInt32($data, $keyEnd + 1)
    if ($length -le 0 -or $length -gt 4096) {
        return $null
    }

    $valueStart = $keyEnd + 6
    if (($valueStart + $length) -gt $data.Length) {
        return $null
    }

    [byte[]]$valueBytes = $data[$valueStart..($valueStart + $length - 1)]
    $path = [System.Text.Encoding]::UTF8.GetString($valueBytes).Trim([char]0, ' ')
    if ($path -match '^(?:[A-Za-z]:\\|\\\\)') {
        return $path
    }

    return $null
}

function Resolve-IdaPythonExecutable {
    param([string]$TargetPath)

    if (-not $TargetPath) {
        return $null
    }

    $target = $TargetPath.Trim().Trim('"').Trim("'")
    if (-not $target) {
        return $null
    }

    if (Test-Path $target -PathType Leaf) {
        $leaf = [System.IO.Path]::GetFileName($target)
        if ($leaf -match '^python(?:3|[0-9]+)?\.exe$') {
            return $target
        }
    }

    $candidates = [System.Collections.Generic.List[string]]::new()

    if (Test-Path $target -PathType Container) {
        $candidates.Add((Join-Path $target "python.exe"))
        $candidates.Add((Join-Path $target "python3.exe"))
    }
    else {
        $parent = Split-Path -Parent $target
        $leaf = [System.IO.Path]::GetFileName($target)

        if ($leaf -match '^python([0-9]+)?\.dll$') {
            $digits = $Matches[1]
            if ($digits) {
                $candidates.Add((Join-Path $parent "python$digits.exe"))
            }
            $candidates.Add((Join-Path $parent "python.exe"))
            $candidates.Add((Join-Path $parent "python3.exe"))
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return $candidate
        }
    }

    if ($leaf -match '^python([0-9]+)\.dll$') {
        $digits = $Matches[1]
        if ($digits.Length -ge 2) {
            $versionName = "python$($digits.Substring(0, 1)).$($digits.Substring(1))"
            $command = Get-Command $versionName -ErrorAction SilentlyContinue
            if ($command -and $command.Source) {
                return $command.Source
            }
        }
    }

    return $null
}

function Test-PythonExecutable {
    param([string]$Path)

    if (-not $Path -or -not (Test-Path $Path -PathType Leaf)) {
        return $false
    }

    # The Microsoft Store "App Installer" aliases under \WindowsApps\ are
    # stubs when Store Python is absent: they print "Python was not found"
    # and exit 9009. Only a binary that actually runs counts as a Python.
    # Run directly (no Start-Process): its file-redirect parameters reject
    # device paths like NUL on some systems, which used to mark EVERY
    # candidate as unusable ("No stable system Python found").
    Invoke-Silent { & $Path -c "import sys" }
    return ($LASTEXITCODE -eq 0)
}

function Test-PythonIsStable {
    param([string]$Path)

    if (-not (Test-PythonExecutable $Path)) {
        return $false
    }
    # Prerelease builds (e.g. "3.15.0a5") have no pip wheels for the
    # dependencies Spectra installs into IDA's Python (PySide6, anthropic).
    # Only final releases qualify.
    Invoke-Silent { & $Path -c "import sys; sys.exit(0 if sys.version_info.releaselevel == 'final' else 1)" }
    return ($LASTEXITCODE -eq 0)
}

function Get-PythonVersionString {
    param([string]$Path)

    $out = Invoke-Silent { & $Path -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))" }
    if ($out) {
        return ( (@($out) | Select-Object -First 1).Trim() )
    }
    return $null
}

function Get-StableSystemPythons {
    # Enumerate standalone CPython installs, newest version first, keeping
    # only final releases that actually execute (Store stubs filtered).
    $seen = @{}
    $candidates = [System.Collections.Generic.List[string]]::new()

    # Official launcher: py -0p lists installed distributions with paths
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $listing = Invoke-Silent { & py -0p }
        foreach ($line in @($listing)) {
            if ($line -match '([A-Za-z]:\\\S+pythonw?\.exe)') {
                $exe = $Matches[1]
                if (-not $seen.ContainsKey($exe.ToLower())) {
                    $seen[$exe.ToLower()] = $true
                    $candidates.Add($exe)
                }
            }
        }
    }

    foreach ($glob in @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "${env:ProgramFiles}\Python3*\python.exe",
        "${env:ProgramFiles(x86)}\Python3*\python.exe"
    )) {
        foreach ($item in (Get-Item $glob -ErrorAction SilentlyContinue)) {
            $exe = $item.FullName
            if (-not $seen.ContainsKey($exe.ToLower())) {
                $seen[$exe.ToLower()] = $true
                $candidates.Add($exe)
            }
        }
    }

    $stable = @()
    foreach ($exe in $candidates) {
        if (Test-PythonIsStable $exe) {
            $stable += [pscustomobject]@{
                Exe     = $exe
                Version = (Get-PythonVersionString $exe)
            }
        }
    }

    # "3.10" must outrank "3.9": compare major*100+minor, not a double
    $sorted = @($stable | Sort-Object {
        $parts = "$($_.Version)".Split('.')
        if ($parts.Count -eq 2) { [int]$parts[0] * 100 + [int]$parts[1] } else { 0 }
    } -Descending)

    if ($sorted.Count -gt 0) {
        $listing = ($sorted | ForEach-Object { "v$($_.Version) ($($_.Exe))" }) -join ", "
        Write-Info "Stable system Python found: $listing"
    }
    return $sorted
}

function Ensure-IdaPythonSelection {
    # Windows counterpart of macOS/Linux, where IDA naturally runs against
    # a regular system Python. If IDA's current Python is missing or a
    # prerelease (no wheels for PySide6/anthropic), switch IDA to the
    # newest stable system Python via idapyswitch. A healthy current
    # selection is kept untouched.
    #
    # Returns the python.exe ALL pip installs must target: the freshly
    # switched one, the already-good current one, or $null when nothing
    # could be selected.
    param([string]$IdaInstallDir)

    if (-not $IdaInstallDir) {
        return
    }

    $idapyswitch = Join-Path $IdaInstallDir "idapyswitch.exe"
    if (-not (Test-Path $idapyswitch -PathType Leaf)) {
        return
    }

    $currentTarget = Get-IdaRegPythonTarget -UserDir (Get-IdaUserDir)
    $currentExe = Resolve-IdaPythonExecutable -TargetPath $currentTarget
    if ($currentExe -and (Test-PythonIsStable $currentExe)) {
        Write-Info "IDA already uses a stable Python: $currentExe (v$(Get-PythonVersionString $currentExe))"
        return $currentExe
    }

    if ($currentExe) {
        Write-Warn "IDA's current Python is a prerelease or unusable: $currentExe"
    }
    else {
        Write-Info "IDA has no usable Python selected yet"
    }

    $stable = Get-StableSystemPythons
    if (-not $stable) {
        Write-Warn "No stable system Python found - leaving IDA's Python selection unchanged."
        Write-Warn "Install one from https://www.python.org/downloads/ and rerun this installer."
        return $null
    }

    $choice = @($stable)[0]
    $choiceDir = Split-Path -Parent $choice.Exe
    $dll = Join-Path $choiceDir ("python" + "$($choice.Version)".Replace(".", "") + ".dll")
    if (-not (Test-Path $dll -PathType Leaf)) {
        Write-Warn "No python DLL next to $($choice.Exe) - leaving selection unchanged"
        return $null
    }

    Write-Info "Selecting Python $($choice.Version) for IDA (same as macOS/Linux setups): $($choice.Exe)"
    & $idapyswitch --force-path $dll
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "idapyswitch failed (exit $LASTEXITCODE) - IDA keeps its current Python"
        return $null
    }
    Write-Ok "IDA Python switched to v$($choice.Version): $dll"
    return $choice.Exe
}

function Get-IdaPython {
    $userDir = Get-IdaUserDir
    $pythonTarget = Get-IdaRegPythonTarget -UserDir $userDir
    $resolved = Resolve-IdaPythonExecutable -TargetPath $pythonTarget
    if (Test-PythonExecutable $resolved) {
        return $resolved
    }

    $installDir = Get-IdaInstallDir
    if (-not $installDir) {
        return $null
    }

    # Check for Python 3.x directories
    $python3Dirs = Get-ChildItem -Path (Join-Path $installDir "python3*") -Directory -ErrorAction SilentlyContinue
    if ($python3Dirs) {
        $sortedDirs = $python3Dirs | Sort-Object FullName -Descending
        foreach ($dir in $sortedDirs) {
            foreach ($name in @("python.exe", "python3.exe")) {
                $candidate = Join-Path $dir.FullName $name
                if (Test-PythonExecutable $candidate) {
                    return $candidate
                }
            }
        }
    }

    # Check python\ subdirectory
    foreach ($candidate in @(
        (Join-Path $installDir "python\python.exe"),
        (Join-Path $installDir "python\python3.exe")
    )) {
        if (Test-PythonExecutable $candidate) {
            return $candidate
        }
    }

    # Try idapyswitch
    $idapyswitch = Join-Path $installDir "idapyswitch.exe"
    if (Test-Path $idapyswitch -PathType Leaf) {
        try {
            $output = Invoke-Silent { & $idapyswitch --show-current }
            if ($output) {
                foreach ($line in $output) {
                    $target = $line.Trim().Trim("'")
                    if ($target -like "Path:*") {
                        $target = $target.Substring(5).Trim()
                    }
                    if ($target) {
                        $resolved = Resolve-IdaPythonExecutable -TargetPath $target
                        if (Test-PythonExecutable $resolved) {
                            return $resolved
                        }
                    }
                }
            }
        } catch {
            # idapyswitch failed, continue to fallbacks
        }
    }

    # Final fallback: try common system Python installations. Every
    # candidate must pass the execution check (filters Store stubs).
    $systemPythonPaths = @(
        "python",
        "python3",
        "py",
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python*.exe"
    )

    foreach ($pathPattern in $systemPythonPaths) {
        $matches = Get-Command $pathPattern -ErrorAction SilentlyContinue
        if ($matches) {
            foreach ($command in @($matches)) {
                if (Test-PythonExecutable $command.Source) {
                    return $command.Source
                }
            }
        }
    }

    return $null
}

# ── Prerequisites ────────────────────────────────────────────────────
function Test-Prerequisites {
    if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
        Write-Err "git is required but not installed."
        Write-Err "Install from: https://git-scm.com/download/win"
        Write-Err "Or: winget install Git.Git"
        exit 1
    }

    # Parity with install.sh's check_prereqs: Python is not fatal — the
    # per-host installer will attempt to find the bundled Python.
    $hasPython = @("python3", "python", "py") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue }
    if (-not $hasPython) {
        Write-Warn "Python not found in PATH -- the per-host installer will attempt to find the bundled Python."
    }
}

# ── Clone or update ──────────────────────────────────────────────────
function Install-Repository {
    $gitDir = Join-Path $InstallDir ".git"
    if (Test-Path $gitDir) {
        Write-Info "Updating existing installation at $InstallDir..."
        # Mirrors install.sh: fetch/reset failures abort with git's own
        # error visible (no redirect); checkout is best-effort (|| true).
        git -C $InstallDir fetch origin $Branch --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Err "git fetch failed"
            exit 1
        }
        Invoke-Silent { git -C $InstallDir checkout $Branch --quiet }
        git -C $InstallDir reset --hard "origin/$Branch" --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Err "git reset failed"
            exit 1
        }
        Write-Ok "Updated to latest $Branch"
    }
    else {
        if (Test-Path $InstallDir) {
            $backup = "${InstallDir}.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
            Write-Warn "$InstallDir exists but is not a git repo -- backing up to $backup"
            Rename-Item $InstallDir $backup
        }
        Write-Info "Cloning Spectra into $InstallDir..."
        # No stderr redirect: on failure git's message must stay visible
        # instead of becoming a RemoteException.
        git clone --branch $Branch --depth 1 $RepoUrl $InstallDir --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Err "git clone failed"
            exit 1
        }
        Write-Ok "Cloned successfully"
    }

    # Clear Python cache to ensure fresh module loading
    Clear-PythonCache
}

# ── Clear Python cache ──────────────────────────────────────────────────
function Clear-PythonCache {
    Write-Info "Clearing Python cache..."
    $cacheCount = 0

    # Clear __pycache__ directories in Spectra installation
    if (Test-Path $InstallDir) {
        Get-ChildItem -Path $InstallDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $cacheCount++
        }

        # Clear .pyc files
        Get-ChildItem -Path $InstallDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            $cacheCount++
        }
    }

    # Clear IDA plugin cache if present
    $idaCacheDir = Join-Path $HOME ".idapro\plugins\__pycache__"
    if (Test-Path $idaCacheDir) {
        Get-ChildItem -Path $idaCacheDir -Filter "spectra*" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $cacheCount++
        }
    }

    # Clear Binary Ninja plugin cache if present
    $bnCacheDir = Join-Path $HOME ".binaryninja\plugins\__pycache__"
    if (Test-Path $bnCacheDir) {
        Get-ChildItem -Path $bnCacheDir -Filter "spectra*" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $cacheCount++
        }
    }

    if ($cacheCount -gt 0) {
        Write-Ok "Cleared $cacheCount Python cache entries"
    } else {
        Write-Info "No Python cache to clear"
    }
}

# ── Run installers ───────────────────────────────────────────────────
function Install-IDA {
    $script = Join-Path $InstallDir "install_ida.bat"
    if (-not (Test-Path $script)) {
        Write-Err "install_ida.bat not found in $InstallDir"
        return $false
    }
    Write-Info "Running IDA Pro installer..."
    Write-Host ""

    # Try to resolve IDA install dir and Python for better performance
    $setIdaDir = $false
    if (-not $env:IDADIR) {
        $resolvedIdaDir = Get-IdaInstallDir
        if ($resolvedIdaDir) {
            Write-Info "Detected IDA installation directory: $resolvedIdaDir"
            $env:IDADIR = $resolvedIdaDir
            $setIdaDir = $true
        }
        else {
            # Auto-detection failed — ask instead of guessing.
            Write-Warn "Could not auto-detect the IDA Pro installation directory."
            $answer = Read-Host "    Enter IDA Pro directory (Enter to skip)"
            if ($answer -and (Test-Path $answer)) {
                $env:IDADIR = (Resolve-Path $answer).Path
                $setIdaDir = $true
                Write-Info "Using provided IDA directory: $($env:IDADIR)"
            }
            elseif ($answer) {
                Write-Warn "Directory not found: $answer - continuing without it"
            }
        }
    }

    # Make sure IDA runs against a stable system Python (macOS/Linux
    # parity): switch via idapyswitch when the current one is a
    # prerelease/missing, BEFORE resolving the python the deps go into.
    # Every pip install below targets the SELECTED python.
    $selectedPython = $null
    if ($env:IDADIR) {
        $selectedPython = Ensure-IdaPythonSelection -IdaInstallDir $env:IDADIR
    }

    $setIdaPython = $false
    if (-not $env:IDA_PYTHON) {
        # Prefer the just-selected python directly; fall back to the
        # general discovery only when no selection could be made.
        $resolvedIdaPython = if ($selectedPython) { $selectedPython } else { Get-IdaPython }
        if ($resolvedIdaPython) {
            Write-Info "Resolved IDA Python: $resolvedIdaPython"
            $env:IDA_PYTHON = $resolvedIdaPython
            $setIdaPython = $true
        }
    }

    # Run the batch installer
    Push-Location $InstallDir
    try {
        # Same approach as install.sh's run_ida_installer (`bash "$script"`):
        # stream the installer's output directly to the console and judge
        # success by exit code. Do NOT capture with 2>&1 — PowerShell 5.1
        # wraps redirected native stderr as ErrorRecords, and under
        # $ErrorActionPreference = "Stop" the first one (e.g. pip's benign
        # "script ... not on PATH" WARNING) becomes a terminating
        # RemoteException. Unredirected stderr simply prints, like bash.
        & cmd.exe /c $script
        $success = $LASTEXITCODE -eq 0
    }
    finally {
        Pop-Location
        if ($setIdaPython) {
            Remove-Item Env:IDA_PYTHON -ErrorAction SilentlyContinue
        }
        if ($setIdaDir) {
            Remove-Item Env:IDADIR -ErrorAction SilentlyContinue
        }
    }
    return $success
}

function Install-BinaryNinja {
    $script = Join-Path $InstallDir "install_binaryninja.bat"
    if (-not (Test-Path $script)) {
        Write-Err "install_binaryninja.bat not found in $InstallDir"
        return $false
    }
    Write-Info "Running Binary Ninja installer..."
    Write-Host ""
    Push-Location $InstallDir
    try {
        # Same as Install-IDA: stream output directly, judge by exit code.
        & cmd.exe /c $script
        $success = $LASTEXITCODE -eq 0
    }
    finally { Pop-Location }
    return $success
}

# ── Skills installation ────────────────────────────────────────────────────
function Setup-Skills {
    $skillsDir = Join-Path $env:USERPROFILE ".claude\skills"
    $claudeExtSource = Join-Path $InstallDir "claude_ext"

    # Ensure ~/.claude/skills exists
    if (-not (Test-Path $skillsDir)) {
        try {
            New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
        }
        catch {
            Write-Warn "Could not create $skillsDir - skipping skills installation"
            return
        }
    }

    # Copy claude_ext to ~/.claude/skills if it exists
    if (Test-Path $claudeExtSource) {
        $targetDir = Join-Path $skillsDir "claude_ext"
        Write-Info "Copying claude_ext to ~/.claude/skills..."

        # Remove existing directory if present
        if (Test-Path $targetDir) {
            Remove-Item $targetDir -Recurse -Force
        }

        # Copy directory
        Copy-Item -Path $claudeExtSource -Destination $targetDir -Recurse -Force
        Write-Ok "Skills installed: $targetDir"
    }
    else {
        Write-Warn "claude_ext not found in $InstallDir - skipping skills installation"
    }
}

# ── CLI dependencies setup ────────────────────────────────────────────────────
function Setup-CLIDependencies {
    Write-Info "Setting up CLI dependencies..."

    # Windows uses PySide6 (Qt6) by default — same as install.sh's
    # non-macOS branch. Resolve which Python drives pip (python3 ->
    # python -> py -3), mirroring install.sh's pip3 fallback chain.
    $showCmd = $installCmd = $null
    if (Get-Command "python3" -ErrorAction SilentlyContinue) {
        $showCmd = { python3 -m pip show PySide6 }
        $installCmd = { python3 -m pip install PySide6 --disable-pip-version-check }
    }
    elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
        $showCmd = { python -m pip show PySide6 }
        $installCmd = { python -m pip install PySide6 --disable-pip-version-check }
    }
    elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
        $showCmd = { py -3 -m pip show PySide6 }
        $installCmd = { py -3 -m pip install PySide6 --disable-pip-version-check }
    }
    else {
        Write-Warn "No Python found - skipping CLI dependencies"
        return
    }

    $pyside6Installed = Invoke-Silent $showCmd
    if (-not $pyside6Installed) {
        Write-Info "Installing PySide6..."
        Invoke-Silent $installCmd | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "PySide6 installed successfully"
        }
        else {
            Write-Warn "Failed to install PySide6 - CLI may not work properly"
        }
    }
    else {
        Write-Ok "PySide6 already installed"
    }
}

# ── CLI wrapper setup ────────────────────────────────────────────────────
function Setup-CLIWrapper {
    # Create CLI wrapper script in repository root
    $repoWrapper = Join-Path $InstallDir "spectra-cli.ps1"
    $wrapperContent = @"
#!/usr/bin/env pwsh
# Spectra CLI wrapper - launches interactive Spectra CLI shell
# Usage: .\spectra-cli [target_directory]

`$SCRIPT_DIR = Split-Path -Parent `$PSCommandPath
`$WORK_DIR = if (`$args.Count -gt 0) { `$args[0] } else { "." }

python3 "`$SCRIPT_DIR\spectra_cli.py" dir_loc "`$WORK_DIR"
"@
    $wrapperContent | Out-File -FilePath $repoWrapper -Encoding UTF8

    # Determine install location for the wrapper script
    $binDir = Join-Path $env:USERPROFILE ".local\bin"
    if (-not (Test-Path $binDir)) {
        try {
            New-Item -ItemType Directory -Path $binDir -Force | Out-Null
        }
        catch {
            $binDir = Join-Path $InstallDir "bin"
            New-Item -ItemType Directory -Path $binDir -Force | Out-Null
        }
    }

    $targetCmd = Join-Path $binDir "spectra.ps1"
    $oldLink = Join-Path $binDir "spectra-cli.ps1"

    # Remove old symlinks/files if present
    if (Test-Path $oldLink) { Remove-Item $oldLink -Force }
    if (Test-Path $targetCmd) { Remove-Item $targetCmd -Force }

    # Write a direct, robust launcher script to binDir
    $launcherContent = @"
#!/usr/bin/env pwsh
# Spectra CLI launcher
`$WORK_DIR = if (`$args.Count -gt 0) { `$args[0] } else { "." }
python3 "$InstallDir\spectra_cli.py" dir_loc "`$WORK_DIR"
"@
    $launcherContent | Out-File -FilePath $targetCmd -Encoding UTF8
    Write-Ok "CLI wrapper installed: $targetCmd"

    # Check if binDir is in PATH
    $pathEntries = $env:PATH -split ';'
    if ($binDir -notin $pathEntries) {
        Write-Host ""
        Write-Warn "⚠️  $binDir is not in your PATH"
        Write-Warn "Add it using:"
        Write-Warn "  [Environment]::SetEnvironmentVariable('Path', `$env:PATH + ';$binDir', 'User')"
        Write-Warn "Then restart your terminal."
    }
    else {
        Write-Ok "✓ $binDir is already in your PATH"
    }

    Write-Host ""
    Write-Info "Usage:"
    Write-Host "  spectra          # Start Spectra in current directory" -ForegroundColor Cyan
    Write-Host "  spectra C:\path   # Start Spectra in specified directory" -ForegroundColor Cyan
    Write-Host ""
}

# ── Main ─────────────────────────────────────────────────────────────
Show-Banner
Test-Prerequisites

# Windows ARM64 check
$isARM64 = Test-ARM64
if ($isARM64) {
    Write-Info "Windows ARM64 detected"
    $hasBuildTools = Test-VSBuildTools
    if (-not $hasBuildTools) {
        Write-Warn "Visual Studio Build Tools not found. Some Python packages may fail to build."
        Write-Warn "For best results, install: winget install Microsoft.VisualStudio.2022.BuildTools"
        Write-Host ""
        $response = Read-Host "Continue anyway? (Y/N)"
        if ($response -ne "Y" -and $response -ne "y") {
            exit 0
        }
    }
}

# Auto-detect if no target specified
if (-not $Target) {
    $hasIda = Test-IDA
    $hasBinja = Test-BinaryNinja

    if ($hasIda -and $hasBinja) {
        $Target = "both"
        Write-Ok "Detected both IDA Pro and Binary Ninja"
    }
    elseif ($hasIda) {
        $Target = "ida"
        Write-Ok "Detected IDA Pro"
    }
    elseif ($hasBinja) {
        $Target = "binja"
        Write-Ok "Detected Binary Ninja"
    }
    else {
        Write-Warn "No IDA Pro or Binary Ninja installation detected."
        Write-Warn "Installing anyway -- defaulting to both."
        $Target = "both"
    }
}

Write-Info "Target: $Target"
Write-Info "Install directory: $InstallDir"
Write-Host ""

Install-Repository
Write-Host ""

$failed = $false

switch ($Target) {
    "ida" {
        if (-not (Install-IDA)) { $failed = $true }
    }
    "binja" {
        if (-not (Install-BinaryNinja)) { $failed = $true }
    }
    "both" {
        if (-not (Install-IDA))   { Write-Warn "IDA installation failed"; $failed = $true }
        Write-Host ""
        if (-not (Install-BinaryNinja)) { Write-Warn "Binary Ninja installation failed"; $failed = $true }
    }
}

Write-Host ""
if ($failed) {
    Write-Warn "Installation completed with errors. Check the output above."
}
else {
    Write-Ok "Spectra installation complete!"
}
Write-Host "  Install location: $InstallDir" -ForegroundColor DarkGray
Write-Host "  To update later:  cd $InstallDir; git pull" -ForegroundColor DarkGray
Write-Host ""

# Install skills to ~/.claude/skills
Setup-Skills
Write-Host ""

# Setup CLI dependencies (Qt bindings)
Setup-CLIDependencies
Write-Host ""

# Install CLI wrapper
Setup-CLIWrapper

# Windows ARM64 notice
if ($isARM64) {
    Write-Host "====================================" -ForegroundColor Yellow
    Write-Host "Windows ARM64 detected!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "IDA Pro runs as x64 on ARM64 Windows." -ForegroundColor Cyan
    Write-Host "If you experience import errors, run:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  cd $InstallDir" -ForegroundColor White
    Write-Host "  .\install_windows_arm64_fix.bat" -ForegroundColor White
    Write-Host ""
    Write-Host "See WINDOWS_ARM64_FIX.md for details." -ForegroundColor DarkGray
    Write-Host "====================================" -ForegroundColor Yellow
    Write-Host ""
}

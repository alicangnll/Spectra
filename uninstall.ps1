# ──────────────────────────────────────────────────────────────────────
# Spectra — uninstaller (Windows)
#
#   irm https://raw.githubusercontent.com/alicangnll/Spectra/main/uninstall.ps1 | iex
#
# Or with arguments:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/uninstall.ps1))) -All
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/uninstall.ps1))) -Ida
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alicangnll/Spectra/main/uninstall.ps1))) -Binja
#
# ──────────────────────────────────────────────────────────────────────

param(
    [switch]$All,
    [switch]$Ida,
    [switch]$Binja,
    [switch]$KeepDeps,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$InstallDir = if ($env:SPECTRA_DIR) { $env:SPECTRA_DIR } else { Join-Path $HOME ".spectra" }

# ── Helpers ──────────────────────────────────────────────────────────
function Write-Info    { param($Msg) Write-Host "[*] $Msg" -ForegroundColor Cyan }
function Write-Ok      { param($Msg) Write-Host "[+] $Msg" -ForegroundColor Green }
function Write-Warn    { param($Msg) Write-Host "[!] $Msg" -ForegroundColor Yellow }
function Write-Err     { param($Msg) Write-Host "[-] $Msg" -ForegroundColor Red }

function Show-Banner {
    Write-Host ""
    Write-Host "    +========================================+" -ForegroundColor White
    Write-Host "    |            六眼  Spectra             |" -ForegroundColor White
    Write-Host "    |         Uninstall Script             |" -ForegroundColor White
    Write-Host "    +========================================+" -ForegroundColor White
    Write-Host ""
}

# ── Helper functions ─────────────────────────────────────────────────────

function Remove-Link {
    param($Target)

    if (Test-Path $Target -PathType Leaf) {
        # Check if it's a symlink or just a file
        $item = Get-Item $Target
        if ($item.LinkType -eq "SymbolicLink" -or $item.LinkType -eq "HardLink") {
            Remove-Item $Target -Force
            Write-Ok "Removed symlink: $Target"
            return $true
        }
        else {
            Write-Warn "Skipping non-symlink: $Target (use -Force to remove)"
            if ($Force) {
                Remove-Item $Target -Force -Recurse
                Write-Ok "Removed: $Target"
                return $true
            }
        }
    }
    elseif (Test-Path $Target -PathType Container) {
        Remove-Item $Target -Force -Recurse
        Write-Ok "Removed directory: $Target"
        return $true
    }
    else {
        Write-Info "Already removed: $Target"
        return $false
    }
    return $false
}

# ─── IDA Pro uninstallation ───────────────────────────────────────────────

function Uninstall-IDA {
    Write-Info "Uninstalling Spectra from IDA Pro..."
    Write-Host ""

    $idaDirs = @()
    $found = $false

    # Detect IDA user directories
    $idaUserDir = Join-Path $env:APPDATA "Hex-Rays\IDA Pro"
    if (Test-Path $idaUserDir) {
        $idaDirs += $idaUserDir
        $found = $true
    }

    $idapro = Join-Path $HOME ".idapro"
    if (Test-Path $idapro) {
        $idaDirs += $idapro
        $found = $true
    }

    if (-not $found) {
        Write-Warn "No IDA Pro installation found"
        Write-Host ""
        return
    }

    foreach ($idaDir in $idaDirs) {
        Write-Info "Processing IDA directory: $idaDir"

        # Remove plugin symlinks
        Remove-Link (Join-Path $idaDir "plugins\spectra_plugin.py")
        Remove-Link (Join-Path $idaDir "plugins\spectra")

        # Remove config directory
        Remove-Link (Join-Path $idaDir "spectra")

        # Remove old "iris" symlinks if they exist
        Remove-Link (Join-Path $idaDir "plugins\iris_plugin.py")
        Remove-Link (Join-Path $idaDir "plugins\iris")

        Write-Host ""
    }

    Write-Ok "IDA Pro uninstallation complete"
    Write-Host ""
}

# ─── Binary Ninja uninstallation ───────────────────────────────────────────

function Uninstall-BinaryNinja {
    Write-Info "Uninstalling Spectra from Binary Ninja..."
    Write-Host ""

    $bnDirs = @()
    $found = $false

    # Detect Binary Ninja user directories
    $bnDir = Join-Path $env:APPDATA "Binary Ninja"
    if (Test-Path $bnDir) {
        $bnDirs += $bnDir
        $found = $true
    }

    $bnUserDir = Join-Path $HOME ".binaryninja"
    if (Test-Path $bnUserDir) {
        $bnDirs += $bnUserDir
        $found = $true
    }

    if (-not $found) {
        Write-Warn "No Binary Ninja installation found"
        Write-Host ""
        return
    }

    foreach ($dir in $bnDirs) {
        Write-Info "Processing Binary Ninja directory: $dir"

        # Remove plugin symlink
        Remove-Link (Join-Path $dir "plugins\spectra")

        # Remove config directory
        Remove-Link (Join-Path $dir "spectra")

        # Remove old "iris" symlink if it exists
        Remove-Link (Join-Path $dir "plugins\iris")

        Write-Host ""
    }

    Write-Ok "Binary Ninja uninstallation complete"
    Write-Host ""
}

# ─── Remove CLI wrapper ────────────────────────────────────────────────────

function Uninstall-CLIWrapper {
    Write-Info "Removing CLI wrapper..."
    Write-Host ""

    $removed = $false

    # Check common bin directories
    $binDirs = @(
        (Join-Path $env:USERPROFILE "bin"),
        (Join-Path $InstallDir "bin"),
        "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    )

    foreach ($binDir in $binDirs) {
        if (Test-Path $binDir) {
            $spectraBat = Join-Path $binDir "spectra.bat"
            $spectraPs1 = Join-Path $binDir "spectra.ps1"

            if (Remove-Link $spectraBat) { $removed = $true }
            if (Remove-Link $spectraPs1) { $removed = $true }
        }
    }

    if (-not $removed) {
        Write-Info "No CLI wrapper files found"
    }
    Write-Host ""
}

# ─── Remove repository directory (optional) ─────────────────────────────────

function Uninstall-Repo {
    if (Test-Path $InstallDir) {
        if ($Force) {
            Remove-Item $InstallDir -Force -Recurse
            Write-Ok "Removed repository: $InstallDir"
        }
        else {
            Write-Warn "Repository directory exists: $InstallDir"
            Write-Info "This directory contains the Spectra source code."
            Write-Info "You may want to keep it for future use or manual inspection."
            Write-Host ""
            $response = Read-Host "Remove repository directory? [y/N]"
            if ($response -eq "y" -or $response -eq "Y") {
                Remove-Item $InstallDir -Force -Recurse
                Write-Ok "Removed repository: $InstallDir"
            }
            else {
                Write-Info "Keeping repository directory"
            }
        }
    }
    else {
        Write-Info "Repository directory not found: $InstallDir"
    }
    Write-Host ""
}

# ─── Remove Python dependencies (optional) ─────────────────────────────────

function Uninstall-Dependencies {
    if ($KeepDeps) {
        Write-Info "Skipping Python dependency removal (-KeepDeps specified)"
        Write-Host ""
        return
    }

    Write-Info "Python dependencies were installed via pip."
    Write-Info "To remove them, run the following command manually:"
    Write-Host ""
    Write-Host "  pip uninstall -y anthropic httpx pydantic" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "Note: This may affect other tools that use these packages."
    Write-Host ""
}

# ─── Main uninstallation flow ─────────────────────────────────────────────

Show-Banner

# Determine uninstall targets
$uninstallIda = $false
$uninstallBinja = $false

if ($All) {
    $uninstallIda = $true
    $uninstallBinja = $true
}
elseif ($Ida) {
    $uninstallIda = $true
}
elseif ($Binja) {
    $uninstallBinja = $true
}
else {
    # Default: uninstall from both if detected
    $uninstallIda = $true
    $uninstallBinja = $true
}

# Show what will be uninstalled
Write-Info "Uninstall targets:"
if ($uninstallIda) { Write-Host "  - IDA Pro" -ForegroundColor White }
if ($uninstallBinja) { Write-Host "  - Binary Ninja" -ForegroundColor White }
Write-Host "  - CLI wrapper" -ForegroundColor White
Write-Host ""

# Confirm before proceeding
if (-not $Force) {
    Write-Warn "This will remove Spectra from the selected targets."
    Write-Warn "Configuration and user data will be permanently deleted."
    Write-Host ""
    $response = Read-Host "Continue with uninstallation? [y/N]"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Info "Uninstallation cancelled"
        exit 0
    }
    Write-Host ""
}

# Run uninstallations
if ($uninstallIda) {
    Uninstall-IDA
}

if ($uninstallBinja) {
    Uninstall-BinaryNinja
}

# Remove CLI wrapper
Uninstall-CLIWrapper

# Ask about repository directory
Uninstall-Repo

# Show dependency removal instructions
Uninstall-Dependencies

# Final summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "      Uninstallation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Info "Thank you for using Spectra!"
Write-Info "If you have any feedback, please visit:"
Write-Host "  https://github.com/alicangnll/Spectra/issues" -ForegroundColor Cyan
Write-Host ""

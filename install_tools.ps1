################################################################################
# Spectra Tool Installation Script for Windows
#
# This script installs all required tools for Spectra security research platform
# Platform: Windows 10/11 with PowerShell 5.1+
#
# Tools covered:
# - Dynamic Instrumentation: Frida, DynamoRIO
# - Network Analysis: Wireshark, Scapy, mitmproxy, Burp Suite
# - Debugging: GDB (MinGW), WinDbg
# - Fuzzing: AFL++, LibFuzzer, Honggfuzz
# - Reverse Engineering: Radare2
# - Symbolic Execution: Angr
#
# Usage: .\install_tools.ps1 [options]
#   -All        Install all tools (default)
#   -Minimal    Install minimal set (GDB, Radare2, Scapy)
#   -Check      Check if tools are installed
#   -Help       Show help message
#
# Note: Run PowerShell as Administrator for best results
################################################################################

param(
    [switch]$All = $false,
    [switch]$Minimal = $false,
    [switch]$Check = $false,
    [switch]$Help = $false
)

################################################################################
# Utility Functions
################################################################################

function Write-Header {
    param([string]$Message)
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

function Test-Command {
    param([string]$Command)
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-PythonPackage {
    param([string]$Package)
    try {
        $null = python -c "import $Package" 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Invoke-DownloadFile {
    param(
        [string]$Url,
        [string]$Output
    )
    Write-Info "Downloading: $Url"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Output -UseBasicParsing
        Write-Success "Downloaded: $Output"
        return $true
    } catch {
        Write-Error "Failed to download: $Url"
        return $false
    }
}

################################################################################
# Package Manager Installation
################################################################################

function Install-PackageManager {
    Write-Header "Installing Package Managers"

    # Check for Chocolatey
    if (Test-Command "choco") {
        Write-Success "Chocolatey already installed"
    } else {
        Write-Info "Installing Chocolatey..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    }

    # Check for Scoop (optional, user-focused)
    if (-not (Test-Command "scoop")) {
        Write-Info "Scoop not installed. Install manually for user-scoped packages:"
        Write-Info "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
        Write-Info "Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression"
    }

    # Check for Winget (Windows 11, Windows 10 with updates)
    if (Test-Command "winget") {
        Write-Success "Winget available"
    } else {
        Write-Warning "Winget not available (Windows 10/11 feature)"
    }

    Write-Success "Package managers ready"
}

################################################################################
# Frida Installation
################################################################################

function Install-Frida {
    Write-Header "Installing Frida"

    if (Test-Command "frida") {
        Write-Success "Frida already installed"
        frida --version
        return
    }

    Write-Info "Installing Frida via pip..."
    python -m pip install frida frida-tools

    if (Test-Command "frida") {
        Write-Success "Frida installed successfully"
    } else {
        Write-Error "Frida installation failed"
    }
}

################################################################################
# DynamoRIO Installation
################################################################################

function Install-DynamoRIO {
    Write-Header "Installing DynamoRIO"

    if (Test-Command "drrun") {
        Write-Success "DynamoRIO already installed"
        return
    }

    Write-Info "DynamoRIO requires manual installation on Windows"
    Write-Info "Download from: https://github.com/DynamoRIO/dynamorio/releases"
    Write-Info "Or use: choco install dynamorio"

    if (Test-Command "choco") {
        Write-Info "Attempting installation via Chocolatey..."
        choco install dynamorio -y
    }

    if (Test-Command "drrun") {
        Write-Success "DynamoRIO installed successfully"
    } else {
        Write-Warning "DynamoRIO requires manual installation"
    }
}

################################################################################
# Wireshark Installation
################################################################################

function Install-Wireshark {
    Write-Header "Installing Wireshark"

    if (Test-Command "wireshark") {
        Write-Success "Wireshark already installed"
        return
    }

    Write-Info "Installing Wireshark..."

    if (Test-Command "choco") {
        choco install wireshark -y
    } elseif (Test-Command "winget") {
        winget install WiresharkFoundation.Wireshark
    } else {
        Write-Error "No package manager available. Install Wireshark manually:"
        Write-Info "Download from: https://www.wireshark.org/download.html"
        return
    }

    # Note: Wireshark requires Npcap for packet capture
    Write-Warning "Wireshark requires Npcap for packet capture"
    Write-Info "Download Npcap from: https://npcap.com/"
}

################################################################################
# Scapy Installation
################################################################################

function Install-Scapy {
    Write-Header "Installing Scapy"

    if (Test-PythonPackage "scapy") {
        Write-Success "Scapy already installed"
        return
    }

    Write-Info "Installing Scapy..."
    python -m pip install scapy

    # Install Npcap for Scapy (if not already installed)
    Write-Info "Scapy requires Npcap for raw socket access"
    Write-Info "Download: https://npcap.com/"

    if (Test-PythonPackage "scapy") {
        Write-Success "Scapy installed successfully"
    } else {
        Write-Error "Scapy installation failed"
    }
}

################################################################################
# mitmproxy Installation
################################################################################

function Install-Mitmproxy {
    Write-Header "Installing mitmproxy"

    if (Test-Command "mitmproxy") {
        Write-Success "mitmproxy already installed"
        return
    }

    Write-Info "Installing mitmproxy..."

    if (Test-Command "choco") {
        choco install mitmproxy -y
    } elif (Test-Command "winget") {
        Write-Info "Winget package for mitmproxy may not be available"
    }

    if (Test-Command "mitmproxy") {
        Write-Success "mitmproxy installed successfully"
    } else {
        Write-Warning "mitmproxy may require manual installation"
        Write-Info "Download from: https://mitmproxy.org/"
    }
}

################################################################################
# Burp Suite Installation
################################################################################

function Install-Burp {
    Write-Header "Installing Burp Suite"

    if (Test-Command "burpsuite") {
        Write-Success "Burp Suite already installed"
        return
    }

    Write-Info "Burp Suite requires manual installation"
    Write-Info "Download from: https://portswigger.net/burp/releases"
    Write-Info "Community edition is free"

    if (Test-Command "winget") {
        Write-Info "Attempting installation via Winget..."
        winget install PortSwigger.BurpSuite -e
    }

    Write-Info "Burp Suite Free edition available for download"
}

################################################################################
# GDB Installation (MinGW)
################################################################################

function Install-GDB {
    Write-Header "Installing GDB"

    if (Test-Command "gdb") {
        Write-Success "GDB already installed"
        gdb --version | Select-Object -First 1
        return
    }

    Write-Info "Installing MinGW-w64 GDB..."

    if (Test-Command "choco") {
        choco install mingw -y
    } else {
        Write-Info "Download MinGW-w64 from: https://www.mingw-w64.org/"
    }

    if (Test-Command "gdb") {
        Write-Success "GDB installed successfully"
    } else {
        Write-Warning "GDB installation may have failed"
    }
}

################################################################################
# WinDbg Installation
################################################################################

function Install-WinDbg {
    Write-Header "Installing WinDbg"

    if (Test-Command "windbg") {
        Write-Success "WinDbg already installed"
        return
    }

    Write-Info "WinDbg Preview is available via Microsoft Store"
    Write-Info "Or install Windows SDK for WinDbg classic"

    if (Test-Command "winget") {
        Write-Info "Attempting installation via Winget..."
        winget install Microsoft.WinDbg -e
    }

    Write-Info "WinDbg Preview: Microsoft Store or winget"
    Write-Info "Classic WinDbg: Windows SDK installation"
}

################################################################################
# Valgrind Installation
################################################################################

function Install-Valgrind {
    Write-Header "Valgrind on Windows"

    Write-Warning "Valgrind is NOT available on Windows"
    Write-Info "Alternatives:"
    Write-Info "  - Dr. Memory (Windows memory debugger): https://drmemory.org/"
    Write-Info "  - Application Verifier (Windows built-in)"
    Write-Info "  - WinDbg with !heap extension"

    if (Test-Command "choco") {
        Write-Info "Installing Dr. Memory as alternative..."
        choco install drmemory -y
    }
}

################################################################################
# Radare2 Installation
################################################################################

function Install-Radare2 {
    Write-Header "Installing Radare2"

    if (Test-Command "r2") {
        Write-Success "Radare2 already installed"
        return
    }

    Write-Info "Installing Radare2..."

    if (Test-Command "choco") {
        choco install radare2 -y
    } else {
        Write-Info "Download Radare2 for Windows:"
        Write-Info "https://github.com/radareorg/radare2/releases"
        Write-Info "Or use: pip install r2pipe (Python bindings)"
    }

    if (Test-Command "r2") {
        Write-Success "Radare2 installed successfully"
    } else {
        Write-Warning "Radare2 may require manual installation"
    }
}

################################################################################
# AFL++ Installation
################################################################################

function Install-AFL {
    Write-Header "Installing AFL++"

    if (Test-Command "afl-fuzz") {
        Write-Success "AFL++ already installed"
        return
    }

    Write-Warning "AFL++ on Windows is experimental"
    Write-Info "Alternatives:"
    Write-Info "  - WinAFL (Windows fork of AFL): https://github.com/googleprojectzero/winafl"
    Write-Info "  - Harness for AFL++ on Windows via WSL"

    if (Test-Command "choco") {
        Write-Info "AFL++ is not available via Chocolatey"
    }

    Write-Info "Install WinAFL manually or use WSL for AFL++"
}

################################################################################
# LibFuzzer Installation
################################################################################

function Install-LibFuzzer {
    Write-Header "LibFuzzer on Windows"

    Write-Info "LibFuzzer is included with LLVM/Clang"

    if (Test-Command "clang++") {
        Write-Success "Clang already installed (includes LibFuzzer)"
        clang++ --version | Select-Object -First 1
        return
    }

    Write-Info "Clang with LibFuzzer available via:"
    Write-Info "  - Visual Studio installer (C++ Clang tools)"
    Write-Info "  - LLVM installer: https://llvm.org/"

    if (Test-Command "winget") {
        Write-Info "Attempting installation via Winget..."
        winget install LLVM.LLVM -e
    }
}

################################################################################
# Honggfuzz Installation
################################################################################

function Install-Honggfuzz {
    Write-Header "Installing Honggfuzz"

    if (Test-Command "honggfuzz") {
        Write-Success "Honggfuzz already installed"
        return
    }

    Write-Warning "Honggfuzz on Windows requires manual compilation"
    Write-Info "Download from: https://github.com/google/honggfuzz"
    Write-Info "Requires MSYS2 or MinGW for compilation"

    Write-Info "Alternative: Use WinAFL for Windows fuzzing"
}

################################################################################
# Angr Installation
################################################################################

function Install-Angr {
    Write-Header "Installing Angr"

    if (Test-PythonPackage "angr") {
        Write-Success "Angr already installed"
        return
    }

    Write-Info "Installing Angr (may take several minutes)..."

    python -m pip install --upgrade pip
    python -m pip install angr

    if (Test-PythonPackage "angr") {
        Write-Success "Angr installed successfully"
    } else {
        Write-Error "Angr installation failed"
        Write-Info "Angr requires: Visual C++ Build Tools"
    }
}

################################################################################
# Additional Tools
################################################################################

function Install-AdditionalTools {
    Write-Header "Installing Additional Tools"

    if (Test-Command "choco") {
        Write-Info "Installing common security tools via Chocolatey..."
        $tools = @(
            "7zip",
            "procexp",
            "sysinternals",
            "putty",
            "vim",
            "git",
            "python"
        )

        foreach ($tool in $tools) {
            Write-Info "Installing $tool..."
            choco install $tool -y
        }
    }

    Write-Success "Additional tools installed"
}

function Install-PythonPackages {
    Write-Header "Installing Python Security Packages"

    python -m pip install --upgrade pip

    $packages = @(
        "pwntools",
        "ropgadget",
        "capstone",
        "keystone-engine",
        "unicorn",
        "requests",
        "beautifulsoup4",
        "pyyaml",
        "pygments"
    )

    foreach ($pkg in $packages) {
        Write-Info "Installing $pkg..."
        python -m pip install $pkg
    }

    Write-Success "Python packages installed successfully"
}

################################################################################
# Check Installation
################################################################################

function Test-Installation {
    Write-Header "Checking Installed Tools"

    $tools = @(
        @{Cmd="frida"; Name="Frida"},
        @{Cmd="drrun"; Name="DynamoRIO"},
        @{Cmd="wireshark"; Name="Wireshark"},
        @{Cmd="tshark"; Name="tshark"},
        @{Cmd="mitmproxy"; Name="mitmproxy"},
        @{Cmd="mitmdump"; Name="mitmdump"},
        @{Cmd="gdb"; Name="GDB"},
        @{Cmd="windbg"; Name="WinDbg"},
        @{Cmd="r2"; Name="Radare2"},
        @{Cmd="radare2"; Name="Radare2"},
        @{Cmd="drmemory"; Name="Dr. Memory"},
        @{Cmd="clang++"; Name="Clang"}
    )

    $installed = 0
    $total = $tools.Count

    foreach ($tool in $tools) {
        if (Test-Command $tool.Cmd) {
            Write-Success "$($tool.Name)"
            $installed++
        } else {
            Write-Warning "$($tool.Name) (not found)"
        }
    }

    Write-Host ""
    Write-Info "Installed: $installed/$total tools"

    # Check Python packages
    Write-Host ""
    Write-Info "Checking Python packages..."

    $pyPackages = @("scapy", "angr", "pwntools", "capstone")
    $pyInstalled = 0

    foreach ($pkg in $pyPackages) {
        if (Test-PythonPackage $pkg) {
            Write-Success "Python: $pkg"
            $pyInstalled++
        } else {
            Write-Warning "Python: $pkg (not found)"
        }
    }

    Write-Info "Python packages: $pyInstalled/$($pyPackages.Count)"
}

################################################################################
# Installation Functions
################################################################################

function Install-All {
    Write-Header "Spectra Tool Installation (Windows)"

    # Check for Python
    if (-not (Test-Command "python")) {
        Write-Warning "Python not found. Installing..."
        if (Test-Command "choco") {
            choco install python -y
        } else {
            Write-Error "Python required for most tools. Install from python.org"
            return
        }
    }

    Install-PackageManager
    Write-Host ""

    # Install all tools
    Install-Frida
    Install-DynamoRIO
    Install-Wireshark
    Install-Scapy
    Install-Mitmproxy
    Install-Burp
    Install-GDB
    Install-WinDbg
    Install-Valgrind
    Install-Radare2
    Install-AFL
    Install-LibFuzzer
    Install-Honggfuzz
    Install-Angr
    Install-AdditionalTools
    Install-PythonPackages

    Write-Host ""
    Write-Header "Installation Complete"

    # Show installation summary
    Test-Installation

    Write-Host ""
    Write-Info "Windows-specific notes:"
    Write-Info "- Npcap required for Wireshark and Scapy packet capture"
    Write-Info "- Some tools may need WSL (Windows Subsystem for Linux)"
    Write-Info "- WinAFL available as AFL alternative"
    Write-Info "- Dr. Memory available as Valgrind alternative"
}

function Install-Minimal {
    Write-Header "Spectra Minimal Tool Installation (Windows)"

    if (-not (Test-Command "python")) {
        Write-Error "Python required. Install from python.org or via choco"
        return
    }

    Install-GDB
    Install-Radare2
    Install-Scapy
    Install-PythonPackages

    Write-Host ""
    Write-Header "Minimal Installation Complete"
}

function Show-Help {
    Write-Host @"
Spectra Tool Installation Script (Windows)

Usage: .\install_tools.ps1 [options]

Options:
  -All        Install all tools (default)
  -Minimal    Install minimal set (GDB, Radare2, Scapy, Python packages)
  -Check      Check if tools are installed
  -Help       Show this help message

Supported Tools:
  - Dynamic Instrumentation: Frida, DynamoRIO
  - Network Analysis: Wireshark, Scapy, mitmproxy, Burp Suite
  - Debugging: GDB (MinGW), WinDbg
  - Fuzzing: WinAFL (AFL++ alternative), LibFuzzer, Honggfuzz
  - Reverse Engineering: Radare2
  - Symbolic Execution: Angr

Windows Notes:
  - Run PowerShell as Administrator for best results
  - Npcap required for packet capture (Wireshark, Scapy)
  - Some tools require WSL (Windows Subsystem for Linux)
  - WinAFL available as AFL++ alternative
  - Dr. Memory available as Valgrind alternative

Examples:
  .\install_tools.ps1 -All       # Install all tools
  .\install_tools.ps1 -Minimal  # Install minimal set
  .\install_tools.ps1 -Check    # Check installation status

"@
}

################################################################################
# Script Entry Point
################################################################################

# Check if help requested
if ($Help) {
    Show-Help
    exit 0
}

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Not running as Administrator. Some installations may fail."
    Write-Info "Right-click PowerShell and select 'Run as Administrator'"
}

# Execute requested action
if ($Check) {
    Test-Installation
} elseif ($Minimal) {
    Install-Minimal
} elseif ($All) {
    Install-All
} else {
    # Default to full installation
    Install-All
}

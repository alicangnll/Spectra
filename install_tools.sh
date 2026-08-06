#!/bin/bash

################################################################################
# Spectra Tool Installation Script
#
# This script installs all required tools for Spectra security research platform
# Supports: Linux (apt/yum/pacman), macOS (Homebrew)
#
# Tools covered:
# - Dynamic Instrumentation: Frida, DynamoRIO
# - Network Analysis: Wireshark, Scapy, mitmproxy, Burp
# - Debugging: GDB, Valgrind (WinDbg - Windows only)
# - Fuzzing: AFL++, LibFuzzer, Honggfuzz
# - Reverse Engineering: Radare2
# - Symbolic Execution: Angr
#
# Usage: ./install_tools.sh [options]
#   --all       Install all tools (default)
#   --minimal   Install minimal set (GDB, Radare2, Scapy)
#   --check     Check if tools are installed
#   --help      Show this help message
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Utility Functions
################################################################################

print_header() {
    echo -e "${BLUE}=====================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=====================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            echo "debian"
        elif [ -f /etc/redhat-release ]; then
            echo "redhat"
        elif [ -f /etc/arch-release ]; then
            echo "arch"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

################################################################################
# Installation Functions
################################################################################

install_package_manager() {
    OS=$(detect_os)

    case "$OS" in
        "debian")
            if ! check_command "apt-get"; then
                print_error "apt-get not found. Please run as root or with sudo."
                exit 1
            fi
            sudo apt-get update
            ;;
        "redhat")
            if ! check_command "yum"; then
                print_error "yum not found. Please run as root or with sudo."
                exit 1
            fi
            sudo yum update -y
            ;;
        "arch")
            if ! check_command "pacman"; then
                print_error "pacman not found. Please run as root or with sudo."
                exit 1
            fi
            sudo pacman -Sy
            ;;
        "macos")
            if ! check_command "brew"; then
                print_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            else
                print_success "Homebrew already installed"
                brew update
            fi
            ;;
        *)
            print_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
}

################################################################################
# Frida Installation
################################################################################

install_frida() {
    print_header "Installing Frida"

    if check_command "frida"; then
        print_success "Frida already installed"
        frida --version
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian"|"redhat"|"arch")
            pip install frida frida-tools
            ;;
        "macos")
            brew install frida
            ;;
    esac

    print_success "Frida installed successfully"
}

################################################################################
# DynamoRIO Installation
################################################################################

install_dynamorio() {
    print_header "Installing DynamoRIO"

    if check_command "drrun" || check_command "drcov"; then
        print_success "DynamoRIO already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y dynamorio
            ;;
        "macos")
            print_info "DynamoRIO requires manual installation on macOS"
            print_info "Download from: https://github.com/DynamoRIO/dynamorio/releases"
            print_info "Or use: brew install dynamorio (if available)"
            return
            ;;
        *)
            print_info "DynamoRIO requires manual installation"
            print_info "Download from: https://github.com/DynamoRIO/dynamorio/releases"
            ;;
    esac

    print_success "DynamoRIO installed successfully"
}

################################################################################
# Wireshark Installation
################################################################################

install_wireshark() {
    print_header "Installing Wireshark"

    if check_command "wireshark" || check_command "tshark"; then
        print_success "Wireshark already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y wireshark tshark
            # Add user to wireshark group for non-root capture
            print_info "To capture without sudo: sudo usermod -aG wireshark $USER"
            ;;
        "redhat")
            sudo yum install -y wireshark
            ;;
        "arch")
            sudo pacman -S wireshark-cli wireshark-qt
            ;;
        "macos")
            brew install --cask wireshark
            ;;
    esac

    print_success "Wireshark installed successfully"
}

################################################################################
# Scapy Installation
################################################################################

install_scapy() {
    print_header "Installing Scapy"

    if python3 -c "import scapy" 2>/dev/null; then
        print_success "Scapy already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y python3-scapy
            ;;
        "redhat")
            sudo yum install -y python3-scapy
            ;;
        "arch")
            sudo pacman -S python-scapy
            ;;
        "macos")
            pip3 install scapy
            ;;
    esac

    print_success "Scapy installed successfully"
}

################################################################################
# mitmproxy Installation
################################################################################

install_mitmproxy() {
    print_header "Installing mitmproxy"

    if check_command "mitmproxy" || check_command "mitmdump"; then
        print_success "mitmproxy already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y mitmproxy
            ;;
        "redhat")
            sudo yum install -y mitmproxy
            ;;
        "arch")
            sudo pacman -S mitmproxy
            ;;
        "macos")
            brew install mitmproxy
            ;;
    esac

    print_success "mitmproxy installed successfully"
}

################################################################################
# Burp Suite Installation
################################################################################

install_burp() {
    print_header "Installing Burp Suite"

    if check_command "burpsuite" || check_command "burp"; then
        print_success "Burp Suite already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            print_info "Burp Suite requires manual installation"
            print_info "Download from: https://portswigger.net/burp/releases"
            print_info "Or use: sudo snap install burpsuite (if snap is available)"
            ;;
        "redhat")
            print_info "Burp Suite requires manual installation"
            print_info "Download from: https://portswigger.net/burp/releases"
            ;;
        "arch")
            print_info "Check AUR for burpsuite community packages"
            ;;
        "macos")
            print_info "Burp Suite requires manual installation"
            print_info "Download from: https://portswigger.net/burp/releases"
            ;;
    esac

    print_info "Burp Suite Free edition is available for download"
}

################################################################################
# GDB Installation
################################################################################

install_gdb() {
    print_header "Installing GDB"

    if check_command "gdb"; then
        print_success "GDB already installed"
        gdb --version | head -1
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y gdb
            ;;
        "redhat")
            sudo yum install -y gdb
            ;;
        "arch")
            sudo pacman -S gdb
            ;;
        "macos")
            brew install gdb
            print_warning "GDB on macOS requires code signing"
            print_info "See: https://sourceware.org/gdb/wiki/BuildingOnDarwin"
            ;;
    esac

    print_success "GDB installed successfully"
}

################################################################################
# Valgrind Installation
################################################################################

install_valgrind() {
    print_header "Installing Valgrind"

    if check_command "valgrind"; then
        print_success "Valgrind already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y valgrind
            ;;
        "redhat")
            sudo yum install -y valgrind
            ;;
        "arch")
            sudo pacman -S valgrind
            ;;
        "macos")
            brew install valgrind
            ;;
    esac

    print_success "Valgrind installed successfully"
}

################################################################################
# Radare2 Installation
################################################################################

install_radare2() {
    print_header "Installing Radare2"

    if check_command "r2" || check_command "radare2"; then
        print_success "Radare2 already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian"|"redhat"|"arch")
            print_info "Installing Radare2 from official script..."
            git clone https://github.com/radareorg/radare2.git || true
            if [ -d "radare2" ]; then
                cd radare2
                sys/install.sh
                cd ..
                rm -rf radare2
            else
                sudo apt-get install -y radare2 || sudo yum install -y radare2
            fi
            ;;
        "macos")
            brew install radare2
            ;;
    esac

    print_success "Radare2 installed successfully"
}

################################################################################
# AFL++ Installation
################################################################################

install_afl() {
    print_header "Installing AFL++"

    if check_command "afl-fuzz" || check_command "afl-gcc"; then
        print_success "AFL++ already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y afl++
            ;;
        "redhat")
            sudo yum install -y afl++
            ;;
        "arch")
            sudo pacman -S afl++
            ;;
        "macos")
            brew install afl-plus-plus
            ;;
    esac

    print_success "AFL++ installed successfully"
}

################################################################################
# LibFuzzer Installation
################################################################################

install_libfuzzer() {
    print_header "Installing LibFuzzer"

    # LibFuzzer is typically part of LLVM/Clang
    print_info "LibFuzzer is included with LLVM/Clang"

    if check_command "clang++"; then
        print_success "Clang already installed (includes LibFuzzer)"
        clang++ --version | head -1
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y clang
            ;;
        "redhat")
            sudo yum install -y clang
            ;;
        "arch")
            sudo pacman -S clang
            ;;
        "macos")
            print_success "Clang is available via Xcode Command Line Tools"
            ;;
    esac

    print_success "LibFuzzer (via Clang) installed successfully"
}

################################################################################
# Honggfuzz Installation
################################################################################

install_honggfuzz() {
    print_header "Installing Honggfuzz"

    if check_command "honggfuzz"; then
        print_success "Honggfuzz already installed"
        return
    fi

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y honggfuzz
            ;;
        "redhat")
            sudo yum install -y honggfuzz || true
            if ! check_command "honggfuzz"; then
                print_info "Building Honggfuzz from source..."
                git clone https://github.com/google/honggfuzz.git || true
                if [ -d "honggfuzz" ]; then
                    cd honggfuzz
                    make
                    sudo make install
                    cd ..
                    rm -rf honggfuzz
                fi
            fi
            ;;
        "arch")
            sudo pacman -S honggfuzz
            ;;
        "macos")
            brew install honggfuzz
            ;;
    esac

    print_success "Honggfuzz installed successfully"
}

################################################################################
# Angr Installation
################################################################################

install_angr() {
    print_header "Installing Angr"

    if python3 -c "import angr" 2>/dev/null; then
        print_success "Angr already installed"
        return
    fi

    # Angr requires specific Python version and dependencies
    print_info "Installing Angr (may take several minutes)..."

    OS=$(detect_os)

    case "$OS" in
        "debian")
            sudo apt-get install -y python3-dev python3-pip python3-venv build-essential
            ;;
        "redhat")
            sudo yum install -y python3-devel python3-pip gcc
            ;;
        "arch")
            sudo pacman -S python python-pip gcc
            ;;
        "macos")
            brew install python@3.11
            ;;
    esac

    # Install via pip
    pip3 install --upgrade pip
    pip3 install angr

    print_success "Angr installed successfully"
}

################################################################################
# Additional Tools
################################################################################

install_additional_tools() {
    print_header "Installing Additional Security Tools"

    OS=$(detect_os)

    case "$OS" in
        "debian")
            print_info "Installing additional tools..."
            sudo apt-get install -y \
                binutils \
                strace \
                ltrace \
                objdump \
                hexdump \
                bsdmainutils \
                curl \
                wget \
                git \
                python3-pip \
                python3-venv
            ;;
        "redhat")
            sudo yum install -y \
                binutils \
                strace \
                ltrace \
                objdump \
                curl \
                wget \
                git \
                python3-pip
            ;;
        "arch")
            sudo pacman -S --needed \
                binutils \
                strace \
                ltrace \
                curl \
                wget \
                git \
                python-pip
            ;;
        "macos")
            print_info "Installing additional tools..."
            brew install \
                binutils \
                curl \
                wget \
                git
            ;;
    esac

    print_success "Additional tools installed successfully"
}

install_python_packages() {
    print_header "Installing Python Security Packages"

    pip3 install --upgrade pip

    # Common security packages
    pip3 install \
        pwntools \
        ropgadget \
        capstone \
        keystone-engine \
        unicorn \
        requests \
        beautifulsoup4 \
        pyyaml

    print_success "Python packages installed successfully"
}

################################################################################
# Check Installation
################################################################################

check_installation() {
    print_header "Checking Installed Tools"

    local tools=(
        "frida:Frida"
        "drrun:DynamoRIO"
        "wireshark:Wireshark"
        "tshark:tshark"
        "mitmproxy:mitmproxy"
        "gdb:GDB"
        "valgrind:Valgrind"
        "r2:Radare2"
        "radare2:Radare2"
        "afl-fuzz:AFL++"
        "afl-gcc:AFL++"
        "honggfuzz:Honggfuzz"
        "clang++:LibFuzzer"
    )

    local installed=0
    local total=${#tools[@]}

    for tool in "${tools[@]}"; do
        local cmd="${tool%%:*}"
        local name="${tool##*:}"

        if check_command "$cmd"; then
            print_success "$name"
            ((installed++))
        else
            print_warning "$name (not found)"
        fi
    done

    echo ""
    print_info "Installed: $installed/$total tools"

    # Check Python packages
    echo ""
    print_info "Checking Python packages..."

    local py_packages=("scapy" "angr" "pwntools" "capstone")
    local py_installed=0

    for pkg in "${py_packages[@]}"; do
        if python3 -c "import $pkg" 2>/dev/null; then
            print_success "Python: $pkg"
            ((py_installed++))
        else
            print_warning "Python: $pkg (not found)"
        fi
    done

    print_info "Python packages: $py_installed/${#py_packages[@]}"
}

################################################################################
# Main Installation Flow
################################################################################

install_all() {
    print_header "Spectra Tool Installation"

    OS=$(detect_os)
    print_info "Detected OS: $OS"
    echo ""

    # Install package manager dependencies
    install_package_manager
    echo ""

    # Install all tools
    install_frida
    install_dynamorio
    install_wireshark
    install_scapy
    install_mitmproxy
    install_burp
    install_gdb
    install_valgrind
    install_radare2
    install_afl
    install_libfuzzer
    install_honggfuzz
    install_angr
    install_additional_tools
    install_python_packages

    echo ""
    print_header "Installation Complete"

    # Show installation summary
    check_installation

    echo ""
    print_info "Some tools may require additional configuration:"
    print_info "- Wireshark: Add user to 'wireshark' group for non-root capture"
    print_info "- GDB (macOS): Configure code signing"
    print_info "- Burp Suite: Download and install manually"
    print_info "- DynamoRIO: May require manual installation on some platforms"
}

install_minimal() {
    print_header "Spectra Minimal Tool Installation"

    install_gdb
    install_radare2
    install_scapy
    install_python_packages

    echo ""
    print_header "Minimal Installation Complete"
}

################################################################################
# Script Entry Point
################################################################################

show_help() {
    cat << EOF
Spectra Tool Installation Script

Usage: $0 [options]

Options:
  --all       Install all tools (default)
  --minimal   Install minimal set (GDB, Radare2, Scapy, Python packages)
  --check     Check if tools are installed
  --help      Show this help message

Supported Tools:
  - Dynamic Instrumentation: Frida, DynamoRIO
  - Network Analysis: Wireshark, Scapy, mitmproxy, Burp Suite
  - Debugging: GDB, Valgrind
  - Fuzzing: AFL++, LibFuzzer, Honggfuzz
  - Reverse Engineering: Radare2
  - Symbolic Execution: Angr

Examples:
  $0 --all       # Install all tools
  $0 --minimal   # Install minimal set
  $0 --check     # Check installation status

EOF
}

main() {
    case "${1:-all}" in
        --all)
            install_all
            ;;
        --minimal)
            install_minimal
            ;;
        --check)
            check_installation
            ;;
        --help|-h)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"

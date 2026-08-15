#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Spectra — universal installer (Linux / macOS)
#
#   curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash -s -- --ida
#   curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash -s -- --binja
#   curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash -s -- --both
#
# Environment variables:
#   SPECTRA_DIR     — where to clone the repo   (default: ~/.spectra)
#   RIKUGAN_BRANCH  — git branch to check out   (default: main)
#   IDADIR          — override IDA install dir  (forwarded to install_ida.sh)
#   IDA_PYTHON      — override Python for IDA    (forwarded to install_ida.sh)
#   BN_PYTHON       — override Python for BN     (forwarded to install_binaryninja.sh)
#
# IDA Python auto-configuration:
#   The IDA installer automatically runs `idapyswitch --auto-apply` to
#   configure IDA's Python before installing dependencies.  No manual
#   steps are required.
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/alicangnll/Spectra.git"
INSTALL_DIR="${SPECTRA_DIR:-$HOME/.spectra}"
BRANCH="${RIKUGAN_BRANCH:-main}"

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

info()   { printf "${CYAN}[*]${NC} %s\n" "$*"; }
ok()     { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn()   { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()    { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

banner() {
    printf "\n${BOLD}"
    cat << 'EOF'
    ╔══════════════════════════════════════════╗
    ║            六眼  Spectra                 ║
    ║     Reverse Engineering AI Agent         ║
    ║        IDA Pro  ·  Binary Ninja          ║
    ╚══════════════════════════════════════════╝
EOF
    printf "${NC}\n"
}

# ── Parse arguments ──────────────────────────────────────────────────
TARGET=""
for arg in "$@"; do
    case "$arg" in
        --ida)       TARGET="ida"   ;;
        --binja|--bn) TARGET="binja" ;;
        --both)      TARGET="both"  ;;
        --help|-h)
            echo "Usage: curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash -s -- [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ida       Install for IDA Pro only"
            echo "  --binja     Install for Binary Ninja only"
            echo "  --both      Install for both hosts"
            echo "  (no flag)   Auto-detect installed hosts"
            echo ""
            echo "Environment:"
            echo "  SPECTRA_DIR=$INSTALL_DIR"
            echo "  RIKUGAN_BRANCH=$BRANCH"
            exit 0
            ;;
    esac
done

# ── Host detection ───────────────────────────────────────────────────

# _DETECTED_IDA_DIR is set by detect_ida() when it finds an install dir,
# so that run_ida_installer() can forward it without re-scanning.
_DETECTED_IDA_DIR=""

detect_ida() {
    if [[ "$(uname)" == "Darwin" ]]; then
        [[ -d "$HOME/.idapro" ]] && return 0
        [[ -d "$HOME/Library/Application Support/Hex-Rays/IDA Pro" ]] && return 0
        ls /Applications/IDA*.app &>/dev/null && return 0
        ls "$HOME/Applications/IDA"*.app &>/dev/null 2>&1 && return 0
    else
        # ~/.idapro or ~/.ida user directory
        [[ -d "$HOME/.idapro" ]] && return 0
        [[ -d "$HOME/.ida"    ]] && return 0

        # Standard system-wide locations
        for d in /opt/ida* /opt/idapro* /usr/local/ida* /usr/local/idapro*; do
            [[ -d "$d" ]] && { _DETECTED_IDA_DIR="$d"; return 0; }
        done

        # Home-directory installs (common on Kali: ~/ida-pro-9.1, ~/idapro, ~/ida, etc.)
        for d in "$HOME"/ida-pro* "$HOME"/ida-* "$HOME"/idapro* "$HOME"/ida; do
            if [[ -d "$d" && -x "$d/ida64" ]]; then
                _DETECTED_IDA_DIR="$d"
                return 0
            fi
        done
    fi

    # idapyswitch or ida64 on PATH
    if command -v idapyswitch &>/dev/null; then
        _DETECTED_IDA_DIR="$(dirname "$(command -v idapyswitch)")"
        return 0
    fi
    command -v ida64  &>/dev/null && return 0
    command -v idat64 &>/dev/null && return 0
    return 1
}

detect_binja() {
    # Check for Binary Ninja APPLICATION first, not just user directories
    if [[ "$(uname)" == "Darwin" ]]; then
        [[ -d "/Applications/Binary Ninja.app" ]] && return 0
        [[ -d "$HOME/Applications/Binary Ninja.app" ]] && return 0
    else
        [[ -d "$HOME/.binaryninja" ]] && return 0
        [[ -d "/opt/binaryninja" ]] && return 0
        [[ -d "/usr/local/binaryninja" ]] && return 0
        [[ -d "$HOME/binaryninja" ]] && return 0
    fi
    return 1
}

# ── Prerequisites ────────────────────────────────────────────────────
check_prereqs() {
    if ! command -v git &>/dev/null; then
        err "git is required but not installed."
        if [[ "$(uname)" == "Darwin" ]]; then
            err "Install with: xcode-select --install"
        else
            err "Install with your package manager (apt install git / dnf install git)"
        fi
        exit 1
    fi

    if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
        warn "Python not found in PATH — the per-host installer will attempt to find the bundled Python."
    fi
}

# ── Clone or update ──────────────────────────────────────────────────
clone_or_update() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing installation at $INSTALL_DIR..."
        git -C "$INSTALL_DIR" fetch origin "$BRANCH" --quiet
        git -C "$INSTALL_DIR" checkout "$BRANCH" --quiet 2>/dev/null || true
        git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" --quiet
        ok "Updated to latest $BRANCH"
    else
        if [[ -d "$INSTALL_DIR" ]]; then
            warn "$INSTALL_DIR exists but is not a git repo — backing up"
            mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
        fi
        info "Cloning Spectra into $INSTALL_DIR..."
        git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR" --quiet
        ok "Cloned successfully"
    fi

    # Clear Python cache to ensure fresh module loading
    clear_python_cache
}

# ── Clear Python cache ──────────────────────────────────────────────────
clear_python_cache() {
    info "Clearing Python cache..."
    local cache_count=0

    # Clear __pycache__ directories in Spectra installation
    if [[ -d "$INSTALL_DIR" ]]; then
        while IFS= read -r -d '' cache_dir; do
            rm -rf "$cache_dir" 2>/dev/null && ((cache_count++))
        done < <(find "$INSTALL_DIR" -type d -name "__pycache__" -print0 2>/dev/null)

        # Clear .pyc files
        while IFS= read -r -d '' pyc_file; do
            rm -f "$pyc_file" 2>/dev/null && ((cache_count++))
        done < <(find "$INSTALL_DIR" -type f -name "*.pyc" -print0 2>/dev/null)
    fi

    # Clear IDA plugin cache if present
    local ida_cache_dir="$HOME/.idapro/plugins/__pycache__"
    if [[ -d "$ida_cache_dir" ]]; then
        rm -rf "${ida_cache_dir}/spectra"* 2>/dev/null && ((cache_count++))
    fi

    # Clear Binary Ninja plugin cache if present
    local bn_cache_dir="$HOME/.binaryninja/plugins/__pycache__"
    if [[ -d "$bn_cache_dir" ]]; then
        rm -rf "${bn_cache_dir}/spectra"* 2>/dev/null && ((cache_count++))
    fi

    if [[ $cache_count -gt 0 ]]; then
        ok "Cleared $cache_count Python cache entries"
    else
        info "No Python cache to clear"
    fi
}

# ── Run installers ───────────────────────────────────────────────────
run_ida_installer() {
    local script="$INSTALL_DIR/install_ida.sh"
    if [[ ! -f "$script" ]]; then
        err "install_ida.sh not found in $INSTALL_DIR"
        return 1
    fi
    info "Running IDA Pro installer..."
    echo ""
    chmod +x "$script"
    # Forward the detected IDA install dir so install_ida.sh doesn't re-scan.
    # IDADIR env var is already honoured by install_ida.sh's find_ida_install_dir().
    if [[ -n "${_DETECTED_IDA_DIR:-}" && -z "${IDADIR:-}" ]]; then
        IDADIR="$_DETECTED_IDA_DIR" bash "$script"
    else
        bash "$script"
    fi
}

run_binja_installer() {
    local script="$INSTALL_DIR/install_binaryninja.sh"
    if [[ ! -f "$script" ]]; then
        err "install_binaryninja.sh not found in $INSTALL_DIR"
        return 1
    fi
    info "Running Binary Ninja installer..."
    echo ""
    chmod +x "$script"
    bash "$script"
}

# ── Main ─────────────────────────────────────────────────────────────
main() {
    banner
    check_prereqs

    # Auto-detect if no target specified
    if [[ -z "$TARGET" ]]; then
        local has_ida=false has_binja=false
        detect_ida   && has_ida=true
        detect_binja && has_binja=true

        if $has_ida && $has_binja; then
            TARGET="both"
            ok "Detected both IDA Pro and Binary Ninja"
        elif $has_ida; then
            TARGET="ida"
            ok "Detected IDA Pro"
        elif $has_binja; then
            TARGET="binja"
            ok "Detected Binary Ninja"
        else
            warn "No IDA Pro or Binary Ninja installation detected."
            warn "Installing anyway — use --ida or --binja to specify the target."
            warn "Defaulting to both."
            TARGET="both"
        fi
    fi

    info "Target: ${TARGET}"
    info "Install directory: ${INSTALL_DIR}"
    echo ""

    clone_or_update
    echo ""

    local failed=false

    case "$TARGET" in
        ida)
            run_ida_installer || failed=true
            ;;
        binja)
            run_binja_installer || failed=true
            ;;
        both)
            run_ida_installer || { warn "IDA installation failed"; failed=true; }
            echo ""
            run_binja_installer || { warn "Binary Ninja installation failed"; failed=true; }
            ;;
    esac

    echo ""
    if $failed; then
        warn "Installation completed with errors. Check the output above."
    else
        ok "Spectra installation complete!"
    fi
    printf "${DIM}  Install location: ${INSTALL_DIR}${NC}\n"
    printf "${DIM}  To update later:  cd ${INSTALL_DIR} && git pull${NC}\n"
    echo ""

    # Install skills to ~/.claude/skills
    setup_skills
    echo ""

    # Setup CLI dependencies (Qt bindings)
    setup_cli_dependencies
    echo ""

    # Install CLI wrapper
    setup_cli_wrapper
}

# ── Skills installation ────────────────────────────────────────────────────
setup_skills() {
    local skills_dir="$HOME/.claude/skills"
    local claude_ext_source="$INSTALL_DIR/claude_ext"

    # Ensure ~/.claude/skills exists
    if [[ ! -d "$skills_dir" ]]; then
        mkdir -p "$skills_dir" 2>/dev/null || {
            warn "Could not create $skills_dir - skipping skills installation"
            return 1
        }
    fi

    # Copy claude_ext to ~/.claude/skills if it exists
    if [[ -d "$claude_ext_source" ]]; then
        local target_dir="$skills_dir/claude_ext"
        info "Copying claude_ext to ~/.claude/skills..."

        # Remove existing directory if present
        [[ -d "$target_dir" ]] && rm -rf "$target_dir"

        # Copy directory
        cp -R "$claude_ext_source" "$target_dir"
        ok "Skills installed: $target_dir"
    else
        warn "claude_ext not found in $INSTALL_DIR - skipping skills installation"
    fi
}

# ── CLI dependencies setup ────────────────────────────────────────────────────
setup_cli_dependencies() {
    info "Setting up CLI dependencies..."

    # On macOS, ensure PyQt5 is installed and remove conflicting PySide6
    # On other platforms, ensure PySide6 is installed
    if [[ "$(uname)" == "Darwin" ]]; then
        info "macOS detected: ensuring PyQt5 is installed"

        # Check if PySide6 is installed and remove it to avoid conflicts
        local pyside6_installed=false
        if pip3 list 2>/dev/null | grep -q "PySide6"; then
            pyside6_installed=true
            warn "PySide6 found - removing to avoid Qt5/Qt6 conflicts on macOS"
            pip3 uninstall -y --break-system-packages PySide6 PySide6_Addons PySide6_Essentials 2>/dev/null || \
            pip3 uninstall -y PySide6 PySide6_Addons PySide6_Essentials 2>/dev/null || true
            ok "PySide6 removed"
        fi

        # Ensure PyQt5 is installed
        if ! pip3 show PyQt5 >/dev/null 2>&1; then
            info "Installing PyQt5..."
            if pip3 install --break-system-packages PyQt5 >/dev/null 2>&1; then
                ok "PyQt5 installed successfully"
            elif pip3 install --user PyQt5 >/dev/null 2>&1; then
                ok "PyQt5 installed successfully (user)"
            else
                warn "Failed to install PyQt5 - CLI may not work properly"
            fi
        else
            ok "PyQt5 already installed"
        fi
    else
        info "Non-macOS platform: ensuring PySide6 is installed"

        # Ensure PySide6 is installed on Linux/Windows
        if ! pip3 show PySide6 >/dev/null 2>&1; then
            info "Installing PySide6..."
            if pip3 install --break-system-packages PySide6 >/dev/null 2>&1; then
                ok "PySide6 installed successfully"
            elif pip3 install --user PySide6 >/dev/null 2>&1; then
                ok "PySide6 installed successfully (user)"
            else
                warn "Failed to install PySide6 - CLI may not work properly"
            fi
        else
            ok "PySide6 already installed"
        fi
    fi
}

# ── CLI wrapper setup ────────────────────────────────────────────────────
setup_cli_wrapper() {
    # Ensure CLI wrapper script exists in repository root
    local repo_wrapper="$INSTALL_DIR/spectra-cli"
    cat << 'EOF' > "$repo_wrapper"
#!/usr/bin/env bash
# Spectra CLI wrapper - launches interactive Spectra CLI shell
# Usage: spectra [target_directory]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${1:-.}"

python3 "$SCRIPT_DIR/spectra_cli.py" dir_loc "$WORK_DIR"
EOF
    chmod +x "$repo_wrapper"

    # Determine install location for the wrapper script
    local bin_dir="$HOME/.local/bin"
    if [[ ! -d "$bin_dir" ]]; then
        mkdir -p "$bin_dir" 2>/dev/null || bin_dir="$INSTALL_DIR/bin"
        mkdir -p "$bin_dir" 2>/dev/null || bin_dir="$INSTALL_DIR"
    fi

    local target_cmd="$bin_dir/spectra"
    local old_link="$bin_dir/spectra-cli"

    # Remove old symlinks/files if present
    [[ -e "$old_link" ]] && rm -f "$old_link"
    [[ -e "$target_cmd" ]] && rm -f "$target_cmd"

    # Write a direct, robust launcher script to bin_dir
    cat << EOF > "$target_cmd"
#!/usr/bin/env bash
# Spectra CLI launcher
WORK_DIR="\${1:-.}"
python3 "$INSTALL_DIR/spectra_cli.py" dir_loc "\$WORK_DIR"
EOF
    chmod +x "$target_cmd"
    ok "CLI wrapper installed: $target_cmd"

    # Check if bin_dir is in PATH
    if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
        echo ""
        warn "⚠️  $bin_dir is not in your PATH"
        warn "Add this to your ~/.bashrc or ~/.zshrc:"
        warn "  export PATH=\"\$PATH:$bin_dir\""
        warn "Then restart your terminal or run: export PATH=\"\$PATH:$bin_dir\""
    else
        ok "✓ $bin_dir is already in your PATH"
    fi

    echo ""
    info "Usage:"
    echo "  spectra          # Start Spectra in current directory"
    echo "  spectra /path    # Start Spectra in specified directory"
    echo ""
}

main

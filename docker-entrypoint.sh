#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Spectra Docker Entrypoint
#
# This script handles initialization and runs the Spectra CLI
# ──────────────────────────────────────────────────────────────────────

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Logging
info()   { printf "${CYAN}[*]${NC} %s\n" "$*"; }
ok()     { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn()   { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()    { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

# Show banner
banner() {
    printf "\n${BOLD}${CYAN}"
    cat << 'EOF'
    ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
   █  ██╗    ██╗███████╗██████╗ ███╗   ███╗ ██████╗ ███████╗ █
   █  ██║    ██║██╔════╝██╔══██╗████╗ ████║██╔═══██╗██╔════╝ █
   █  ██║    ██║███████╗██████╔╝██╔████╔██║██║   ██║███████╗ █
   █  ██║    ██║╚════██║██╔══██╗██║╚██╔╝██║██║   ██║╚════██║ █
   █  ███████╗███████║██████╔╝██║ ╚═╝ ██║╚██████╔╝███████║ █
   █  ╚══════╝╚══════╝╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚══════╝ █
    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

  ████████╗██╗  ██╗███████╗██╗     ██╗███╗   ██╗ ██████╗ ███████╗
  ██╔════╝██║  ██║██╔════╝██║     ██║████╗  ██║██╔═══██╗██╔════╝
  █████╗  ███████║███████╗██║     ██║██╔██╗ ██║██║   ██║███████╗
  ██╔══╝  ██╔══██║╚════██║██║     ██║██║╚██╗██║██║   ██║╚════██║
  ██║    ██║  ██║███████║███████╗██║██║ ╚████║╚██████╔╝███████║
  ╚═╝    ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝
EOF
    printf "${NC}\n"
    printf "╔══════════════════════════════════════════════════════════════╗\n"
    printf "║  ${BOLD}Spectra CLI - AI-Powered Security Analysis${NC}        ║\n"
    printf "║  ${CYAN}Docker Environment${NC}                                   ║\n"
    printf "╚══════════════════════════════════════════════════════════════╝\n\n"
}

# Initialize directories
init_dirs() {
    info "Initializing data directories..."
    mkdir -p /spectra/data/{sessions,skills,logs}
    chmod -R 755 /spectra/data
    ok "Directories initialized"
}

# Check for API key
check_config() {
    if [[ ! -f "/spectra/data/config.json" ]]; then
        warn "No configuration found. You'll need to set your API key."
        warn "Use: /apikey <your-key> inside Spectra CLI"
    fi
}

# Show help
show_help() {
    cat << 'EOF'
Spectra Docker Usage

Basic usage:
  docker run -it spectra                    # Start CLI
  docker run -it spectra dir_loc /path      # Analyze directory
  docker run -it spectra file_loc /path     # Analyze file

With volume mounts:
  docker run -it \
    -v spectra-data:/spectra/data \
    -v /path/to/targets:/targets:ro \
    spectra dir_loc /targets

Environment variables:
  SPECTRA_PROVIDER      - LLM provider (anthropic, openai, gemini)
  SPECTRA_MODEL        - Model name
  SPECTRA_API_KEY      - API key for provider
  SPECTRA_API_URL      - Custom API URL

Examples:
  # Start with Anthropic
  docker run -it \
    -e SPECTRA_API_KEY="sk-ant-xxx" \
    spectra

  # Analyze a directory
  docker run -it \
    -v /path/to/linux:/target:ro \
    spectra dir_loc /target

  # Use custom API
  docker run -it \
    -e SPECTRA_API_URL="http://localhost:11434/v1" \
    -e SPECTRA_PROVIDER="ollama" \
    spectra

For more commands, run Spectra CLI and type /help
EOF
}

# Main execution
main() {
    banner

    # Show help if requested
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        show_help
        exit 0
    fi

    # Initialize
    init_dirs
    check_config

    # Check if we have arguments
    if [[ $# -eq 0 ]]; then
        info "Starting Spectra CLI..."
        echo ""
    fi

    # Run Spectra CLI
    exec python3 /spectra/spectra_cli.py "$@"
}

# Run main
main "$@"

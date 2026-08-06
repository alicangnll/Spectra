#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Spectra Docker Build Script
#
# Usage: ./docker-build.sh [tag]
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()   { printf "${CYAN}[*]${NC} %s\n" "$*"; }
ok()     { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn()   { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()    { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

# Default tag
TAG="${1:-spectra:latest}"

# Banner
printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════╗${NC}\n"
printf "${BOLD}${CYAN}║${NC}  ${BOLD}Spectra Docker Build Script${NC}                     "
printf "${BOLD}${CYAN}║${NC}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════╝${NC}\n\n"

# Check Docker
info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    err "Docker is not installed!"
    exit 1
fi
ok "Docker found: $(docker --version | head -1)"

# Check Dockerfile
info "Checking Dockerfile..."
if [[ ! -f "Dockerfile" ]]; then
    err "Dockerfile not found in current directory!"
    exit 1
fi
ok "Dockerfile found"

# Build options
info "Building Docker image: ${TAG}"
info "Build options:"
echo "  Tag:           ${TAG}"
echo "  Context:       $(pwd)"
echo "  Dockerfile:    $(pwd)/Dockerfile"
echo ""

# Build
info "Starting build..."
if docker build -t "${TAG}" -f Dockerfile .; then
    echo ""
    ok "Build completed successfully!"
    echo ""
    info "Image details:"
    docker images "${TAG}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    echo ""
    info "To run the container:"
    echo "  docker run -it ${TAG}"
    echo ""
    info "Or use docker-compose:"
    echo "  docker-compose up -d"
    echo ""
else
    err "Build failed!"
    exit 1
fi

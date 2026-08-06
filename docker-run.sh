#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Spectra Docker Run Script
#
# Usage: ./docker-run.sh [options] [spectra_args...]
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

# Default values
IMAGE="${SPECTRA_IMAGE:-spectra:latest}"
CONTAINER_NAME="${SPECTRA_CONTAINER:-spectra-cli}"
DATA_VOLUME="${SPECTRA_DATA_VOLUME:-spectra-data}"
TARGET_DIR="${TARGET_DIR:-./targets}"

# Parse options
MOUNT_TARGET=""
VOLUMES="-v ${DATA_VOLUME}:/spectra/data"
ENV_VARS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image)
            IMAGE="$2"
            shift 2
            ;;
        --name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --target)
            MOUNT_TARGET="$2"
            shift 2
            ;;
        --env)
            ENV_VARS="${ENV_VARS} -e $2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./docker-run.sh [options] [spectra_args...]"
            echo ""
            echo "Options:"
            echo "  --image <name>       Docker image to use (default: spectra:latest)"
            echo "  --name <name>        Container name (default: spectra-cli)"
            echo "  --target <path>      Mount target directory"
            echo "  --env KEY=VAL        Set environment variable"
            echo "  --help, -h           Show this help"
            echo ""
            echo "Examples:"
            echo "  ./docker-run.sh                                      # Start CLI"
            echo "  ./docker-run.sh dir_loc /target                      # Analyze target"
            echo "  ./docker-run.sh --target /path/to/linux dir_loc /target"
            echo "  ./docker-run.sh --env SPECTRA_API_KEY=xxx"
            echo ""
            exit 0
            ;;
        *)
            # Remaining args are for Spectra
            break
            ;;
    esac
done

# Banner
printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════╗${NC}\n"
printf "${BOLD}${CYAN}║${NC}  ${BOLD}Spectra Docker Run${NC}                                 "
printf "${BOLD}${CYAN}║${NC}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════╝${NC}\n\n"

# Check Docker
info "Checking Docker..."
if ! command -v docker &> /dev/null; then
    err "Docker is not installed!"
    exit 1
fi

# Check image
info "Checking image: ${IMAGE}"
if ! docker image inspect "${IMAGE}" &> /dev/null; then
    warn "Image not found. Building..."
    ./docker-build.sh "${IMAGE}" || exit 1
fi

# Add target mount if specified
if [[ -n "${MOUNT_TARGET}" ]]; then
    if [[ ! -d "${MOUNT_TARGET}" ]]; then
        err "Target directory not found: ${MOUNT_TARGET}"
        exit 1
    fi
    VOLUMES="${VOLUMES} -v ${MOUNT_TARGET}:/target:ro"
    info "Mounting target: ${MOUNT_TARGET} -> /target"
fi

# Build docker command
info "Starting container..."
echo ""
info "Configuration:"
echo "  Image:         ${IMAGE}"
echo "  Container:     ${CONTAINER_NAME}"
echo "  Volumes:       ${VOLUMES}"
echo "  Environment:   ${ENV_VARS:-none}"
echo ""

# Run
docker run -it --rm \
    --name "${CONTAINER_NAME}" \
    ${VOLUMES} \
    ${ENV_VARS} \
    -e PYTHONUNBUFFERED=1 \
    "${IMAGE}" \
    "$@"

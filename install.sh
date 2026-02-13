#!/bin/bash
# Token Guardian Installation Script
# Installs the unified Token Guardian CLI and configuration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.tokenguardian"
SYSTEM_CONFIG_DIR="/etc/tokenguardian"
BINARY_PATH="/usr/local/bin/tokenguardian"

echo "╔════════════════════════════════════════════════════╗"
echo "║         TOKEN GUARDIAN INSTALLER                  ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Check Python
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not installed"
    exit 1
fi

PY_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PY_MAJOR=$(echo $PY_VERSION | cut -d'.' -f1)
PY_MINOR=$(echo $PY_VERSION | cut -d'.' -f2)

if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; then
    echo "ERROR: Python 3.8+ required, found $PY_VERSION"
    exit 1
fi

log_info "Python $PY_VERSION OK"

# Install CLI
log_info "Installing CLI to $BINARY_PATH..."
if [ -f "$BINARY_PATH" ]; then
    log_warn "Existing installation found, backing up..."
    cp "$BINARY_PATH" "${BINARY_PATH}.backup"
fi

cp "${SCRIPT_DIR}/tokenguardian.py" "$BINARY_PATH"
chmod +x "$BINARY_PATH"
log_info "CLI installed"

# Create config directories
log_info "Creating configuration directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/cache"
mkdir -p "$CONFIG_DIR/audit"
mkdir -p /var/log/tokenguardian 2>/dev/null || log_warn "Could not create /var/log/tokenguardian (may need sudo)"
mkdir -p /var/run 2>/dev/null || log_warn "Could not create /var/run (may need sudo)"

# Copy default configs
log_info "Installing configuration files..."
if [ -d "${SCRIPT_DIR}/config" ]; then
    for config_file in "${SCRIPT_DIR}/config"/*.yaml; do
        if [ -f "$config_file" ]; then
            filename=$(basename "$config_file")
            if [ ! -f "${CONFIG_DIR}/${filename}" ]; then
                cp "$config_file" "${CONFIG_DIR}/${filename}"
                log_info "  Installed: $filename"
            else
                log_warn "  Skipped (exists): $filename"
            fi
        fi
    done
fi

# Create __init__.py files
log_info "Setting up Python package..."
touch "${SCRIPT_DIR}/src/__init__.py"
touch "${SCRIPT_DIR}/src/core/__init__.py"
touch "${SCRIPT_DIR}/src/daemon/__init__.py"

# Verify installation
log_info "Verifying installation..."
if command -v tokenguardian &> /dev/null; then
    log_info "CLI verification: OK"
    tokenguardian doctor
else
    echo "ERROR: CLI not found in PATH"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║         INSTALLATION COMPLETE                     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Quick Start:"
echo "  tokenguardian status        # Check status"
echo "  tokenguardian doctor        # Validate config"
echo "  tokenguardian dry-run       # Test routing"
echo "  tokenguardian start         # Start daemon (shadow mode)"
echo ""
echo "Configuration:"
echo "  User:   $CONFIG_DIR"
echo "  System: $SYSTEM_CONFIG_DIR (if you have sudo)"
echo ""

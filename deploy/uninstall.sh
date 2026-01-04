#!/bin/bash
# ===========================================
# TradingView MCP Server Uninstallation Script
# ===========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== TradingView MCP Server Uninstallation ===${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

# Stop and disable service
echo "Stopping service..."
systemctl stop tradingview-mcp 2>/dev/null || true
systemctl disable tradingview-mcp 2>/dev/null || true

# Remove systemd service
echo "Removing systemd service..."
rm -f /etc/systemd/system/tradingview-mcp.service
systemctl daemon-reload

# Remove installation directory
echo "Removing installation directory..."
rm -rf /opt/tradingview-mcp

# Ask about config files
read -p "Remove configuration files in /etc/tradingview-mcp? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf /etc/tradingview-mcp
    echo "Configuration files removed."
else
    echo "Configuration files preserved."
fi

# Ask about removing user
read -p "Remove tradingview user? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    userdel tradingview 2>/dev/null || true
    rm -rf /var/lib/tradingview
    echo "User removed."
fi

echo -e "${GREEN}Uninstallation complete.${NC}"

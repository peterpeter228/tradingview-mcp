#!/bin/bash
# ===========================================
# TradingView MCP Server Installation Script
# ===========================================
# 
# This script installs the TradingView MCP server with:
# - Python virtual environment
# - Playwright with Chromium
# - supergateway for stdio→SSE conversion
# - systemd service for auto-restart
#
# SSE service runs on port 8053

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== TradingView MCP Server Installation ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

# Configuration
INSTALL_DIR="/opt/tradingview-mcp"
CONFIG_DIR="/etc/tradingview-mcp"
SERVICE_USER="tradingview"
PYTHON_VERSION="python3"

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/8] Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv nodejs npm

# Step 2: Install supergateway globally
echo -e "${YELLOW}[2/8] Installing supergateway...${NC}"
npm install -g supergateway

# Step 3: Create service user
echo -e "${YELLOW}[3/8] Creating service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -m -d /var/lib/tradingview "$SERVICE_USER"
fi

# Step 4: Create installation directory
echo -e "${YELLOW}[4/8] Setting up installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Copy source files
cp -r src "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"

# Step 5: Create Python virtual environment
echo -e "${YELLOW}[5/8] Creating Python virtual environment...${NC}"
cd "$INSTALL_DIR"
$PYTHON_VERSION -m venv venv
source venv/bin/activate

# Step 6: Install Python dependencies
echo -e "${YELLOW}[6/8] Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Step 7: Install Playwright and Chromium
echo -e "${YELLOW}[7/8] Installing Playwright browsers...${NC}"
playwright install chromium
playwright install-deps chromium

# Step 8: Setup configuration files
echo -e "${YELLOW}[8/8] Setting up configuration...${NC}"

# Create config files if they don't exist
if [ ! -f "$CONFIG_DIR/env" ]; then
    cp deploy/env.example "$CONFIG_DIR/env"
    echo -e "${YELLOW}Created $CONFIG_DIR/env - please edit with your API keys${NC}"
fi

if [ ! -f "$CONFIG_DIR/accounts.yaml" ]; then
    cp accounts.yaml.example "$CONFIG_DIR/accounts.yaml"
    echo -e "${YELLOW}Created $CONFIG_DIR/accounts.yaml - please edit with your TradingView accounts${NC}"
fi

# Set permissions
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"
chmod 600 "$CONFIG_DIR/env"
chmod 600 "$CONFIG_DIR/accounts.yaml"

# Install systemd service
cp deploy/tradingview-mcp.service /etc/systemd/system/
systemctl daemon-reload

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Edit configuration files:"
echo "   sudo nano $CONFIG_DIR/env"
echo "   sudo nano $CONFIG_DIR/accounts.yaml"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start tradingview-mcp"
echo ""
echo "3. Enable auto-start on boot:"
echo "   sudo systemctl enable tradingview-mcp"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status tradingview-mcp"
echo "   sudo journalctl -u tradingview-mcp -f"
echo ""
echo -e "${GREEN}SSE endpoint will be available at: http://localhost:8053${NC}"

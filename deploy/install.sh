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

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
INSTALL_DIR="/opt/tradingview-mcp"
CONFIG_DIR="/etc/tradingview-mcp"
SERVICE_USER="tradingview"

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/9] Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3-full python3-venv nodejs npm curl

# Step 2: Install supergateway globally
echo -e "${YELLOW}[2/9] Installing supergateway...${NC}"
npm install -g supergateway

# Step 3: Create service user
echo -e "${YELLOW}[3/9] Creating service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -m -d /var/lib/tradingview "$SERVICE_USER"
fi

# Step 4: Create installation directory
echo -e "${YELLOW}[4/9] Setting up installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Copy source files
cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_DIR/pyproject.toml" "$INSTALL_DIR/"

# Step 5: Create Python virtual environment
echo -e "${YELLOW}[5/9] Creating Python virtual environment...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

# Step 6: Install Python dependencies
echo -e "${YELLOW}[6/9] Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Step 7: Install Playwright and Chromium
echo -e "${YELLOW}[7/9] Installing Playwright browsers...${NC}"
playwright install chromium
playwright install-deps chromium

# Step 8: Create wrapper script and setup configuration
echo -e "${YELLOW}[8/9] Setting up configuration...${NC}"

# Create MCP start wrapper script
cat > "$INSTALL_DIR/start-mcp.sh" << 'WRAPPER_EOF'
#!/bin/bash
# Internal wrapper script for running MCP server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Run the MCP server
exec "$SCRIPT_DIR/venv/bin/python" -m tradingview_mcp.server
WRAPPER_EOF
chmod +x "$INSTALL_DIR/start-mcp.sh"

# Create config files if they don't exist
if [ ! -f "$CONFIG_DIR/env" ]; then
    cat > "$CONFIG_DIR/env" << 'ENV_EOF'
# /etc/tradingview-mcp/env
# This file is loaded by systemd EnvironmentFile directive

# LLM Configuration (CometAPI - OpenAI compatible)
LLM_API_KEY=your_comet_api_key_here
LLM_API_BASE=https://api.cometapi.com/v1
LLM_MODEL=openai/gpt-4o

# TradingView Accounts Config Path
TRADINGVIEW_ACCOUNTS_CONFIG=/etc/tradingview-mcp/accounts.yaml
ENV_EOF
    echo -e "${YELLOW}Created $CONFIG_DIR/env - please edit with your API keys${NC}"
fi

if [ ! -f "$CONFIG_DIR/accounts.yaml" ]; then
    cp "$PROJECT_DIR/accounts.yaml.example" "$CONFIG_DIR/accounts.yaml"
    echo -e "${YELLOW}Created $CONFIG_DIR/accounts.yaml - please edit with your TradingView accounts${NC}"
fi

# Set permissions
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"
chmod 600 "$CONFIG_DIR/env"
chmod 600 "$CONFIG_DIR/accounts.yaml"

# Step 9: Install systemd service
echo -e "${YELLOW}[9/9] Installing systemd service...${NC}"

# Find supergateway path
SUPERGATEWAY_PATH=$(which supergateway)

cat > /etc/systemd/system/tradingview-mcp.service << EOF
[Unit]
Description=TradingView MCP Server (stdio via supergateway to SSE on port 8053)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR

# Environment file - all keys must be here
EnvironmentFile=$CONFIG_DIR/env

# Run MCP stdio server via supergateway to expose as SSE on port 8053
ExecStart=$SUPERGATEWAY_PATH --stdio "$INSTALL_DIR/start-mcp.sh" --port 8053

# Restart policy
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR /tmp
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradingview-mcp

[Install]
WantedBy=multi-user.target
EOF

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

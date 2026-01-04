#!/bin/bash
# ===========================================
# TradingView MCP Server Quick Setup (Development)
# ===========================================
# 
# Run this script to set up the development environment

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}=== TradingView MCP Server Setup ===${NC}"
echo ""

# Step 1: Check Python
echo -e "${YELLOW}[1/6] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 not found. Please install: sudo apt install python3-full python3-venv${NC}"
    exit 1
fi
echo "Python: $(python3 --version)"

# Step 2: Create virtual environment
echo -e "${YELLOW}[2/6] Creating virtual environment...${NC}"
if [ -d "venv" ]; then
    echo "Virtual environment already exists"
else
    python3 -m venv venv
    echo "Created venv/"
fi

# Step 3: Activate and install dependencies
echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "Dependencies installed"

# Step 4: Install Playwright
echo -e "${YELLOW}[4/6] Installing Playwright Chromium...${NC}"
playwright install chromium
echo "Attempting to install system dependencies (may require sudo)..."
playwright install-deps chromium 2>/dev/null || echo -e "${YELLOW}Note: Run 'sudo playwright install-deps chromium' if browser fails to launch${NC}"

# Step 5: Check for supergateway
echo -e "${YELLOW}[5/6] Checking supergateway...${NC}"
if command -v supergateway &> /dev/null; then
    echo "supergateway: $(which supergateway)"
else
    echo -e "${YELLOW}supergateway not found. Install with: sudo npm install -g supergateway${NC}"
fi

# Step 6: Setup config files
echo -e "${YELLOW}[6/6] Setting up configuration files...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env (please edit with your LLM API key)"
else
    echo ".env already exists"
fi

if [ ! -f "accounts.yaml" ]; then
    cp accounts.yaml.example accounts.yaml
    echo "Created accounts.yaml (please edit with your TradingView accounts)"
else
    echo "accounts.yaml already exists"
fi

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit configuration:"
echo "   nano .env              # Set LLM_API_KEY"
echo "   nano accounts.yaml     # Add TradingView account cookies"
echo ""
echo "2. Install supergateway (if not installed):"
echo "   sudo npm install -g supergateway"
echo ""
echo "3. Run the server:"
echo "   ./run-sse.sh          # SSE mode on port 8053"
echo ""
echo "4. Test with curl:"
echo "   curl http://localhost:8053"
echo ""

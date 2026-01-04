#!/bin/bash
# ===========================================
# Run TradingView MCP Server in SSE mode (dev)
# ===========================================
# 
# This script runs the MCP server through supergateway
# exposing it as an SSE endpoint on port 8053
#
# Requirements:
# - Python virtual environment with dependencies
# - supergateway installed: sudo npm install -g supergateway

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  playwright install chromium"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check for supergateway
if ! command -v supergateway &> /dev/null; then
    echo "supergateway not found. Installing..."
    sudo npm install -g supergateway
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check for local accounts.yaml
if [ ! -f accounts.yaml ] && [ -z "$TRADINGVIEW_ACCOUNTS_CONFIG" ]; then
    echo "WARNING: accounts.yaml not found!"
    echo "Please copy accounts.yaml.example to accounts.yaml and configure your accounts."
    exit 1
fi

# Set config path to local if not set
if [ -z "$TRADINGVIEW_ACCOUNTS_CONFIG" ]; then
    export TRADINGVIEW_ACCOUNTS_CONFIG="$SCRIPT_DIR/accounts.yaml"
fi

echo "=== TradingView MCP Server (SSE mode) ==="
echo "Port: 8053"
echo "Config: $TRADINGVIEW_ACCOUNTS_CONFIG"
echo "Python: $(which python)"
echo ""

# Run with supergateway on port 8053
exec supergateway --stdio "$SCRIPT_DIR/venv/bin/python -m tradingview_mcp.server" --port 8053

#!/bin/bash
# ===========================================
# Run TradingView MCP Server in SSE mode (dev)
# ===========================================
# 
# This script runs the MCP server through supergateway
# exposing it as an SSE endpoint on port 8053
#
# Requirements:
# - Node.js and npm installed
# - supergateway installed: npm install -g supergateway
# - Python dependencies installed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for supergateway
if ! command -v supergateway &> /dev/null; then
    echo "supergateway not found. Installing..."
    npm install -g supergateway
fi

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check for local accounts.yaml
if [ ! -f accounts.yaml ] && [ ! -f "$TRADINGVIEW_ACCOUNTS_CONFIG" ]; then
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
echo ""

# Run with supergateway on port 8053
exec supergateway --stdio "python -m tradingview_mcp.server" --port 8053

#!/bin/bash
# ===========================================
# Run TradingView MCP Server in stdio mode (dev)
# ===========================================
# 
# This script runs the MCP server in stdio mode
# for direct integration with MCP clients

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
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

echo "=== TradingView MCP Server (stdio mode) ===" >&2
echo "Config: $TRADINGVIEW_ACCOUNTS_CONFIG" >&2

# Run in stdio mode
exec python -m tradingview_mcp.server

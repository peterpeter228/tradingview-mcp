#!/bin/bash
# Internal wrapper script for running MCP server with correct PYTHONPATH
# This script is called by supergateway

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Load environment variables if .env exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Set accounts config path if not set
if [ -z "$TRADINGVIEW_ACCOUNTS_CONFIG" ]; then
    if [ -f "$SCRIPT_DIR/accounts.yaml" ]; then
        export TRADINGVIEW_ACCOUNTS_CONFIG="$SCRIPT_DIR/accounts.yaml"
    fi
fi

# Run the MCP server
exec "$SCRIPT_DIR/venv/bin/python" -m tradingview_mcp.server

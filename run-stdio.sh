#!/bin/bash
# ===========================================
# Run TradingView MCP Server in stdio mode
# ===========================================
# 
# This script runs the MCP server in stdio mode
# for direct integration with MCP clients

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!" >&2
    echo "Please run: ./setup.sh" >&2
    exit 1
fi

# Check for accounts.yaml
if [ ! -f "accounts.yaml" ]; then
    echo "ERROR: accounts.yaml not found!" >&2
    echo "Please copy accounts.yaml.example to accounts.yaml" >&2
    exit 1
fi

echo "=== TradingView MCP Server (stdio mode) ===" >&2
echo "Config: $SCRIPT_DIR/accounts.yaml" >&2

# Run MCP server via wrapper script
exec "$SCRIPT_DIR/start-mcp.sh"

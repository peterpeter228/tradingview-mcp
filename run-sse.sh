#!/bin/bash
# ===========================================
# Run TradingView MCP Server in SSE mode
# ===========================================
# 
# This script runs the MCP server through supergateway
# exposing it as an SSE endpoint on port 8053

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run: ./setup.sh"
    exit 1
fi

# Check for supergateway
if ! command -v supergateway &> /dev/null; then
    echo "ERROR: supergateway not found!"
    echo "Please install: sudo npm install -g supergateway"
    exit 1
fi

# Check for accounts.yaml
if [ ! -f "accounts.yaml" ]; then
    echo "ERROR: accounts.yaml not found!"
    echo "Please copy accounts.yaml.example to accounts.yaml and configure your accounts."
    exit 1
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo "WARNING: .env not found, using defaults"
fi

echo "=== TradingView MCP Server (SSE mode) ==="
echo "Port: 8053"
echo "Config: $SCRIPT_DIR/accounts.yaml"
echo ""

# Run with supergateway on port 8053
exec supergateway --stdio "$SCRIPT_DIR/start-mcp.sh" --port 8053

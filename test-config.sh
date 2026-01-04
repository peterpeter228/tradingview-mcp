#!/bin/bash
# ===========================================
# Test TradingView MCP Configuration
# ===========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TradingView MCP Configuration Test ==="
echo ""

# Check virtual environment
echo "[1] Virtual Environment:"
if [ -d "venv" ]; then
    echo "    ✓ venv/ exists"
else
    echo "    ✗ venv/ not found - run ./setup.sh"
fi

# Check .env file
echo ""
echo "[2] Environment File (.env):"
if [ -f ".env" ]; then
    echo "    ✓ .env exists"
    
    # Source .env
    set -a
    source .env
    set +a
    
    # Check LLM settings
    if [ -n "$LLM_API_KEY" ]; then
        echo "    ✓ LLM_API_KEY is set (${LLM_API_KEY:0:8}...)"
    else
        echo "    ✗ LLM_API_KEY is NOT set!"
    fi
    
    echo "    - LLM_API_BASE: ${LLM_API_BASE:-https://api.cometapi.com/v1}"
    echo "    - LLM_MODEL: ${LLM_MODEL:-openai/gpt-4o}"
else
    echo "    ✗ .env not found - copy from .env.example"
fi

# Check accounts.yaml
echo ""
echo "[3] Accounts Config (accounts.yaml):"
if [ -f "accounts.yaml" ]; then
    echo "    ✓ accounts.yaml exists"
    
    # Count accounts
    ACCOUNT_COUNT=$(grep -c "^\s*- name:" accounts.yaml 2>/dev/null || echo "0")
    echo "    - Found $ACCOUNT_COUNT account(s)"
    
    # Check YAML syntax
    if command -v python3 &> /dev/null; then
        source venv/bin/activate 2>/dev/null
        python3 -c "import yaml; yaml.safe_load(open('accounts.yaml'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "    ✓ YAML syntax is valid"
        else
            echo "    ✗ YAML syntax error!"
        fi
    fi
else
    echo "    ✗ accounts.yaml not found - copy from accounts.yaml.example"
fi

# Check Playwright
echo ""
echo "[4] Playwright:"
if [ -d "venv" ]; then
    source venv/bin/activate
    if python3 -c "from playwright.async_api import async_playwright" 2>/dev/null; then
        echo "    ✓ Playwright module installed"
    else
        echo "    ✗ Playwright module not installed"
    fi
    
    # Check chromium
    CHROMIUM_PATH=$(python3 -c "from playwright._impl._driver import compute_driver_executable; print(compute_driver_executable())" 2>/dev/null)
    if [ -n "$CHROMIUM_PATH" ]; then
        echo "    ✓ Playwright driver found"
    else
        echo "    ? Cannot verify Playwright browser"
    fi
fi

# Check supergateway
echo ""
echo "[5] Supergateway:"
if command -v supergateway &> /dev/null; then
    echo "    ✓ supergateway installed: $(which supergateway)"
else
    echo "    ✗ supergateway not found - run: sudo npm install -g supergateway"
fi

# Test LLM API connection
echo ""
echo "[6] LLM API Test:"
if [ -n "$LLM_API_KEY" ]; then
    echo "    Testing connection to ${LLM_API_BASE:-https://api.cometapi.com/v1}..."
    
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $LLM_API_KEY" \
        "${LLM_API_BASE:-https://api.cometapi.com/v1}/models" 2>/dev/null)
    
    if [ "$RESPONSE" = "200" ]; then
        echo "    ✓ API connection successful (HTTP 200)"
    elif [ "$RESPONSE" = "401" ]; then
        echo "    ✗ API key invalid (HTTP 401)"
    else
        echo "    ? API response: HTTP $RESPONSE"
    fi
else
    echo "    - Skipped (LLM_API_KEY not set)"
fi

echo ""
echo "=== Test Complete ==="

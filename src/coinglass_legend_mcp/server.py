#!/usr/bin/env python3
"""
CoinGlass Legend MCP Server

Multi-account chart screenshot and LLM analysis server for legend.coinglass.com.
Uses Playwright for browser automation and CometAPI (OpenAI-compatible) for analysis.

Features:
- Multi-account support via YAML cookie configuration
- High-resolution viewport (2560x1440 default)
- Canvas-based render waiting strategy
- UI overlay hiding for clean screenshots
- Isolated error handling per account

SSE Port: 8056 (via supergateway)
"""

import os
import sys
import base64
import logging
import asyncio
import traceback
from typing import Optional, Any
from pathlib import Path

import yaml
import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configure logging to stderr for journalctl visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration Constants (can be overridden via environment variables)
# =============================================================================

# Viewport dimensions (high resolution for multi-panel charts)
VIEWPORT_W = int(os.getenv("VIEWPORT_W", "2560"))
VIEWPORT_H = int(os.getenv("VIEWPORT_H", "1440"))

# Stabilization wait time in milliseconds after canvas appears
STABILIZE_WAIT_MS = int(os.getenv("STABILIZE_WAIT_MS", "1200"))

# Whether to hide UI elements before screenshot
HIDE_UI = os.getenv("HIDE_UI", "true").lower() in ("true", "1", "yes")

# LLM Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.cometapi.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-5.2")
LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "120"))

# Accounts configuration file path
ACCOUNTS_YAML = os.getenv("ACCOUNTS_YAML", "/etc/coinglass-legend-mcp/accounts.yaml")

# Default chart URL
DEFAULT_CHART_URL = "https://legend.coinglass.com/zh/chart/88314a3573a644dabdd85431bea14b7d"

# =============================================================================
# CSS selectors for UI elements to hide (tolerant - won't fail if missing)
# =============================================================================

UI_HIDE_CSS = """
/* Hide left sidebar/toolbar */
.left-toolbar,
.sidebar,
[class*="sidebar"],
[class*="left-panel"],
[class*="tool-bar"],
[class*="toolbar"],
.tv-side-toolbar,
div[data-name="drawing-toolbar"] {
    display: none !important;
    visibility: hidden !important;
}

/* Hide top navigation/header */
header,
nav,
.header,
.navbar,
[class*="header"],
[class*="nav-bar"],
[class*="top-bar"],
.tv-header,
div[class*="Header"] {
    display: none !important;
    visibility: hidden !important;
}

/* Hide right side panels/overlays */
.right-panel,
[class*="right-panel"],
[class*="side-panel"],
.floating-panel,
[class*="floating"],
[class*="overlay"],
.modal,
[class*="modal"],
[class*="popup"],
[class*="tooltip"] {
    display: none !important;
    visibility: hidden !important;
}

/* Hide footer */
footer,
.footer,
[class*="footer"],
[class*="bottom-bar"] {
    display: none !important;
    visibility: hidden !important;
}

/* Hide any fixed/sticky elements that might overlay */
[style*="position: fixed"],
[style*="position:fixed"] {
    display: none !important;
}

/* Hide cookie banners and notifications */
[class*="cookie"],
[class*="consent"],
[class*="notification"],
[class*="toast"],
[class*="banner"],
[class*="alert"]:not([class*="price"]) {
    display: none !important;
    visibility: hidden !important;
}

/* Hide scrollbars for cleaner screenshot */
::-webkit-scrollbar {
    display: none !important;
}
* {
    scrollbar-width: none !important;
}
"""

# =============================================================================
# Global browser instance (reused for efficiency)
# =============================================================================

_playwright = None
_browser: Optional[Browser] = None


async def get_browser() -> Browser:
    """Get or create a persistent browser instance."""
    global _playwright, _browser
    
    if _browser is not None:
        return _browser
    
    # Start Playwright
    if _playwright is None:
        _playwright = await async_playwright().start()
    
    # Launch browser in headless mode with optimized flags
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
        ]
    )
    logger.info("Browser launched successfully")
    return _browser


async def cleanup():
    """Cleanup browser resources."""
    global _browser, _playwright
    
    if _browser:
        await _browser.close()
        _browser = None
    
    if _playwright:
        await _playwright.stop()
        _playwright = None
    
    logger.info("Browser resources cleaned up")


# =============================================================================
# Account Configuration Loading
# =============================================================================

def load_accounts_config(config_path: str = ACCOUNTS_YAML) -> list[dict]:
    """
    Load multi-account cookie configuration from YAML file.
    
    Expected format:
    accounts:
      - name: acc1
        cookies:
          - name: session
            value: "xxxx"
            domain: ".coinglass.com"
            path: "/"
            secure: true
            httpOnly: true
          - name: legend_token
            value: "yyyy"
            domain: "legend.coinglass.com"
            path: "/"
    
    Returns:
        List of account configurations with name and cookies.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config format is invalid.
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(
            f"账号配置文件不存在: {config_path}\n"
            f"请创建配置文件，格式参考 accounts.yaml.example"
        )
    
    if not path.is_file():
        raise ValueError(f"配置路径不是文件: {config_path}")
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析失败: {e}")
    
    if not config or 'accounts' not in config:
        raise ValueError("配置文件缺少 'accounts' 字段")
    
    accounts = config['accounts']
    if not isinstance(accounts, list) or len(accounts) == 0:
        raise ValueError("'accounts' 必须是非空列表")
    
    # Validate each account
    validated_accounts = []
    for i, acc in enumerate(accounts):
        if not isinstance(acc, dict):
            raise ValueError(f"账号 {i+1} 配置格式错误，应为字典")
        
        if 'name' not in acc:
            raise ValueError(f"账号 {i+1} 缺少 'name' 字段")
        
        if 'cookies' not in acc or not isinstance(acc['cookies'], list):
            raise ValueError(f"账号 '{acc['name']}' 缺少有效的 'cookies' 列表")
        
        # Normalize cookies for Playwright
        normalized_cookies = []
        for cookie in acc['cookies']:
            if not isinstance(cookie, dict):
                continue
            if 'name' not in cookie or 'value' not in cookie:
                continue
            
            # Build Playwright-compatible cookie
            pw_cookie = {
                'name': str(cookie['name']),
                'value': str(cookie['value']),
                'domain': str(cookie.get('domain', '.coinglass.com')),
                'path': str(cookie.get('path', '/')),
            }
            
            # Optional fields
            if 'secure' in cookie:
                pw_cookie['secure'] = bool(cookie['secure'])
            if 'httpOnly' in cookie:
                pw_cookie['httpOnly'] = bool(cookie['httpOnly'])
            if 'sameSite' in cookie:
                pw_cookie['sameSite'] = str(cookie['sameSite'])
            if 'expires' in cookie:
                pw_cookie['expires'] = float(cookie['expires'])
            
            normalized_cookies.append(pw_cookie)
        
        if not normalized_cookies:
            raise ValueError(f"账号 '{acc['name']}' 没有有效的 cookie 配置")
        
        validated_accounts.append({
            'name': acc['name'],
            'cookies': normalized_cookies
        })
    
    logger.info(f"成功加载 {len(validated_accounts)} 个账号配置")
    return validated_accounts


# =============================================================================
# Screenshot Capture
# =============================================================================

async def capture_chart_screenshot(
    context: BrowserContext,
    chart_url: str,
    hide_ui: bool = HIDE_UI,
    viewport_w: int = VIEWPORT_W,
    viewport_h: int = VIEWPORT_H,
    stabilize_wait_ms: int = STABILIZE_WAIT_MS
) -> bytes:
    """
    Capture a screenshot of the CoinGlass Legend chart.
    
    Strategy:
    1. Navigate to chart URL
    2. Wait for page to load (domcontentloaded)
    3. Wait for main container to appear
    4. Wait for at least one canvas element
    5. Apply stabilization wait for chart rendering
    6. Optionally hide UI overlays
    7. Capture screenshot of chart area (or full page fallback)
    
    Args:
        context: Playwright browser context with cookies
        chart_url: URL of the chart to capture
        hide_ui: Whether to inject CSS to hide UI elements
        viewport_w: Viewport width
        viewport_h: Viewport height
        stabilize_wait_ms: Additional wait time after canvas detection
    
    Returns:
        PNG image bytes
    
    Raises:
        Exception: If screenshot capture fails
    """
    page = await context.new_page()
    
    try:
        # Set high-resolution viewport
        await page.set_viewport_size({"width": viewport_w, "height": viewport_h})
        
        logger.info(f"Loading chart: {chart_url}")
        
        # Navigate to chart page
        await page.goto(chart_url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for main app container (multiple possible selectors)
        main_container_selectors = [
            '#app',
            '#root',
            '[id*="app"]',
            '[id*="root"]',
            'main',
            '.main-content',
            '[class*="chart"]',
            '[class*="Chart"]',
        ]
        
        container_found = False
        for selector in main_container_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                container_found = True
                logger.debug(f"Found main container: {selector}")
                break
            except:
                continue
        
        if not container_found:
            logger.warning("Main container not found, continuing anyway...")
        
        # Wait for at least one canvas element (critical for chart rendering)
        canvas_selectors = [
            'canvas',
            '[class*="canvas"]',
            'svg[class*="chart"]',
        ]
        
        canvas_found = False
        for selector in canvas_selectors:
            try:
                await page.wait_for_selector(selector, timeout=15000)
                canvas_found = True
                logger.info(f"Canvas element found: {selector}")
                break
            except:
                continue
        
        if not canvas_found:
            logger.warning("No canvas element found, attempting screenshot anyway...")
        
        # Stabilization wait for chart layers to complete rendering
        logger.info(f"Waiting {stabilize_wait_ms}ms for chart stabilization...")
        await asyncio.sleep(stabilize_wait_ms / 1000.0)
        
        # Inject CSS to hide UI overlays if enabled
        if hide_ui:
            try:
                await page.add_style_tag(content=UI_HIDE_CSS)
                logger.info("UI hiding CSS injected")
                # Brief wait for CSS to take effect
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to inject UI hiding CSS: {e}")
        
        # Try to find and screenshot the main chart container
        chart_container_selectors = [
            '[class*="chart-container"]',
            '[class*="ChartContainer"]',
            '[class*="trading-chart"]',
            '[class*="main-chart"]',
            '.chart',
            '#chart',
            'main',
        ]
        
        screenshot = None
        for selector in chart_container_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Check if element has reasonable size
                    box = await element.bounding_box()
                    if box and box['width'] > 500 and box['height'] > 300:
                        screenshot = await element.screenshot(type='png')
                        logger.info(f"Screenshot captured from container: {selector}")
                        break
            except Exception as e:
                logger.debug(f"Container {selector} not usable: {e}")
                continue
        
        # Fallback to full page screenshot
        if screenshot is None:
            logger.info("Using full page screenshot as fallback")
            screenshot = await page.screenshot(type='png', full_page=True)
        
        logger.info(f"Screenshot captured: {len(screenshot)} bytes")
        return screenshot
        
    finally:
        await page.close()


# =============================================================================
# LLM Analysis (CometAPI - OpenAI Compatible)
# =============================================================================

async def llm_analyze_png(
    png_bytes: bytes,
    prompt: str,
    api_key: str = LLM_API_KEY,
    api_base: str = LLM_API_BASE,
    model: str = LLM_MODEL,
    timeout_s: int = LLM_TIMEOUT_S
) -> str:
    """
    Analyze a chart screenshot using LLM with vision capability.
    
    Args:
        png_bytes: PNG image bytes
        prompt: Analysis prompt/question
        api_key: OpenAI-compatible API key
        api_base: API base URL (CometAPI)
        model: Model identifier
        timeout_s: Request timeout in seconds
    
    Returns:
        Analysis text from LLM
    
    Raises:
        ValueError: If API key is not configured
        httpx.TimeoutException: If request times out
        Exception: For other API errors
    """
    if not api_key:
        raise ValueError("LLM_API_KEY 环境变量未设置")
    
    # Encode image as base64 data URL for vision model
    image_base64 = base64.b64encode(png_bytes).decode('utf-8')
    image_data_url = f"data:image/png;base64,{image_base64}"
    
    # Build the messages payload for OpenAI-compatible API
    messages = [
        {
            "role": "system",
            "content": (
                "你是专业的加密货币和金融市场分析师。"
                "请分析用户提供的 CoinGlass Legend 图表截图，"
                "包括价格走势、技术指标、资金流向、持仓变化等信息。"
                "给出专业、简洁、有洞察力的分析。"
            )
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url,
                        "detail": "high"
                    }
                },
                {
                    "type": "text",
                    "text": prompt or "请分析这张 CoinGlass Legend 图表，包括主要指标、趋势和关键信号。"
                }
            ]
        }
    ]
    
    # Make API request
    api_url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7
    }
    
    logger.info(f"Calling LLM API: {model} @ {api_base}")
    
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        if 'choices' not in result or len(result['choices']) == 0:
            raise ValueError(f"LLM API 返回异常: {result}")
        
        analysis = result['choices'][0]['message']['content']
        logger.info(f"LLM analysis completed: {len(analysis)} chars")
        return analysis


# =============================================================================
# Main Analysis Function (Multi-Account)
# =============================================================================

async def analyze_chart_for_all_accounts(
    chart_url: str,
    extra_prompt: str = ""
) -> list[dict[str, str]]:
    """
    Analyze chart for all configured accounts.
    
    For each account:
    1. Create new browser context
    2. Inject account cookies
    3. Capture screenshot
    4. Call LLM for analysis
    5. Return analysis result
    
    Individual account failures don't affect other accounts.
    
    Args:
        chart_url: URL of the chart to analyze
        extra_prompt: Additional prompt for LLM analysis
    
    Returns:
        List of results: [{"account": "name", "analysis": "..."}]
    """
    # Load accounts configuration
    try:
        accounts = load_accounts_config()
    except Exception as e:
        error_msg = f"配置加载失败: {type(e).__name__}: {e}"
        logger.error(error_msg)
        traceback.print_exc(file=sys.stderr)
        return [{"account": "配置错误", "analysis": error_msg}]
    
    # Get browser instance
    try:
        browser = await get_browser()
    except Exception as e:
        error_msg = f"浏览器启动失败: {type(e).__name__}: {e}"
        logger.error(error_msg)
        traceback.print_exc(file=sys.stderr)
        return [{"account": "浏览器错误", "analysis": error_msg}]
    
    results = []
    
    for account in accounts:
        account_name = account['name']
        logger.info(f"Processing account: {account_name}")
        
        context = None
        try:
            # Create new context for this account
            context = await browser.new_context(
                viewport={'width': VIEWPORT_W, 'height': VIEWPORT_H},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            )
            
            # Add cookies for this account
            await context.add_cookies(account['cookies'])
            logger.info(f"Cookies injected for {account_name}: {len(account['cookies'])} cookies")
            
            # Capture screenshot
            png_bytes = await capture_chart_screenshot(
                context=context,
                chart_url=chart_url,
                hide_ui=HIDE_UI,
                viewport_w=VIEWPORT_W,
                viewport_h=VIEWPORT_H,
                stabilize_wait_ms=STABILIZE_WAIT_MS
            )
            
            # Build analysis prompt
            prompt = "请分析这张 CoinGlass Legend 图表，包括主要指标、价格趋势、资金流向和关键交易信号。"
            if extra_prompt:
                prompt = f"{extra_prompt}\n\n{prompt}"
            
            # Call LLM for analysis
            analysis = await llm_analyze_png(
                png_bytes=png_bytes,
                prompt=prompt,
                api_key=LLM_API_KEY,
                api_base=LLM_API_BASE,
                model=LLM_MODEL,
                timeout_s=LLM_TIMEOUT_S
            )
            
            results.append({
                "account": account_name,
                "analysis": analysis
            })
            logger.info(f"Account {account_name}: analysis completed")
            
        except Exception as e:
            # Capture full traceback for debugging
            error_traceback = traceback.format_exc()
            logger.error(f"Account {account_name} failed:\n{error_traceback}")
            print(f"Account {account_name} failed:\n{error_traceback}", file=sys.stderr)
            
            # Determine error type
            if "截图" in str(e) or "screenshot" in str(e).lower() or "page" in str(e).lower():
                error_prefix = "截图失败"
            else:
                error_prefix = "LLM 分析失败"
            
            results.append({
                "account": account_name,
                "analysis": f"{error_prefix}: {type(e).__name__}: {e}"
            })
            
        finally:
            # Clean up context
            if context:
                try:
                    await context.close()
                except:
                    pass
    
    return results


# =============================================================================
# MCP Server Setup
# =============================================================================

app = Server("coinglass-legend-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="analyze_coinglass_legend_chart",
            description=(
                "分析 CoinGlass Legend 图表。"
                "使用多账号分别截图并调用 LLM 进行分析，返回每个账号的分析结果。"
                "只返回文本分析，不返回图片或 base64。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chart_url": {
                        "type": "string",
                        "description": (
                            "CoinGlass Legend 图表 URL。"
                            f"默认: {DEFAULT_CHART_URL}"
                        ),
                        "default": DEFAULT_CHART_URL
                    },
                    "extra_prompt": {
                        "type": "string",
                        "description": "附加分析要求（可选）",
                        "default": ""
                    }
                },
                "required": []
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "analyze_coinglass_legend_chart":
        chart_url = arguments.get("chart_url", DEFAULT_CHART_URL)
        extra_prompt = arguments.get("extra_prompt", "")
        
        # Validate URL
        if not chart_url.startswith("https://legend.coinglass.com"):
            return [TextContent(
                type="text",
                text="错误: URL 必须是 legend.coinglass.com 域名下的图表链接"
            )]
        
        logger.info(f"Starting analysis for URL: {chart_url}")
        
        # Perform analysis for all accounts
        results = await analyze_chart_for_all_accounts(
            chart_url=chart_url,
            extra_prompt=extra_prompt
        )
        
        # Format response (only text, no images/base64/urls)
        response_parts = []
        response_parts.append(f"=== CoinGlass Legend 图表分析 ===\n")
        response_parts.append(f"图表 URL: {chart_url}\n")
        response_parts.append(f"分析账号数: {len(results)}\n")
        response_parts.append("-" * 50 + "\n")
        
        for i, result in enumerate(results, 1):
            response_parts.append(f"\n【账号 {i}: {result['account']}】\n")
            response_parts.append(result['analysis'])
            response_parts.append("\n")
            if i < len(results):
                response_parts.append("-" * 40 + "\n")
        
        response_parts.append("\n" + "=" * 50)
        
        # Return as structured JSON-like format for programmatic access
        import json
        structured_result = {
            "results": results
        }
        
        return [
            TextContent(
                type="text",
                text="\n".join(response_parts)
            ),
            TextContent(
                type="text",
                text=f"\n\n[JSON 格式结果]\n```json\n{json.dumps(structured_result, ensure_ascii=False, indent=2)}\n```"
            )
        ]
    
    return [TextContent(type="text", text=f"未知工具: {name}")]


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Run the MCP server."""
    logger.info("Starting CoinGlass Legend MCP Server...")
    logger.info(f"Viewport: {VIEWPORT_W}x{VIEWPORT_H}")
    logger.info(f"Stabilize wait: {STABILIZE_WAIT_MS}ms")
    logger.info(f"Hide UI: {HIDE_UI}")
    logger.info(f"LLM Model: {LLM_MODEL}")
    logger.info(f"LLM API Base: {LLM_API_BASE}")
    logger.info(f"Accounts config: {ACCOUNTS_YAML}")
    
    # Validate configuration at startup
    try:
        accounts = load_accounts_config()
        logger.info(f"Validated {len(accounts)} accounts from config")
    except Exception as e:
        logger.warning(f"Config validation warning: {e}")
        logger.warning("Server starting anyway - config errors will be reported at runtime")
    
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set - LLM analysis will fail")
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await cleanup()


def run():
    """Synchronous entry point for script execution."""
    asyncio.run(main())


if __name__ == "__main__":
    run()

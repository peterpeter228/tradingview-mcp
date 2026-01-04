#!/usr/bin/env python3
"""
TradingView MCP Server - Multi-Account Analysis Edition
Supports multiple TradingView accounts, CometAPI LLM analysis, high-res screenshots.
Returns analysis text only - no base64/images.
"""

import os
import sys
import asyncio
import traceback
import logging
from typing import Optional
import base64

import yaml
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, Page
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from openai import AsyncOpenAI

# Configure logging to stderr for systemd/journalctl
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global browser instance (reused for efficiency)
_playwright = None
_browser: Optional[Browser] = None

# LLM Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.cometapi.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")

# Accounts configuration path
ACCOUNTS_CONFIG_PATH = os.getenv(
    "TRADINGVIEW_ACCOUNTS_CONFIG", "/etc/tradingview-mcp/accounts.yaml"
)

# High-res viewport settings
VIEWPORT_WIDTH = 2560
VIEWPORT_HEIGHT = 1440


def load_accounts() -> list[dict]:
    """Load TradingView accounts from YAML config."""
    config_path = ACCOUNTS_CONFIG_PATH

    # Also check local path
    if not os.path.exists(config_path):
        local_path = os.path.join(os.path.dirname(__file__), "../../accounts.yaml")
        if os.path.exists(local_path):
            config_path = local_path
        else:
            # Try workspace root
            workspace_path = os.path.join(os.path.dirname(__file__), "../../accounts.yaml")
            if os.path.exists(workspace_path):
                config_path = workspace_path

    if not os.path.exists(config_path):
        logger.error(f"Accounts config not found: {config_path}")
        return []

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        accounts = config.get("tradingview_accounts", [])
        logger.info(f"Loaded {len(accounts)} TradingView accounts")
        return accounts
    except Exception as e:
        logger.error(f"Failed to load accounts config: {e}")
        print(traceback.format_exc(), file=sys.stderr)
        return []


async def get_browser() -> Browser:
    """Get or create a persistent browser instance."""
    global _playwright, _browser

    if _browser is not None:
        return _browser

    # Start Playwright
    if _playwright is None:
        _playwright = await async_playwright().start()

    # Launch browser in headless mode
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    logger.info("Browser launched successfully")
    return _browser


async def hide_ui_elements(page: Page) -> None:
    """Hide TradingView UI elements that obstruct the chart."""
    try:
        # JavaScript to hide UI elements
        await page.evaluate(
            """() => {
            // Hide right sidebar (watchlist/details panel)
            const rightPanel = document.querySelector('[data-name="right-toolbar"]');
            if (rightPanel) rightPanel.style.display = 'none';
            
            // Hide drawing toolbar on right
            const drawingToolbar = document.querySelector('.right-toolbar');
            if (drawingToolbar) drawingToolbar.style.display = 'none';
            
            // Hide watchlist
            const watchlist = document.querySelector('[data-name="watchlist"]');
            if (watchlist) watchlist.style.display = 'none';
            
            // Hide details panel
            const detailsPanel = document.querySelector('[data-name="details"]');
            if (detailsPanel) detailsPanel.style.display = 'none';
            
            // Hide object tree panel
            const objectTree = document.querySelector('[data-name="object-tree"]');
            if (objectTree) objectTree.style.display = 'none';
            
            // Hide top toolbar header
            const header = document.querySelector('.layout__area--top');
            if (header) header.style.display = 'none';
            
            // Hide bottom toolbar
            const bottomBar = document.querySelector('.layout__area--bottom');
            if (bottomBar) bottomBar.style.display = 'none';
            
            // Hide left toolbar
            const leftToolbar = document.querySelector('.layout__area--left');
            if (leftToolbar) leftToolbar.style.display = 'none';
            
            // Expand chart area
            const chartArea = document.querySelector('.chart-container');
            if (chartArea) {
                chartArea.style.width = '100vw';
                chartArea.style.height = '100vh';
            }
            
            // Hide any floating panels
            const floatingPanels = document.querySelectorAll('[class*="floating"]');
            floatingPanels.forEach(p => p.style.display = 'none');
            
            // Hide popup menus
            const popups = document.querySelectorAll('[class*="popup"]');
            popups.forEach(p => p.style.display = 'none');
        }"""
        )
        logger.info("UI elements hidden")
    except Exception as e:
        logger.warning(f"Failed to hide some UI elements: {e}")


async def create_future_whitespace(page: Page) -> None:
    """Drag the timeline left to create whitespace on the right for future price levels."""
    try:
        # Find the chart canvas and drag it
        await page.evaluate(
            """() => {
            // Try to find the chart canvas
            const canvas = document.querySelector('canvas');
            if (!canvas) return;
            
            const rect = canvas.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            
            // Create and dispatch mouse events to simulate drag
            const mouseDown = new MouseEvent('mousedown', {
                bubbles: true,
                cancelable: true,
                clientX: centerX + 200,
                clientY: centerY,
                button: 0
            });
            
            const mouseMove = new MouseEvent('mousemove', {
                bubbles: true,
                cancelable: true,
                clientX: centerX - 300,
                clientY: centerY,
                button: 0
            });
            
            const mouseUp = new MouseEvent('mouseup', {
                bubbles: true,
                cancelable: true,
                clientX: centerX - 300,
                clientY: centerY,
                button: 0
            });
            
            canvas.dispatchEvent(mouseDown);
            canvas.dispatchEvent(mouseMove);
            canvas.dispatchEvent(mouseUp);
        }"""
        )

        # Also try using Playwright's native mouse drag
        try:
            chart_area = await page.query_selector(".chart-markup-table")
            if chart_area:
                box = await chart_area.bounding_box()
                if box:
                    start_x = box["x"] + box["width"] * 0.7
                    start_y = box["y"] + box["height"] * 0.5
                    end_x = box["x"] + box["width"] * 0.3

                    await page.mouse.move(start_x, start_y)
                    await page.mouse.down()
                    await page.mouse.move(end_x, start_y, steps=10)
                    await page.mouse.up()
                    logger.info("Timeline dragged to create future whitespace")
        except Exception as e:
            logger.warning(f"Native mouse drag failed: {e}")

    except Exception as e:
        logger.warning(f"Failed to create future whitespace: {e}")


async def capture_chart_screenshot(
    account: dict, chart_url: str, symbol: str = None, interval: str = "D"
) -> tuple[str, Optional[bytes]]:
    """
    Capture a TradingView chart screenshot for a specific account.

    Returns:
        Tuple of (account_name, screenshot_bytes or None)
    """
    account_name = account.get("name", "unknown")
    session_id = account.get("session")
    session_sign = account.get("sign")

    if not session_id or not session_sign:
        logger.error(f"Account {account_name}: Missing session or sign")
        return account_name, None

    context = None
    page = None

    try:
        browser = await get_browser()

        # Create new context for this account
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            device_scale_factor=2,  # High DPI for crisp screenshots
        )

        # Add TradingView cookies
        await context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": session_id,
                    "domain": ".tradingview.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
                {
                    "name": "sessionid_sign",
                    "value": session_sign,
                    "domain": ".tradingview.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
            ]
        )

        page = await context.new_page()

        # Build URL - prefer chartId URL if provided, otherwise build from symbol
        if chart_url and "/chart/" in chart_url:
            # Use provided chart URL directly (with chartId)
            final_url = chart_url
            if not final_url.startswith("http"):
                final_url = f"https://www.tradingview.com{chart_url}"
        elif symbol:
            # Build URL from symbol
            final_url = f"https://www.tradingview.com/chart/?symbol={symbol}&interval={interval}"
        else:
            logger.error(f"Account {account_name}: No chart URL or symbol provided")
            return account_name, None

        logger.info(f"Account {account_name}: Loading {final_url}")

        # Navigate to chart
        try:
            await page.goto(final_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning(f"Account {account_name}: Initial load timeout, continuing... {e}")

        # Wait for chart elements to load
        try:
            await page.wait_for_selector("canvas", timeout=30000)
        except Exception as e:
            logger.warning(f"Account {account_name}: Canvas not found: {e}")

        # Wait for chart indicators to render
        await asyncio.sleep(1)

        # Hide UI elements
        await hide_ui_elements(page)

        # Create future whitespace
        await create_future_whitespace(page)

        # Brief wait for stability
        await asyncio.sleep(0.5)

        # Take screenshot
        screenshot = await page.screenshot(
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        )

        logger.info(f"Account {account_name}: Screenshot captured ({len(screenshot)} bytes)")
        return account_name, screenshot

    except Exception as e:
        logger.error(f"Account {account_name}: Screenshot failed: {e}")
        print(traceback.format_exc(), file=sys.stderr)
        return account_name, None

    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass


async def analyze_with_llm(screenshot_bytes: bytes, symbol: str, account_name: str) -> str:
    """
    Analyze chart screenshot using CometAPI (OpenAI-compatible).
    Returns analysis text only - no base64/images.
    """
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY is not set!")
        return "LLM 分析失败：EnvironmentError: LLM_API_KEY not configured. Please set LLM_API_KEY in .env"

    logger.info(f"Account {account_name}: Starting LLM analysis...")
    logger.info(f"  API Base: {LLM_API_BASE}")
    logger.info(f"  Model: {LLM_MODEL}")
    logger.info(f"  Screenshot size: {len(screenshot_bytes)} bytes")

    try:
        client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)

        # Encode screenshot to base64 for LLM (internal use only, not returned to user)
        image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""你是一位专业的技术分析师。请分析这张 TradingView 图表截图（{symbol}）。

请提供以下分析：

1. **趋势判断**：当前价格趋势（上升/下降/震荡）
2. **关键价位**：
   - 支撑位（Support Levels）
   - 阻力位（Resistance Levels）
   - Key Levels（如果图表上有标注）
3. **技术指标解读**：根据图表上显示的指标（如有）
4. **形态分析**：识别任何显著的价格形态
5. **交易建议**：基于技术分析的操作建议

请用简洁专业的中文回答，重点突出可操作的信息。"""

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=2000,
            temperature=0.3,
        )

        analysis = response.choices[0].message.content
        logger.info(f"Account {account_name}: LLM analysis completed")
        return analysis

    except Exception as e:
        error_msg = f"LLM 分析失败：{type(e).__name__}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"  API Base: {LLM_API_BASE}")
        logger.error(f"  Model: {LLM_MODEL}")
        logger.error(f"  API Key set: {bool(LLM_API_KEY)}")
        print(traceback.format_exc(), file=sys.stderr)
        return error_msg


async def cleanup():
    """Cleanup browser resources."""
    global _browser, _playwright

    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None

    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None


# Initialize MCP server
app = Server("tradingview-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="analyze_tradingview_chart",
            description="分析 TradingView 图表。支持多账号并行分析，返回每个账号的技术分析结果。"
            "可以传入 chart URL（推荐，如 /chart/xxxxx）或 symbol（如 BINANCE:BTCUSDT）。"
            "返回纯文本分析结果，不包含图片。",
            inputSchema={
                "type": "object",
                "properties": {
                    "chart_url": {
                        "type": "string",
                        "description": "TradingView 图表 URL，推荐使用 /chart/xxxxx 格式（保存的图表布局）",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "交易对符号，格式 'EXCHANGE:SYMBOL'（如 'BINANCE:BTCUSDT'）。如果提供了 chart_url 则此参数可选",
                    },
                    "interval": {
                        "type": "string",
                        "description": "时间周期：1, 5, 15, 30, 60, 240（分钟）或 D, W, M（日/周/月）",
                        "default": "D",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_accounts",
            description="列出已配置的 TradingView 账号",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_accounts":
        accounts = load_accounts()
        if not accounts:
            return [
                TextContent(
                    type="text", text="未配置 TradingView 账号。请检查 accounts.yaml 配置文件。"
                )
            ]

        account_list = "\n".join([f"- {acc.get('name', 'unnamed')}" for acc in accounts])
        return [
            TextContent(
                type="text", text=f"已配置 {len(accounts)} 个 TradingView 账号：\n{account_list}"
            )
        ]

    elif name == "analyze_tradingview_chart":
        chart_url = arguments.get("chart_url", "")
        symbol = arguments.get("symbol", "")
        interval = arguments.get("interval", "D")

        if not chart_url and not symbol:
            return [
                TextContent(
                    type="text",
                    text="错误：请提供 chart_url 或 symbol 参数。\n"
                    "示例：chart_url='/chart/xxxxx' 或 symbol='BINANCE:BTCUSDT'",
                )
            ]

        accounts = load_accounts()
        if not accounts:
            return [
                TextContent(
                    type="text",
                    text="错误：未配置 TradingView 账号。请检查 accounts.yaml 配置文件。",
                )
            ]

        # Display symbol for logging
        display_symbol = symbol if symbol else chart_url.split("/")[-1] if chart_url else "unknown"
        logger.info(f"Starting analysis for {display_symbol}")
        logger.info(f"Processing {len(accounts)} account(s) in PARALLEL")

        async def process_single_account(account: dict) -> dict:
            """Process a single account - screenshot + LLM analysis."""
            account_name = account.get("name", "unknown")
            logger.info(f"[{account_name}] Starting...")

            try:
                # Capture screenshot
                _, screenshot = await capture_chart_screenshot(
                    account=account,
                    chart_url=chart_url,
                    symbol=symbol,
                    interval=interval,
                )

                if screenshot is None:
                    return {
                        "account": account_name,
                        "analysis": f"截图失败：无法获取账号 {account_name} 的图表截图",
                    }

                # Analyze with LLM
                analysis = await analyze_with_llm(
                    screenshot_bytes=screenshot,
                    symbol=display_symbol,
                    account_name=account_name,
                )

                logger.info(f"[{account_name}] Completed!")
                return {"account": account_name, "analysis": analysis}

            except Exception as e:
                error_msg = f"处理失败：{type(e).__name__}: {str(e)}"
                logger.error(f"[{account_name}] {error_msg}")
                print(traceback.format_exc(), file=sys.stderr)
                return {"account": account_name, "analysis": error_msg}

        # Process all accounts in parallel
        results = await asyncio.gather(
            *[process_single_account(acc) for acc in accounts],
            return_exceptions=False,
        )

        # Format response - analysis text only, no images
        response_parts = []
        for r in results:
            response_parts.append(f"## 账号: {r['account']}\n\n{r['analysis']}")

        response_text = "\n\n---\n\n".join(response_parts)

        # Return structured result
        import json

        structured_result = json.dumps({"results": results}, ensure_ascii=False, indent=2)

        return [
            TextContent(
                type="text",
                text=f"{response_text}\n\n---\n\n**结构化数据：**\n```json\n{structured_result}\n```",
            )
        ]

    return [TextContent(type="text", text=f"未知工具: {name}")]


async def main():
    """Run the MCP server (stdio mode)."""
    logger.info("=" * 50)
    logger.info("Starting TradingView MCP Server (stdio mode)...")
    logger.info("=" * 50)

    # Log configuration
    logger.info(f"LLM_API_BASE: {LLM_API_BASE}")
    logger.info(f"LLM_MODEL: {LLM_MODEL}")
    logger.info(f"LLM_API_KEY: {'SET (' + LLM_API_KEY[:8] + '...)' if LLM_API_KEY else 'NOT SET!'}")
    logger.info(f"ACCOUNTS_CONFIG_PATH: {ACCOUNTS_CONFIG_PATH}")

    # Validate LLM configuration
    if not LLM_API_KEY:
        logger.error("ERROR: LLM_API_KEY not found in environment!")
        logger.error("Please set LLM_API_KEY in .env file or environment")

    # Load and validate accounts
    accounts = load_accounts()
    if not accounts:
        logger.error("ERROR: No TradingView accounts configured!")
        logger.error(f"Please create accounts config at: {ACCOUNTS_CONFIG_PATH}")
    else:
        logger.info(f"Loaded {len(accounts)} TradingView accounts:")
        for acc in accounts:
            name = acc.get("name", "unnamed")
            has_session = "YES" if acc.get("session") else "NO"
            has_sign = "YES" if acc.get("sign") else "NO"
            logger.info(f"  - {name}: session={has_session}, sign={has_sign}")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await cleanup()


def run():
    """Entry point for the MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()

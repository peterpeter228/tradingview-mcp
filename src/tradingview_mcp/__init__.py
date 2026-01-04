"""
TradingView MCP Server - Multi-Account Analysis Edition

Features:
- Multi-account TradingView support via YAML config
- LLM analysis via CometAPI (OpenAI-compatible)
- High-resolution chart screenshots (2560x1440)
- Auto-hide UI elements for clean screenshots
- Returns analysis text only - no base64/images
"""

__version__ = "0.2.0"

from .server import main, run, app

__all__ = ["main", "run", "app", "__version__"]

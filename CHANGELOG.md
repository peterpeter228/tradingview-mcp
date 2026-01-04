# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-01-04

### Added
- **多账号支持**：通过 YAML 配置多个 TradingView 账号轮询分析
- **LLM 分析集成**：使用 CometAPI（OpenAI 兼容）进行图表技术分析
- **高分辨率截图**：2560×1440 视口，device_scale_factor=2
- **UI 自动隐藏**：隐藏 watchlist、toolbar、sidebar 等干扰元素
- **时间轴拖动**：创建右侧未来空白区，防止 Key Levels 被遮挡
- **systemd 服务**：支持后台运行和自动重启
- **supergateway 集成**：stdio MCP 通过 SSE 暴露在 8053 端口

### Changed
- MCP 工具改为 `analyze_tradingview_chart`（一键返回分析）
- 返回格式改为纯文本分析，不再返回 base64/图片
- 错误处理增强，打印完整 traceback 到 stderr

### Removed
- `get_chart_snapshot` 工具（合并到 analyze_tradingview_chart）
- `validate_session` 工具
- `list_timeframes` 工具
- ImageContent 返回类型

### Fixed
- LLM 异常被吞问题：现在打印完整 traceback
- 截图 Key Levels 被遮挡问题：自动隐藏 UI + 创建空白区
- chart URL 不稳定问题：优先使用 chartId URL
- systemd 环境变量问题：使用 EnvironmentFile

## [0.1.0] - 2025-10-31

### Added
- Initial release with Playwright-based chart fetching
- Three MCP tools: `get_chart_snapshot`, `validate_session`, `list_timeframes`
- Session-based authentication via TradingView cookies
- Support for all TradingView symbols and timeframes
- Persistent browser reuse for efficiency
- Comprehensive documentation in README.md

### Technical Details
- Uses Playwright in headless mode (~150MB memory)
- Optimized with browser instance reuse
- Response time: 3-5 seconds per chart
- Supports customizable dimensions and themes

[0.2.0]: https://github.com/yourusername/tradingview-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/yourusername/tradingview-mcp/releases/tag/v0.1.0

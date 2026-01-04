# TradingView MCP Server

多账号 TradingView 图表分析 MCP 服务器，支持 CometAPI LLM 分析。

## 功能特性

- ✅ **多账号支持**：通过 YAML 配置多个 TradingView 账号，依次轮询分析
- ✅ **LLM 分析**：使用 CometAPI（OpenAI 兼容）进行图表技术分析
- ✅ **仅返回分析文本**：不返回 base64/图片/screenshot
- ✅ **高分辨率截图**：2560×1440 视口，确保图表清晰
- ✅ **自动隐藏 UI**：隐藏 watchlist、toolbar 等干扰元素
- ✅ **SSE 端口固定**：8053 端口（通过 supergateway）
- ✅ **systemd 自动重启**：后台服务支持

## 系统要求

- Python 3.10+
- Node.js 16+ (用于 supergateway)
- Chromium (由 Playwright 自动安装)

## 快速安装

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/tradingview-mcp.git
cd tradingview-mcp
```

### 2. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3-full python3-venv nodejs npm
```

### 3. 一键安装（推荐）

```bash
# 运行自动安装脚本
./setup.sh

# 安装 supergateway（需要 sudo）
sudo npm install -g supergateway
```

### 或手动安装

```bash
# 创建虚拟环境（必须！现代 Linux 不允许直接 pip install）
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
sudo playwright install-deps chromium

# 安装 supergateway（全局）
sudo npm install -g supergateway
```

### 3. 配置文件

```bash
# 复制配置模板
cp .env.example .env
cp accounts.yaml.example accounts.yaml

# 编辑配置
nano .env           # 配置 LLM API Key
nano accounts.yaml  # 配置 TradingView 账号
```

### 4. 配置 .env

```env
LLM_API_KEY=your_comet_api_key_here
LLM_API_BASE=https://api.cometapi.com/v1
LLM_MODEL=openai/gpt-4o
TRADINGVIEW_ACCOUNTS_CONFIG=./accounts.yaml
```

### 5. 配置 accounts.yaml

```yaml
tradingview_accounts:
  - name: account1
    session: your_sessionid_cookie
    sign: your_sessionid_sign_cookie

  - name: account2
    session: another_sessionid
    sign: another_sign
```

**获取 TradingView Cookie：**
1. 登录 TradingView
2. 打开开发者工具 (F12)
3. Application → Cookies → tradingview.com
4. 复制 `sessionid` 和 `sessionid_sign` 的值

## 运行方式

### 开发模式 - SSE (推荐)

```bash
chmod +x run-sse.sh
./run-sse.sh
```

服务将在 `http://localhost:8053` 启动。

### 开发模式 - stdio

```bash
chmod +x run-stdio.sh
./run-stdio.sh
```

### 生产部署 (systemd)

```bash
# 运行安装脚本
sudo ./deploy/install.sh

# 编辑配置
sudo nano /etc/tradingview-mcp/env
sudo nano /etc/tradingview-mcp/accounts.yaml

# 启动服务
sudo systemctl start tradingview-mcp
sudo systemctl enable tradingview-mcp

# 查看日志
sudo journalctl -u tradingview-mcp -f
```

## MCP 工具

### analyze_tradingview_chart

分析 TradingView 图表，支持多账号轮询。

**参数：**
- `chart_url` (string, 可选): TradingView 图表 URL，推荐使用 `/chart/xxxxx` 格式
- `symbol` (string, 可选): 交易对符号，如 `BINANCE:BTCUSDT`
- `interval` (string, 默认 "D"): 时间周期

**示例调用：**

```json
{
  "name": "analyze_tradingview_chart",
  "arguments": {
    "chart_url": "/chart/YOUR_CHART_ID"
  }
}
```

或

```json
{
  "name": "analyze_tradingview_chart",
  "arguments": {
    "symbol": "BINANCE:BTCUSDT",
    "interval": "4H"
  }
}
```

**返回格式：**

```json
{
  "results": [
    {
      "account": "account1",
      "analysis": "技术分析内容..."
    },
    {
      "account": "account2",
      "analysis": "技术分析内容..."
    }
  ]
}
```

### list_accounts

列出已配置的 TradingView 账号。

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| SSE | 8053 | supergateway 暴露的 SSE 端点 |

**注意：** 代码中不再使用 8006 或其他端口。

## systemd 服务管理

```bash
# 启动
sudo systemctl start tradingview-mcp

# 停止
sudo systemctl stop tradingview-mcp

# 重启
sudo systemctl restart tradingview-mcp

# 查看状态
sudo systemctl status tradingview-mcp

# 查看日志
sudo journalctl -u tradingview-mcp -f

# 开机自启
sudo systemctl enable tradingview-mcp

# 禁用自启
sudo systemctl disable tradingview-mcp
```

## 目录结构

```
tradingview-mcp/
├── src/
│   └── tradingview_mcp/
│       ├── __init__.py
│       └── server.py          # MCP 服务器主代码
├── deploy/
│   ├── install.sh             # 安装脚本
│   ├── uninstall.sh           # 卸载脚本
│   ├── tradingview-mcp.service # systemd 服务文件
│   └── env.example            # 环境变量模板
├── .env.example               # 本地环境变量模板
├── accounts.yaml.example      # 账号配置模板
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目配置
├── run-sse.sh                 # SSE 模式启动脚本
└── run-stdio.sh               # stdio 模式启动脚本
```

## 故障排查

### 0. PEP 668 错误（externally-managed-environment）

如果看到 `externally-managed-environment` 错误，说明系统不允许直接 `pip install`。

**解决方案：使用虚拟环境**
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活后再安装
source venv/bin/activate
pip install -r requirements.txt
```

### 1. LLM 分析失败

检查日志：
```bash
sudo journalctl -u tradingview-mcp -f
```

常见原因：
- `LLM_API_KEY` 未配置或无效
- API 配额用尽
- 网络问题

### 2. 截图失败

检查：
- TradingView session cookie 是否过期
- accounts.yaml 配置是否正确
- Playwright 浏览器是否安装

### 3. 端口被占用

```bash
# 检查 8053 端口
ss -lntp | grep 8053

# 如果被占用，找出进程
sudo lsof -i :8053
```

### 4. 环境变量未生效

确保 systemd 从 EnvironmentFile 加载：
```bash
cat /etc/tradingview-mcp/env
sudo systemctl daemon-reload
sudo systemctl restart tradingview-mcp
```

## 安全建议

1. **保护配置文件**：
   ```bash
   sudo chmod 600 /etc/tradingview-mcp/env
   sudo chmod 600 /etc/tradingview-mcp/accounts.yaml
   ```

2. **定期更新 Cookie**：TradingView session 会过期，需要定期更新

3. **不要将敏感信息提交到 Git**：确保 `.env` 和 `accounts.yaml` 在 `.gitignore` 中

## License

MIT

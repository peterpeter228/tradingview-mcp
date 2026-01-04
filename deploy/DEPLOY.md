# CoinGlass Legend MCP Server 部署指南

## 概述

本服务提供 CoinGlass Legend 图表的多账号截图与 LLM 分析功能，通过 MCP (Model Context Protocol) 协议提供服务，使用 supergateway 暴露为 SSE 接口。

**固定端口**: `8056`

## 系统要求

- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- Python 3.10+
- Node.js 18+ (用于 supergateway)
- 至少 2GB RAM
- 网络访问 legend.coinglass.com 和 CometAPI

## 一、安装步骤

### 1.1 创建服务用户

```bash
sudo useradd -r -s /bin/false -m -d /opt/coinglass-legend-mcp coinglass-mcp
```

### 1.2 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm

# 或使用 nvm 安装 Node.js
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
```

### 1.3 安装项目代码

```bash
# 克隆仓库
sudo mkdir -p /opt/coinglass-legend-mcp
sudo chown coinglass-mcp:coinglass-mcp /opt/coinglass-legend-mcp

cd /opt/coinglass-legend-mcp
sudo -u coinglass-mcp git clone https://github.com/yourusername/tradingview-mcp.git .

# 或者直接复制代码
# sudo cp -r /path/to/tradingview-mcp/* /opt/coinglass-legend-mcp/
# sudo chown -R coinglass-mcp:coinglass-mcp /opt/coinglass-legend-mcp
```

### 1.4 创建 Python 虚拟环境并安装依赖

```bash
cd /opt/coinglass-legend-mcp

# 创建虚拟环境
sudo -u coinglass-mcp python3.11 -m venv venv

# 激活并安装依赖
sudo -u coinglass-mcp ./venv/bin/pip install --upgrade pip
sudo -u coinglass-mcp ./venv/bin/pip install -r requirements.txt

# 安装 Playwright 浏览器
sudo -u coinglass-mcp ./venv/bin/playwright install chromium
sudo -u coinglass-mcp ./venv/bin/playwright install-deps
```

### 1.5 安装 supergateway

```bash
# 全局安装 supergateway
sudo npm install -g supergateway

# 或者在项目目录使用 npx（systemd unit 中已配置）
```

## 二、配置文件

### 2.1 创建配置目录

```bash
sudo mkdir -p /etc/coinglass-legend-mcp
sudo chown coinglass-mcp:coinglass-mcp /etc/coinglass-legend-mcp
sudo chmod 750 /etc/coinglass-legend-mcp
```

### 2.2 配置 LLM API

```bash
sudo cp deploy/llm.env.example /etc/coinglass-legend-mcp/llm.env
sudo chmod 600 /etc/coinglass-legend-mcp/llm.env
sudo chown coinglass-mcp:coinglass-mcp /etc/coinglass-legend-mcp/llm.env

# 编辑配置
sudo nano /etc/coinglass-legend-mcp/llm.env
```

配置内容：

```env
LLM_API_KEY=sk-your-cometapi-key-here
LLM_API_BASE=https://api.cometapi.com/v1
LLM_MODEL=openai/gpt-5.2
LLM_TIMEOUT_S=120
```

### 2.3 配置多账号 Cookie

```bash
sudo cp deploy/accounts.yaml.example /etc/coinglass-legend-mcp/accounts.yaml
sudo chmod 600 /etc/coinglass-legend-mcp/accounts.yaml
sudo chown coinglass-mcp:coinglass-mcp /etc/coinglass-legend-mcp/accounts.yaml

# 编辑配置
sudo nano /etc/coinglass-legend-mcp/accounts.yaml
```

配置示例：

```yaml
accounts:
  - name: acc1
    cookies:
      - name: session
        value: "your_real_session_cookie"
        domain: ".coinglass.com"
        path: "/"
        secure: true
        httpOnly: true
      - name: legend_token
        value: "your_real_legend_token"
        domain: "legend.coinglass.com"
        path: "/"
        secure: true
        httpOnly: false
  - name: acc2
    cookies:
      - name: session
        value: "account2_session"
        domain: ".coinglass.com"
        path: "/"
```

**获取 Cookie 步骤**:

1. 打开浏览器，登录 https://legend.coinglass.com
2. 按 F12 打开开发者工具
3. 切换到 Application → Cookies
4. 找到 `.coinglass.com` 和 `legend.coinglass.com` 下的 cookie
5. 复制 `session`、`legend_token` 等关键 cookie 值

## 三、安装 systemd 服务

### 3.1 复制 service 文件

```bash
sudo cp deploy/coinglass-legend-mcp-sse-8056.service /etc/systemd/system/

# 修改 ExecStart 中的 python 路径为虚拟环境路径
sudo sed -i 's|python -m|/opt/coinglass-legend-mcp/venv/bin/python -m|' \
    /etc/systemd/system/coinglass-legend-mcp-sse-8056.service
```

### 3.2 重载并启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable coinglass-legend-mcp-sse-8056
sudo systemctl start coinglass-legend-mcp-sse-8056
```

### 3.3 检查服务状态

```bash
sudo systemctl status coinglass-legend-mcp-sse-8056
```

## 四、验证部署

### 4.1 检查端口监听

```bash
ss -lntp | grep ':8056'
# 预期输出: LISTEN 0 xxx *:8056 *:* users:(("node",...))
```

### 4.2 健康检查

```bash
curl -sS http://127.0.0.1:8056/healthz
# 预期输出: {"status":"ok"} 或类似
```

### 4.3 列出可用工具

```bash
# 使用 curl 调用 MCP tools/list
curl -X POST http://127.0.0.1:8056/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

预期返回包含 `analyze_coinglass_legend_chart` 工具。

### 4.4 调用分析工具

```bash
curl -X POST http://127.0.0.1:8056/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "analyze_coinglass_legend_chart",
      "arguments": {
        "chart_url": "https://legend.coinglass.com/zh/chart/88314a3573a644dabdd85431bea14b7d",
        "extra_prompt": "请重点分析资金流向"
      }
    }
  }'
```

## 五、日志查看

```bash
# 实时查看日志
sudo journalctl -u coinglass-legend-mcp-sse-8056 -f

# 查看最近 100 行日志
sudo journalctl -u coinglass-legend-mcp-sse-8056 -n 100

# 查看错误日志
sudo journalctl -u coinglass-legend-mcp-sse-8056 -p err
```

## 六、常见问题

### Q1: 浏览器启动失败

```bash
# 安装浏览器依赖
sudo -u coinglass-mcp /opt/coinglass-legend-mcp/venv/bin/playwright install-deps
```

### Q2: Cookie 过期导致截图失败

更新 `/etc/coinglass-legend-mcp/accounts.yaml` 中的 cookie 值，然后重启服务：

```bash
sudo systemctl restart coinglass-legend-mcp-sse-8056
```

### Q3: LLM 分析超时

增加超时时间，编辑 `/etc/coinglass-legend-mcp/llm.env`：

```env
LLM_TIMEOUT_S=180
```

### Q4: 端口被占用

```bash
# 检查占用端口的进程
sudo lsof -i :8056

# 强制使用 8056 端口（确保只运行一个实例）
sudo systemctl stop coinglass-legend-mcp-sse-8056
sudo kill $(lsof -t -i :8056)
sudo systemctl start coinglass-legend-mcp-sse-8056
```

## 七、安全建议

1. **限制配置文件权限**：确保 `llm.env` 和 `accounts.yaml` 只有服务用户可读
2. **防火墙配置**：仅允许可信 IP 访问 8056 端口
3. **定期轮换 Cookie**：CoinGlass cookie 可能会过期，建议定期更新
4. **API Key 保护**：不要将 `llm.env` 提交到版本控制

```bash
# 防火墙示例（仅允许本地和特定 IP）
sudo ufw allow from 127.0.0.1 to any port 8056
sudo ufw allow from 10.0.0.0/8 to any port 8056
```

## 八、维护命令

```bash
# 重启服务
sudo systemctl restart coinglass-legend-mcp-sse-8056

# 停止服务
sudo systemctl stop coinglass-legend-mcp-sse-8056

# 禁用开机自启
sudo systemctl disable coinglass-legend-mcp-sse-8056

# 更新代码后重启
cd /opt/coinglass-legend-mcp
sudo -u coinglass-mcp git pull
sudo -u coinglass-mcp ./venv/bin/pip install -r requirements.txt
sudo systemctl restart coinglass-legend-mcp-sse-8056
```

## 九、MCP 客户端配置示例

### Claude Desktop 配置

```json
{
  "mcpServers": {
    "coinglass-legend": {
      "url": "http://127.0.0.1:8056/sse"
    }
  }
}
```

### Cursor 配置

在 `.cursor/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "coinglass-legend": {
      "url": "http://127.0.0.1:8056/sse"
    }
  }
}
```

---

**版本**: 0.1.0  
**端口**: 8056 (固定)  
**协议**: MCP over SSE

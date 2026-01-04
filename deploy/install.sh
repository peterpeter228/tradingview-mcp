#!/bin/bash
#
# CoinGlass Legend MCP Server 快速安装脚本
# 
# 使用方法:
#   sudo bash install.sh
#
# 前提条件:
# - Ubuntu 20.04+ / Debian 11+
# - 已安装 Python 3.10+
# - 已安装 Node.js 18+
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo_error "请使用 sudo 运行此脚本"
    exit 1
fi

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo_info "项目目录: $PROJECT_ROOT"

# 配置变量
SERVICE_USER="coinglass-mcp"
INSTALL_DIR="/opt/coinglass-legend-mcp"
CONFIG_DIR="/etc/coinglass-legend-mcp"
PYTHON_CMD="python3"

# 检查 Python 版本
echo_info "检查 Python 版本..."
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo_error "未找到 Python3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo_info "Python 版本: $PYTHON_VERSION"

# 检查 Node.js
echo_info "检查 Node.js..."
if ! command -v node &> /dev/null; then
    echo_error "未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi
NODE_VERSION=$(node -v)
echo_info "Node.js 版本: $NODE_VERSION"

# 创建服务用户
echo_info "创建服务用户 $SERVICE_USER..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -m -d "$INSTALL_DIR" "$SERVICE_USER"
    echo_info "用户 $SERVICE_USER 创建成功"
else
    echo_warn "用户 $SERVICE_USER 已存在"
fi

# 创建安装目录
echo_info "创建安装目录 $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# 复制项目文件
echo_info "复制项目文件..."
cp -r "$PROJECT_ROOT/src" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/pyproject.toml" "$INSTALL_DIR/"

# 设置权限
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# 创建虚拟环境并安装依赖
echo_info "创建 Python 虚拟环境..."
sudo -u "$SERVICE_USER" $PYTHON_CMD -m venv "$INSTALL_DIR/venv"

echo_info "安装 Python 依赖..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 安装 Playwright 浏览器
echo_info "安装 Playwright Chromium 浏览器..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/playwright" install chromium

echo_info "安装 Playwright 系统依赖..."
"$INSTALL_DIR/venv/bin/playwright" install-deps || echo_warn "Playwright 依赖安装可能需要手动处理"

# 创建配置目录
echo_info "创建配置目录 $CONFIG_DIR..."
mkdir -p "$CONFIG_DIR"

# 复制示例配置文件（如果不存在）
if [ ! -f "$CONFIG_DIR/llm.env" ]; then
    cp "$SCRIPT_DIR/llm.env.example" "$CONFIG_DIR/llm.env"
    echo_info "已创建 $CONFIG_DIR/llm.env（请编辑填入真实配置）"
else
    echo_warn "$CONFIG_DIR/llm.env 已存在，跳过"
fi

if [ ! -f "$CONFIG_DIR/accounts.yaml" ]; then
    cp "$SCRIPT_DIR/accounts.yaml.example" "$CONFIG_DIR/accounts.yaml"
    echo_info "已创建 $CONFIG_DIR/accounts.yaml（请编辑填入真实 Cookie）"
else
    echo_warn "$CONFIG_DIR/accounts.yaml 已存在，跳过"
fi

# 设置配置文件权限
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"
chmod 750 "$CONFIG_DIR"
chmod 600 "$CONFIG_DIR/llm.env"
chmod 600 "$CONFIG_DIR/accounts.yaml"

# 安装 systemd service
echo_info "安装 systemd service..."
SERVICE_FILE="/etc/systemd/system/coinglass-legend-mcp-sse-8056.service"

# 复制并修改 service 文件
cp "$SCRIPT_DIR/coinglass-legend-mcp-sse-8056.service" "$SERVICE_FILE"

# 替换 python 路径为虚拟环境路径
sed -i "s|python -m|$INSTALL_DIR/venv/bin/python -m|" "$SERVICE_FILE"

# 重载 systemd
systemctl daemon-reload

echo ""
echo_info "=========================================="
echo_info "安装完成！"
echo_info "=========================================="
echo ""
echo_warn "⚠️  重要：请先完成以下配置步骤："
echo ""
echo "1. 编辑 LLM API 配置:"
echo "   sudo nano $CONFIG_DIR/llm.env"
echo ""
echo "2. 编辑账号 Cookie 配置:"
echo "   sudo nano $CONFIG_DIR/accounts.yaml"
echo ""
echo "3. 启动服务:"
echo "   sudo systemctl enable coinglass-legend-mcp-sse-8056"
echo "   sudo systemctl start coinglass-legend-mcp-sse-8056"
echo ""
echo "4. 验证服务:"
echo "   ss -lntp | grep ':8056'"
echo "   curl -sS http://127.0.0.1:8056/healthz"
echo ""
echo "5. 查看日志:"
echo "   sudo journalctl -u coinglass-legend-mcp-sse-8056 -f"
echo ""

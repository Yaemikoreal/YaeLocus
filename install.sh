#!/usr/bin/env bash
set -euo pipefail

# YaeLocus v1.5.0 - 一键安装脚本 (macOS/Linux)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   YaeLocus v1.5.0 - 一键安装脚本${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 1. 检查 Python ──
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[ERROR] 未检测到 Python，请先安装 Python 3.8+${NC}"
    echo "macOS: brew install python@3.11"
    echo "Ubuntu: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1 | cut -d' ' -f2)
echo -e "${GREEN}[OK]${NC} $PYTHON $PYVER"

# ── 2. 创建虚拟环境 ──
if [ ! -f ".venv/bin/python" ]; then
    echo ""
    echo -e "${YELLOW}[*]${NC} 创建虚拟环境 .venv ..."
    "$PYTHON" -m venv .venv
    echo -e "${GREEN}[OK]${NC} 虚拟环境已创建"
else
    echo -e "${GREEN}[OK]${NC} 虚拟环境已存在"
fi

VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
VENV_PIP="$PROJECT_DIR/.venv/bin/pip"

# ── 3. 升级 pip ──
echo ""
echo -e "${YELLOW}[*]${NC} 升级 pip ..."
"$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || true

# ── 4. 安装依赖 ──
echo -e "${YELLOW}[*]${NC} 安装 YaeLocus 及依赖 ..."
"$VENV_PIP" install -e . -q 2>/dev/null || {
    echo -e "${YELLOW}[WARN]${NC} 基础安装有警告，继续 ..."
}

# AI 支持
echo -e "${YELLOW}[*]${NC} 安装 AI 支持 ..."
"$VENV_PIP" install "httpx>=0.27.0" -q 2>/dev/null || true

# Web GUI 支持
echo -e "${YELLOW}[*]${NC} 安装 Web GUI 支持 ..."
"$VENV_PIP" install fastapi uvicorn python-multipart -q 2>/dev/null || true

# ── 5. 验证 ──
echo ""
echo -e "${YELLOW}[*]${NC} 验证安装 ..."
if "$VENV_PYTHON" -m geocode.cli --help &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} 安装验证成功"
else
    echo -e "${RED}[ERROR]${NC} 安装验证失败"
    exit 1
fi

# ── 6. 创建桌面快捷方式 (Linux) ──
if [ "$(uname)" = "Linux" ] && [ -d "$HOME/.local/share/applications" ]; then
    cat > "$HOME/.local/share/applications/yaelocus.desktop" << EOF
[Desktop Entry]
Name=YaeLocus Web
Comment=Geocoding Tool Web GUI
Exec=$VENV_PYTHON -m geocode.cli serve
Path=$PROJECT_DIR
Type=Application
Categories=Utility;
EOF
    echo -e "${GREEN}[OK]${NC} 桌面快捷方式已创建"
fi

# ── 7. 创建命令行别名 ──
ALIAS_CMD="alias yaelocus='$VENV_PYTHON -m geocode.cli'"
if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "yaelocus" "$HOME/.bashrc" 2>/dev/null; then
        echo "$ALIAS_CMD" >> "$HOME/.bashrc"
        echo -e "${GREEN}[OK]${NC} 别名已添加到 ~/.bashrc"
    fi
fi
if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "yaelocus" "$HOME/.zshrc" 2>/dev/null; then
        echo "$ALIAS_CMD" >> "$HOME/.zshrc"
        echo -e "${GREEN}[OK]${NC} 别名已添加到 ~/.zshrc"
    fi
fi

# ── 8. 运行诊断 ──
echo ""
echo -e "${YELLOW}[*]${NC} 运行环境诊断 ..."
"$VENV_PYTHON" -m geocode.cli doctor 2>/dev/null || true

# ── 9. 完成 ──
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}    安装完成!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo "  快速开始:"
echo "    yaelocus serve         启动 Web 图形界面（推荐）"
echo "    yaelocus config         配置 API 密钥"
echo "    yaelocus geocode \"地址\" 单地址编码"
echo "    yaelocus run -i data/清单.xlsx  批量处理"
echo ""
echo "  提示: 重新打开终端或执行 'source ~/.bashrc' 使别名生效"
echo ""

read -r -p "是否现在启动 Web 界面? [y/N] " START_NOW
if [ "${START_NOW,,}" = "y" ]; then
    "$VENV_PYTHON" -m geocode.cli serve
fi

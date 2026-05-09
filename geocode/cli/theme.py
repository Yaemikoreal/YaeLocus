"""
YaeLocus TUI 色彩主题

从 DeepSeek-TUI 借鉴: 语义化颜色、消息类型标记、终端自适应
"""

from dataclasses import dataclass, field
from typing import Literal


# ── 语义颜色 ──────────────────────────────────────────────────

PRIMARY   = "#1a73e8"   # 品牌蓝 — 标题 / header
PRIMARY_BG = "#0d1b3e"  # 深蓝背景
SUCCESS   = "#2ecc71"   # 绿 — OK / 成功 / API 可用
WARNING   = "#f39c12"   # 橙 — 弃用 / 警告 / 注意
ERROR     = "#e74c3c"   # 红 — 失败 / 错误
MUTED     = "#9ca3af"   # 灰 — 辅助文字
DIM       = "#6b7280"   # 深灰 — 更弱的文字
CODE_BG   = "#1e1e2e"   # 深色 — 代码块背景

# 消息角色颜色
USER_COLOR  = "cyan"        # 用户输入
AI_COLOR    = "#6aaef2"     # AI 回复
SYS_COLOR   = "dim"         # 系统消息
ERR_COLOR   = "#e74c3c"     # 错误
TOOL_COLOR  = "#f39c12"     # 工具执行

# API 来源颜色（地图标记）
SOURCE_COLORS = {
    "amap": "blue",
    "tianditu": "green",
    "baidu": "red",
}

# 出行方式颜色
MODE_COLORS = {
    "driving": "#2196F3",
    "transit": "#4CAF50",
    "walking": "#FF9800",
    "bicycling": "#00BCD4",
}


# ── 消息标记前缀 ──────────────────────────────────────────────

MSG_PREFIX = {
    "user":      ("▎", USER_COLOR),
    "assistant": ("●", AI_COLOR),
    "system":    ("·", SYS_COLOR),
    "error":     ("✗", ERR_COLOR),
    "tool":      ("⚙", TOOL_COLOR),
    "thinking":  ("…", "dim"),
}

# ── Toast 级别 ────────────────────────────────────────────────

TOAST_STYLES = {
    "info":    ("[dim]ℹ[/dim]",  PRIMARY),
    "success": ("[green]✓[/green]", SUCCESS),
    "warning": ("[yellow]⚠[/yellow]", WARNING),
    "error":   ("[red]✗[/red]", ERROR),
}

# ── 进度微调器帧 ──────────────────────────────────────────────

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
STREAMING_PULSE = ["●", "○"]

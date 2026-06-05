"""
AI 工具定义 — OpenAI 兼容 function calling 格式

遵循 Claude Code 设计模式：
- 单一 execute_command 工具，CLI 命令即结构化接口
- --json 输出提供结构化返回值
- ERROR_RECOVERY_MAP 提供自动恢复路径

混合协议策略：
1. 优先使用 tools 参数让模型原生输出 tool_use 块
2. 模型不支持 tools 参数时，fallback 到 [CMD] 文本协议
"""

YAELOCUS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "执行 yaelocus CLI 命令并返回结构化 JSON 输出。"
                "可用命令包括：geocode single/batch/reverse/convert、"
                "map list/create、config check/status、cache stats/clear 等。"
                "建议使用 --json 参数获取结构化输出。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "yaelocus 完整命令，如 "
                            "'geocode single 北京市朝阳区' 或 "
                            "'config check --json' 或 "
                            "'map list --detail --json'"
                        ),
                    }
                },
                "required": ["command"],
            },
        },
    }
]

CMD_PATTERN = r"\[CMD\]\s*\n?(.*?)\n?\s*\[\/CMD\]"
MAX_AGENT_ROUNDS = 4
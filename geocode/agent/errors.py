"""
Agent 可理解的错误定义

扩展错误信息，包含自动恢复路径，供 AI Agent 理解和处理错误。
"""

from dataclasses import dataclass
from typing import Optional

from ..errors import (
    API_QUOTA_EXCEEDED,
    COLUMN_NOT_FOUND,
    FILE_NOT_FOUND,
    INVALID_API_KEY,
    NETWORK_ERROR,
    NO_API_KEY,
    GeocodeError,
)


@dataclass
class AgentRecoverableError:
    """Agent 可自动恢复的错误"""
    original_error: GeocodeError
    recoverable: bool  # Agent 是否可以自动修复
    auto_fix_action: Optional[str] = None  # 建议执行的恢复命令
    retry_after_seconds: Optional[int] = None  # 重试等待时间（秒）

    def to_dict(self) -> dict:
        return {
            "code": self.original_error.code,
            "message": self.original_error.message,
            "suggestion": self.original_error.suggestion,
            "recoverable": self.recoverable,
            "auto_fix_action": self.auto_fix_action,
            "retry_after_seconds": self.retry_after_seconds,
        }

    def to_agent_error(self) -> dict:
        """转换为 Agent 错误格式（不含 original_error）"""
        return {
            "code": self.original_error.code,
            "message": self.original_error.message,
            "suggestion": self.original_error.suggestion,
            "recoverable": self.recoverable,
            "auto_fix_action": self.auto_fix_action,
        }


# ── 错误恢复映射表 ──────────────────────────────────────────────────
# 定义每个错误码的恢复策略，供 Agent 自动处理

ERROR_RECOVERY_MAP: dict = {
    "NO_API_KEY": AgentRecoverableError(
        original_error=NO_API_KEY,
        recoverable=True,
        auto_fix_action="config setup",
        retry_after_seconds=None,
    ),
    "FILE_NOT_FOUND": AgentRecoverableError(
        original_error=FILE_NOT_FOUND,
        recoverable=False,  # 需要用户提供正确路径
        auto_fix_action=None,
        retry_after_seconds=None,
    ),
    "COLUMN_NOT_FOUND": AgentRecoverableError(
        original_error=COLUMN_NOT_FOUND,
        recoverable=True,
        auto_fix_action="map list --detail",  # 查看文件列信息
        retry_after_seconds=None,
    ),
    "API_QUOTA_EXCEEDED": AgentRecoverableError(
        original_error=API_QUOTA_EXCEEDED,
        recoverable=True,
        auto_fix_action="config check",  # 查看其他可用 API
        retry_after_seconds=None,  # 等待配额重置（通常次日）
    ),
    "NETWORK_ERROR": AgentRecoverableError(
        original_error=NETWORK_ERROR,
        recoverable=True,
        auto_fix_action=None,  # 等待后重试
        retry_after_seconds=5,  # 建议 5 秒后重试
    ),
    "INVALID_API_KEY": AgentRecoverableError(
        original_error=INVALID_API_KEY,
        recoverable=True,
        auto_fix_action="config setup",
        retry_after_seconds=None,
    ),
}


def get_agent_error(code: str) -> Optional[AgentRecoverableError]:
    """根据错误码获取 Agent 可理解的错误信息"""
    return ERROR_RECOVERY_MAP.get(code)


def make_agent_response_error(error: GeocodeError, command: str) -> dict:
    """生成 Agent 友好的错误响应"""
    agent_error = get_agent_error(error.code)

    if agent_error:
        error_dict = agent_error.to_agent_error()
    else:
        # 未知错误，默认不可恢复
        error_dict = {
            "code": error.code,
            "message": error.message,
            "suggestion": error.suggestion,
            "recoverable": False,
            "auto_fix_action": None,
        }

    return {
        "command": command,
        "status": "error",
        "error": error_dict,
    }


def get_all_error_definitions() -> dict:
    """获取所有错误码定义（供 API 端点返回）"""
    return {
        code: err.to_dict()
        for code, err in ERROR_RECOVERY_MAP.items()
    }


# ── Agent 错误处理流程说明 ───────────────────────────────────────────

ERROR_HANDLING_PROTOCOL = """
Agent 错误处理流程:

1. 解析响应中的 error.code
2. 检查 error.recoverable 字段
3. 若 recoverable=true:
   a. 如果有 auto_fix_action，执行该命令
   b. 如果有 retry_after_seconds，等待指定秒数后重试
   c. 根据 suggestion 提示用户或自动执行
   d. 重试原命令
4. 若 recoverable=false:
   a. 向用户报告 error.message
   b. 提示 error.suggestion
   c. 请求用户提供必要信息（如正确的文件路径）

示例:
响应: {
  "error": {
    "code": "NO_API_KEY",
    "recoverable": true,
    "auto_fix_action": "config setup"
  }
}

Agent 行动:
1. 执行: yaelocus config setup
2. 用户配置 API Key
3. 重试原命令
"""

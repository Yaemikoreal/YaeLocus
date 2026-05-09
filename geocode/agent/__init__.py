"""
Agent 集成模块

提供 AI Agent（openclaw、opencode、claude code）友好的接口层。

核心功能:
- JSON Schema 定义（结构化输出格式）
- 错误恢复映射（自动修复路径）
- 统一响应结构

使用示例:
    from geocode.agent import AgentResponse, AgentError, get_schema

    # 获取命令 Schema
    schema = get_schema("geocode_batch")

    # 创建响应
    response = AgentResponse(
        command="geocode_single",
        status=CommandStatus.SUCCESS,
        results=[{"longitude": 116.4, "latitude": 39.9}]
    )

    # 创建错误响应
    error = AgentError(
        code="NO_API_KEY",
        message="未配置 API 密钥",
        suggestion="运行 config setup",
        recoverable=True,
        auto_fix_action="config setup"
    )
"""

from .errors import (
    ERROR_RECOVERY_MAP,
    AgentRecoverableError,
    get_agent_error,
    get_all_error_definitions,
    make_agent_response_error,
)
from .schema import (
    SCHEMA_REGISTRY,
    AgentError,
    AgentResponse,
    CommandStatus,
    get_all_schemas,
    get_schema,
    validate_response,
)

__all__ = [
    # Schema
    "CommandStatus",
    "AgentError",
    "AgentResponse",
    "get_schema",
    "get_all_schemas",
    "validate_response",
    "SCHEMA_REGISTRY",
    # Errors
    "AgentRecoverableError",
    "get_agent_error",
    "make_agent_response_error",
    "get_all_error_definitions",
    "ERROR_RECOVERY_MAP",
]

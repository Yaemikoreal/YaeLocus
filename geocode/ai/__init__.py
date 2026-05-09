"""
AI 集成模块

提供统一的大模型 API 客户端，支持多个国内 AI 供应商：
- DeepSeek
- 通义千问 (Qwen)
- 智谱 (GLM)
- Kimi (Moonshot)
"""

from .client import AIClient
from .providers import ProviderConfig, BUILTIN_PROVIDERS, get_provider
from .prompts import ROUTE_ANALYSIS_PROMPT, ROUTE_COMPARISON_PROMPT

__all__ = [
    "AIClient",
    "ProviderConfig",
    "BUILTIN_PROVIDERS",
    "get_provider",
    "ROUTE_ANALYSIS_PROMPT",
    "ROUTE_COMPARISON_PROMPT",
]

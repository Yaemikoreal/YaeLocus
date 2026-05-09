"""
AI 供应商配置模块

定义支持的 AI 供应商及其 API 接入信息。
所有供应商兼容 OpenAI Chat Completion 格式。
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProviderConfig:
    """AI 供应商配置"""
    name: str
    display_name: str
    base_url: str
    default_model: str
    api_key_env: str
    api_key: str = ""
    available_models: List[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


# 内置供应商列表
BUILTIN_PROVIDERS = [
    ProviderConfig(
        name="deepseek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        available_models=["deepseek-chat", "deepseek-reasoner"],
    ),
    ProviderConfig(
        name="qwen",
        display_name="通义千问",
        base_url="https://dashscope.aliyuncs.com/compatible-mode",
        default_model="qwen-plus",
        api_key_env="QWEN_API_KEY",
        available_models=["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    ),
    ProviderConfig(
        name="glm",
        display_name="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        api_key_env="GLM_API_KEY",
        available_models=["glm-4-plus", "glm-4-air", "glm-4-flash"],
    ),
    ProviderConfig(
        name="moonshot",
        display_name="Kimi (Moonshot)",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        api_key_env="MOONSHOT_API_KEY",
        available_models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    ),
]


def get_provider(name: str) -> Optional[ProviderConfig]:
    """按名称查找供应商配置"""
    for p in BUILTIN_PROVIDERS:
        if p.name == name:
            return p
    return None


def get_available_providers() -> List[ProviderConfig]:
    """获取已配置 API Key 的供应商列表"""
    providers = []
    for p in BUILTIN_PROVIDERS:
        key = os.getenv(p.api_key_env, "")
        if key:
            p.api_key = key
            providers.append(p)
    return providers


def get_all_providers() -> List[ProviderConfig]:
    """获取所有供应商并加载环境变量中的 API Key"""
    result = []
    for p in BUILTIN_PROVIDERS:
        p.api_key = os.getenv(p.api_key_env, "")
        result.append(p)
    return result

"""
统一 AI 客户端

支持多个国内 AI 供应商的 OpenAI 兼容 API。
使用 requests.Session 复用连接，延续项目现有模式。
"""

import json
import os
import time
from typing import Dict, List, Optional, Iterator

import requests

from .providers import ProviderConfig, get_provider, get_available_providers


class AIClient:
    """统一的 AI API 客户端

    支持 DeepSeek、通义千问、智谱 GLM、Kimi 等 OpenAI 兼容 API。

    Usage:
        client = AIClient(provider="deepseek")
        response = client.chat([
            {"role": "user", "content": "Hello"}
        ])
        print(response["choices"][0]["message"]["content"])
    """

    def __init__(
        self,
        provider: str = "deepseek",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        self.provider_name = provider
        self.timeout = timeout
        self._session = requests.Session()

        # 加载供应商配置
        provider_config = get_provider(provider)
        if not provider_config and not base_url:
            available = [p.name for p in get_available_providers()]
            raise ValueError(
                f"不支持的供应商: '{provider}'。可用供应商: {available}"
            )

        # 优先使用传入参数，其次环境变量，最后默认值
        self.base_url = (base_url or provider_config.base_url).rstrip("/")
        self.api_key = api_key or os.getenv(provider_config.api_key_env, "")
        self.model = model or provider_config.default_model

        if not self.api_key:
            key_env = provider_config.api_key_env
            raise ValueError(
                f"未配置 {provider_config.display_name} API Key。"
                f"请设置环境变量 {key_env} 或在 .env 文件中配置。"
            )

        # 设置 HTTP 头部
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def chat(
        self,
        messages: List[Dict],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict:
        """调用 AI Chat Completion API

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式输出
            temperature: 温度参数 (0-2)
            max_tokens: 最大输出 token 数
            **kwargs: 其他 API 参数

        Returns:
            API 响应字典
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        try:
            resp = self._session.post(
                self.chat_url,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise ConnectionError(f"AI API 请求超时 (>{self.timeout}s)")
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            if status == 401:
                raise PermissionError(
                    f"AI API 认证失败，请检查 API Key 是否正确"
                )
            elif status == 429:
                raise ConnectionError(
                    f"AI API 请求过于频繁，请稍后重试"
                )
            else:
                raise ConnectionError(
                    f"AI API 请求失败 (HTTP {status}): {body}"
                )

    def chat_with_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """便捷方法：使用 system + user 提示词调用 AI

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            AI 回复文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"].strip()

    def simple_chat(self, message: str, **kwargs) -> str:
        """最简单调用：只传用户消息

        Args:
            message: 用户消息
            **kwargs: 其他参数透传 chat()

        Returns:
            AI 回复文本
        """
        messages = [{"role": "user", "content": message}]
        resp = self.chat(messages=messages, **kwargs)
        return resp["choices"][0]["message"]["content"].strip()

    def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """流式调用 AI Chat Completion API，逐 token 产出内容

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            **kwargs: 其他 API 参数

        Yields:
            每段 token 文本
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        try:
            resp = self._session.post(
                self.chat_url,
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            yielded_any = False
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yielded_any = True
                        yield content
                except json.JSONDecodeError:
                    continue

            if not yielded_any:
                import sys as _sys
                _sys.stderr.write(
                    "[AIClient] WARN: 流式响应未返回任何内容，"
                    "可能是模型名无效或 API 返回了非 SSE 格式。"
                    "请检查 AI_PROVIDER/AI_MODEL 配置。\n"
                )

        except requests.Timeout:
            raise ConnectionError(f"AI API 流式请求超时 (>{self.timeout}s)")
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            if status == 401:
                raise PermissionError(f"AI API 认证失败，请检查 API Key")
            elif status == 429:
                raise ConnectionError(f"AI API 请求过于频繁")
            else:
                raise ConnectionError(f"AI API 请求失败 (HTTP {status}): {body}")

    def close(self):
        """关闭 HTTP 会话"""
        self._session.close()

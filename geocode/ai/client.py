"""
统一 AI 客户端

支持多个国内 AI 供应商的 OpenAI 兼容 API。
使用 requests.Session 复用连接，延续项目现有模式。
"""

import json
import logging
import os
import time
from typing import Dict, Iterator, List, Optional

import requests

from .providers import get_available_providers, get_provider

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    def __init__(self, message: str, code: str = "unknown", provider: str = ""):
        super().__init__(message)
        self.code = code
        self.provider = provider


class AIAuthError(AIClientError):
    def __init__(self, message: str = "AI API 认证失败，请检查 API Key"):
        super().__init__(message, code="auth_error")


class AIRateLimitError(AIClientError):
    def __init__(self, message: str = "AI API 请求过于频繁，请稍后重试"):
        super().__init__(message, code="rate_limit")


class AINetworkError(AIClientError):
    def __init__(self, message: str = "AI API 网络错误"):
        super().__init__(message, code="network_error")


class AITimeoutError(AIClientError):
    def __init__(self, message: str = "AI API 请求超时"):
        super().__init__(message, code="timeout")


class AIResponseError(AIClientError):
    def __init__(self, message: str = "AI API 响应格式异常"):
        super().__init__(message, code="response_error")


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

    CONNECT_TIMEOUT = 10
    READ_TIMEOUT_DEFAULT = 120
    STREAM_CHUNK_TIMEOUT = 30

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

        provider_config = get_provider(provider)
        if not provider_config and not base_url:
            available = [p.name for p in get_available_providers()]
            raise ValueError(
                f"不支持的供应商: '{provider}'。可用供应商: {available}"
            )

        self.base_url = (base_url or (provider_config.base_url if provider_config else "")).rstrip("/")
        api_key_env = provider_config.api_key_env if provider_config else ""
        self.api_key = api_key or os.getenv(api_key_env, "")
        self.model = model or (provider_config.default_model if provider_config else "unknown")

        if not self.api_key:
            display_name = provider_config.display_name if provider_config else provider
            raise ValueError(
                f"未配置 {display_name} API Key。"
                f"请设置环境变量 {api_key_env} 或在 .env 文件中配置。"
            )

        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    @staticmethod
    def _extract_content(resp: Dict) -> str:
        try:
            return resp["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            logger.warning("AI 响应缺少 choices[0].message.content: %s", json.dumps(resp, ensure_ascii=False)[:200])
            raise AIResponseError(
                f"AI 返回了意外的响应格式。"
                f"原始响应: {json.dumps(resp, ensure_ascii=False)[:200]}"
            )

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
                timeout=(self.CONNECT_TIMEOUT, self.timeout),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise AITimeoutError(f"AI API 请求超时 (>{self.timeout}s)")
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            if status == 401:
                raise AIAuthError()
            elif status == 429:
                raise AIRateLimitError()
            else:
                raise AINetworkError(f"AI API 请求失败 (HTTP {status}): {body}")
        except requests.ConnectionError:
            raise AINetworkError("AI API 网络连接失败，请检查网络或代理设置")

    def chat_with_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            resp = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._extract_content(resp)
        except AIClientError:
            raise
        except Exception as e:
            raise AIClientError(f"chat_with_prompt 调用失败: {e}", code="unknown")

    def simple_chat(self, message: str, **kwargs) -> str:
        try:
            messages = [{"role": "user", "content": message}]
            resp = self.chat(messages=messages, **kwargs)
            return self._extract_content(resp)
        except AIClientError:
            raise
        except Exception as e:
            raise AIClientError(f"simple_chat 调用失败: {e}", code="unknown")

    def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens
            payload.update(kwargs)

            resp = self._session.post(
                self.chat_url,
                json=payload,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT_DEFAULT),
                stream=True,
            )
            resp.raise_for_status()

            yielded_any = False
            chunk_count = 0
            last_time = time.time()

            for line in resp.iter_lines():
                now = time.time()
                if now - last_time > self.STREAM_CHUNK_TIMEOUT:
                    logger.warning("流式响应超过 %ds 无数据，视为超时", self.STREAM_CHUNK_TIMEOUT)
                    break
                last_time = now

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
                        chunk_count += 1
                        yield content
                except json.JSONDecodeError:
                    chunk_count += 1
                    logger.debug("SSE chunk JSON 解析失败 (第%d个chunk): %s", chunk_count, data_str[:100])
                    continue

            if not yielded_any:
                logger.warning(
                    "流式响应未返回任何内容 (共 %d 个chunk)。"
                    "可能是模型名无效或 API 返回了非 SSE 格式。"
                    "请检查 AI_PROVIDER/AI_MODEL 配置。",
                    chunk_count,
                )

        except requests.Timeout:
            raise AITimeoutError("AI API 流式请求超时")
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            if status == 401:
                raise AIAuthError()
            elif status == 429:
                raise AIRateLimitError()
            else:
                raise AINetworkError(f"AI API 请求失败 (HTTP {status}): {body}")
        except requests.ConnectionError:
            raise AINetworkError("AI API 网络连接失败，请检查网络或代理设置")
        except AIClientError:
            raise
        except Exception as e:
            raise AIClientError(f"流式请求异常: {e}", code="unknown")

    def close(self):
        self._session.close()

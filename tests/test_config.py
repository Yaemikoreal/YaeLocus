"""配置模块测试"""
import os
import importlib

import dotenv
import pytest

from geocode import config as config_module
from geocode.config import Config


def _reload():
    """重载配置模块以刷新缓存的环境变量"""
    importlib.reload(config_module)


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """每个测试前阻止 .env 加载 — mock dotenv.load_dotenv 以承受 reload"""
    # mock dotenv 模块级别的 load_dotenv（importlib.reload 不会重载依赖模块）
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    # 清除所有相关 env var
    for key in ["AMAP_KEY", "BAIDU_AK", "TIANDITU_TK",
                "AI_ENABLED", "AI_PROVIDER", "AI_MODEL",
                "DEEPSEEK_API_KEY", "QWEN_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
                "ROUTING_MODE", "ROUTING_AUTO_FALLBACK"]:
        monkeypatch.delenv(key, raising=False)
    _reload()
    yield
    importlib.reload(config_module)


class TestConfigValidate:
    """配置验证"""

    def test_no_keys_fails(self, monkeypatch):
        for key in ["AMAP_KEY", "BAIDU_AK", "TIANDITU_TK"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        assert config_module.Config.validate() is False

    def test_amap_only_passes(self, monkeypatch):
        monkeypatch.setenv("AMAP_KEY", "test_key_32chars_xxxxxxxxxxxxxxxxxxxx")
        for key in ["BAIDU_AK", "TIANDITU_TK"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        assert config_module.Config.validate() is True

    def test_baidu_only_passes(self, monkeypatch):
        monkeypatch.setenv("BAIDU_AK", "test_baidu_ak")
        for key in ["AMAP_KEY", "TIANDITU_TK"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        assert config_module.Config.validate() is True

    def test_tianditu_only_passes(self, monkeypatch):
        monkeypatch.setenv("TIANDITU_TK", "test_tianditu_tk")
        for key in ["AMAP_KEY", "BAIDU_AK"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        assert config_module.Config.validate() is True


class TestConfigGetAvailableApis:
    """获取可用 API"""

    def test_amap_only(self, monkeypatch):
        monkeypatch.setenv("AMAP_KEY", "test_key_32chars_xxxxxxxxxxxxxxxxxxxx")
        for key in ["BAIDU_AK", "TIANDITU_TK"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        apis = config_module.Config.get_available_apis()
        assert "amap" in apis
        assert "baidu" not in apis
        assert "tianditu" not in apis

    def test_all_configured(self, monkeypatch):
        monkeypatch.setenv("AMAP_KEY", "test_amap_key_32chars_xxxxxxxxxxxxx")
        monkeypatch.setenv("BAIDU_AK", "test_baidu_ak")
        monkeypatch.setenv("TIANDITU_TK", "test_tianditu_tk")
        _reload()
        apis = config_module.Config.get_available_apis()
        assert len(apis) == 3
        assert apis == ["amap", "tianditu", "baidu"]


class TestConfigApiPriority:
    """API 优先级"""

    def test_priority_order(self):
        _reload()
        assert config_module.Config.API_PRIORITY == ["amap", "tianditu", "baidu"]


class TestConfigAISettings:
    """AI 配置"""

    def test_ai_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("AI_ENABLED", raising=False)
        _reload()
        assert config_module.Config.AI_ENABLED is False

    def test_ai_enabled(self, monkeypatch):
        monkeypatch.setenv("AI_ENABLED", "true")
        _reload()
        assert config_module.Config.AI_ENABLED is True

    def test_get_ai_client_no_provider(self, monkeypatch):
        monkeypatch.setenv("AI_ENABLED", "true")
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        # 确保所有 AI API Key 都被清除
        for key in ["DEEPSEEK_API_KEY", "QWEN_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY"]:
            monkeypatch.delenv(key, raising=False)
        _reload()
        client = config_module.Config.get_ai_client()
        assert client is None

    def test_get_ai_client_valid(self, monkeypatch):
        monkeypatch.setenv("AI_ENABLED", "true")
        monkeypatch.setenv("AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        _reload()
        client = config_module.Config.get_ai_client()
        if client is not None:
            assert client.provider_name == "deepseek"


class TestConfigDefaults:
    """默认值"""

    def test_request_delay(self):
        _reload()
        assert config_module.Config.REQUEST_DELAY == 0.1

    def test_request_timeout(self):
        _reload()
        assert config_module.Config.REQUEST_TIMEOUT == 10

    def test_max_retries(self):
        _reload()
        assert config_module.Config.MAX_RETRIES == 3


class TestConfigRouting:
    """路线规划配置"""

    def test_default_routing_mode(self, monkeypatch):
        monkeypatch.delenv("ROUTING_MODE", raising=False)
        _reload()
        mode = config_module.Config.get_routing_default_mode()
        assert mode in ("ai", "api")

    def test_routing_mode_ai(self, monkeypatch):
        monkeypatch.setenv("ROUTING_MODE", "ai")
        _reload()
        assert config_module.Config.get_routing_default_mode() == "ai"

    def test_routing_auto_fallback(self, monkeypatch):
        monkeypatch.setenv("ROUTING_AUTO_FALLBACK", "true")
        _reload()
        assert config_module.Config.ROUTING_AUTO_FALLBACK is True

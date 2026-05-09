"""共享测试fixtures"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure geocode package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    """临时目录，测试后自动清理"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_cache_file(temp_dir):
    """临时缓存数据库路径"""
    return temp_dir / "test_geocache.db"


@pytest.fixture
def clean_env(monkeypatch):
    """清除相关环境变量，提供干净配置环境"""
    for key in ["AMAP_KEY", "BAIDU_AK", "TIANDITU_TK",
                "AI_ENABLED", "AI_PROVIDER", "AI_MODEL",
                "DEEPSEEK_API_KEY", "QWEN_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
                "ROUTING_MODE", "ROUTING_AUTO_FALLBACK"]:
        monkeypatch.delenv(key, raising=False)
    # 重载配置
    from geocode import config
    import importlib
    importlib.reload(config)
    yield
    importlib.reload(config)


# 已知坐标测试向量 (WGS-84 <-> GCJ-02)
# 来源: 公开的坐标转换参考数据
KNOWN_CONVERSIONS = [
    # (wgs_lat, wgs_lon, gcj_lat, gcj_lon, 描述)
    (39.9042, 116.4074, 39.90569, 116.41355, "北京天安门"),
    (31.2304, 121.4737, 31.23228, 121.48024, "上海外滩"),
    (22.5431, 114.0579, 22.54474, 114.06457, "深圳福田"),
]

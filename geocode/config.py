"""
配置管理模块

从 .env 文件加载配置，支持环境变量覆盖
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

# 获取项目根目录
PROJECT_DIR = Path(__file__).parent.parent.resolve()

# 加载 .env 文件
ENV_FILE = PROJECT_DIR / ".env"
load_dotenv(ENV_FILE)


@dataclass
class APIConfigItem:
    """单个API配置"""
    name: str
    key: str
    url: str
    daily_limit: int
    coordinate_system: str

    @property
    def is_available(self) -> bool:
        return bool(self.key)


class Config:
    """全局配置类"""

    # API密钥
    AMAP_KEY: str = os.getenv("AMAP_KEY", "")
    BAIDU_AK: str = os.getenv("BAIDU_AK", "")
    TIANDITU_TK: str = os.getenv("TIANDITU_TK", "")

    # API端点
    AMAP_URL: str = "https://restapi.amap.com/v3/geocode/geo"
    BAIDU_URL: str = "https://api.map.baidu.com/geocoding/v3/"
    TIANDITU_URL: str = "http://api.tianditu.gov.cn/geocoder"

    # 请求配置
    REQUEST_DELAY: float = 0.1  # 请求间隔(秒)
    REQUEST_TIMEOUT: int = 10  # 超时时间(秒)
    MAX_RETRIES: int = 1  # 最大重试次数

    # API优先级顺序
    API_PRIORITY: List[str] = ["amap", "tianditu", "baidu"]

    # API配额(次/日)
    API_DAILY_LIMITS = {
        "amap": 5000,
        "tianditu": 10000,
        "baidu": 6000
    }

    # 坐标系
    COORDINATE_SYSTEMS = {
        "amap": "GCJ-02",
        "tianditu": "CGCS2000",
        "baidu": "BD-09"
    }

    @classmethod
    def get_api_config(cls, api_name: str) -> Optional[APIConfigItem]:
        """获取指定API的配置"""
        configs = {
            "amap": APIConfigItem(
                name="amap",
                key=cls.AMAP_KEY,
                url=cls.AMAP_URL,
                daily_limit=cls.API_DAILY_LIMITS["amap"],
                coordinate_system=cls.COORDINATE_SYSTEMS["amap"]
            ),
            "tianditu": APIConfigItem(
                name="tianditu",
                key=cls.TIANDITU_TK,
                url=cls.TIANDITU_URL,
                daily_limit=cls.API_DAILY_LIMITS["tianditu"],
                coordinate_system=cls.COORDINATE_SYSTEMS["tianditu"]
            ),
            "baidu": APIConfigItem(
                name="baidu",
                key=cls.BAIDU_AK,
                url=cls.BAIDU_URL,
                daily_limit=cls.API_DAILY_LIMITS["baidu"],
                coordinate_system=cls.COORDINATE_SYSTEMS["baidu"]
            )
        }
        return configs.get(api_name)

    @classmethod
    def get_available_apis(cls) -> List[str]:
        """获取可用的API列表"""
        available = []
        for api_name in cls.API_PRIORITY:
            config = cls.get_api_config(api_name)
            if config and config.is_available:
                available.append(api_name)
        return available

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否有效"""
        return bool(cls.AMAP_KEY or cls.BAIDU_AK or cls.TIANDITU_TK)

    @classmethod
    def get_project_dir(cls) -> Path:
        """获取项目根目录"""
        return PROJECT_DIR


# 导出常用配置
__all__ = [
    "Config",
    "PROJECT_DIR",
]
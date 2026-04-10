"""
YaeLocus - 地址转经纬度工具

支持高德、百度、天地图三个API的智能轮换

Author: Yaemikoreal
Project: https://github.com/Yaemikoreal/YaeLocus

Usage:
    from geocode import Geocoder, CacheManager, APILogger

    # 初始化
    cache = CacheManager()
    logger = APILogger()
    geocoder = Geocoder(cache, logger)

    # 单个地址转换
    result = geocoder.geocode("北京市朝阳区建国路88号")

    # 批量转换
    results = geocoder.batch_geocode(["地址1", "地址2"])
"""

from .cache import CacheManager
from .config import Config
from .coords import gcj02_to_wgs84, bd09_to_wgs84, bd09_to_gcj02
from .errors import GeocodeError, ConfigError, APIError, FileError, NetworkError
from .geocoder import Geocoder
from .logger import APILogger
from .map_visualizer import create_map
from .models import GeocodeResult, APILog, APIConfig

__version__ = "1.2.0"
__all__ = [
    "Geocoder",
    "CacheManager",
    "APILogger",
    "create_map",
    "Config",
    "GeocodeResult",
    "APILog",
    "APIConfig",
    "gcj02_to_wgs84",
    "bd09_to_wgs84",
    "bd09_to_gcj02",
    "GeocodeError",
    "ConfigError",
    "APIError",
    "FileError",
    "NetworkError",
]
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

    # 逆地理编码
    result = geocoder.reverse_geocode(39.9, 116.4)

    # 批量转换
    results = geocoder.batch_geocode(["地址1", "地址2"])
"""

from .cache import CacheManager
from .config import Config
from .coords import bd09_to_gcj02, bd09_to_wgs84, gcj02_to_wgs84, haversine_km, wgs84_to_gcj02
from .errors import APIError, ConfigError, FileError, GeocodeError, NetworkError
from .geocoder import Geocoder
from .logger import APILogger
from .map_visualizer import create_map, create_route_map
from .models import APIConfig, APILog, GeocodeResult
from .optimizer import ItineraryOptimizer

# 预处理和验证模块
from .preprocessing import AddressNormalizer, AddressSplitter, InvalidAddressFilter
from .validation import ConfidenceScore, ConfidenceValidator, CrossProvinceChecker

# 新模块 - 仅当可用时导入
try:
    from .ai import AIClient, ProviderConfig  # noqa: F401
except ImportError:
    pass
try:
    from .routing import DirectionsClient, RoutePlanner, RouteResult, TravelMode  # noqa: F401
except ImportError:
    pass
try:
    from .api import create_api_app, run_api_server  # noqa: F401
except ImportError:
    pass  # web extras 未安装时跳过

# Agent 集成模块 - 供 AI Agent 使用
from .agent import (
    AgentError,
    AgentResponse,
    CommandStatus,
    get_agent_error,
    get_all_error_definitions,
    get_all_schemas,
    get_schema,
    make_agent_response_error,
    validate_response,
)

__version__ = "1.6.0"
__all__ = [
    "Geocoder",
    "CacheManager",
    "APILogger",
    "create_map",
    "create_route_map",
    "Config",
    "GeocodeResult",
    "APILog",
    "APIConfig",
    "gcj02_to_wgs84",
    "bd09_to_wgs84",
    "bd09_to_gcj02",
    "wgs84_to_gcj02",
    "haversine_km",
    "GeocodeError",
    "ConfigError",
    "APIError",
    "FileError",
    "NetworkError",
    "AIClient",
    "ProviderConfig",
    "RoutePlanner",
    "RouteResult",
    "DirectionsClient",
    "TravelMode",
    "ItineraryOptimizer",
    # 新增导出
    "InvalidAddressFilter",
    "AddressNormalizer",
    "AddressSplitter",
    "ConfidenceValidator",
    "ConfidenceScore",
    "CrossProvinceChecker",
    # Agent 集成
    "AgentResponse",
    "AgentError",
    "CommandStatus",
    "get_schema",
    "get_all_schemas",
    "validate_response",
    "get_agent_error",
    "make_agent_response_error",
    "get_all_error_definitions",
]

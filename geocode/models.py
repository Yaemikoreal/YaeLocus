"""
数据模型定义
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class GeocodeResult:
    """地理编码结果"""
    latitude: float
    longitude: float
    original_address: str
    formatted_address: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    source: str = ""  # amap, tianditu, baidu
    coordinate_system: str = ""  # GCJ-02, BD-09, CGCS2000
    original_lat: Optional[float] = None
    original_lon: Optional[float] = None
    success: bool = True

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class APILog:
    """API调用日志"""
    timestamp: str
    address: str
    api_name: str
    status: str  # success, failed, error
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    formatted_address: Optional[str] = None
    time_cost: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class APIConfig:
    """API配置"""
    name: str
    key: str
    url: str
    daily_limit: int
    coordinate_system: str
    priority: int = 1

    @property
    def is_configured(self) -> bool:
        """是否已配置"""
        return bool(self.key)
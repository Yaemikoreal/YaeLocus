"""
行程优化数据结构
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class LocationStat:
    """单位置统计数据"""
    address: str
    lat: float
    lon: float
    frequency: int = 1
    original_addresses: List[str] = field(default_factory=list)
    density_score: float = 0.0
    cluster_id: int = -1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LocationCluster:
    """位置聚类组"""
    cluster_id: int
    center_lat: float
    center_lon: float
    locations: List[LocationStat] = field(default_factory=list)
    total_frequency: int = 0
    radius_km: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["center"] = f"{self.center_lat:.4f},{self.center_lon:.4f}"
        d["location_count"] = len(self.locations)
        return d


@dataclass
class RecommendedRoute:
    """推荐路线方案"""
    name: str
    description: str
    waypoints: List[Dict]
    total_distance_km: float = 0.0
    total_locations: int = 0
    total_frequency: int = 0
    coverage_rate: float = 0.0
    strategy: str = ""
    priority_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

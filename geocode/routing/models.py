"""
路线规划数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
from enum import Enum


class TravelMode(str, Enum):
    """出行方式"""
    DRIVING = "driving"
    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"

    @property
    def display_name(self) -> str:
        names = {
            "driving": "驾车",
            "walking": "步行",
            "bicycling": "骑行",
            "transit": "公共交通",
        }
        return names.get(self.value, self.value)

    @classmethod
    def from_str(cls, s: str) -> "TravelMode":
        for m in cls:
            if m.value == s:
                return m
        raise ValueError(f"不支持的出行方式: {s}，可选: {[m.value for m in cls]}")


@dataclass
class RoutePoint:
    """路线途经点"""
    lat: float
    lon: float
    address: str = ""
    order: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)


@dataclass
class RouteSegment:
    """路线分段"""
    mode: str
    distance_meters: float
    duration_seconds: float
    instruction: str = ""
    polyline: List[Tuple[float, float]] = field(default_factory=list)
    traffic_info: str = ""
    road_name: str = ""

    @property
    def distance_km(self) -> float:
        return self.distance_meters / 1000

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60

    def to_dict(self) -> dict:
        d = asdict(self)
        d["distance_km"] = round(self.distance_km, 2)
        d["duration_minutes"] = round(self.duration_minutes, 1)
        return d


@dataclass
class RouteResult:
    """完整路线结果"""
    mode: str
    origin: RoutePoint
    destination: RoutePoint
    total_distance_meters: float
    total_duration_seconds: float
    segments: List[RouteSegment] = field(default_factory=list)
    waypoints: List[RoutePoint] = field(default_factory=list)
    alternatives: List["RouteResult"] = field(default_factory=list)
    ai_summary: str = ""
    toll_meters: float = 0.0
    toll_fee: str = ""
    provider: str = ""

    @property
    def total_distance_km(self) -> float:
        return self.total_distance_meters / 1000

    @property
    def total_duration_minutes(self) -> float:
        return self.total_duration_seconds / 60

    @property
    def total_duration_text(self) -> str:
        h = int(self.total_duration_minutes // 60)
        m = int(self.total_duration_minutes % 60)
        if h > 0:
            return f"{h}小时{m}分钟"
        return f"{m}分钟"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_distance_km"] = round(self.total_distance_km, 2)
        d["total_duration_minutes"] = round(self.total_duration_minutes, 1)
        d["total_duration_text"] = self.total_duration_text
        d["mode_display"] = TravelMode(self.mode).display_name
        return d

    def to_csv_row(self) -> dict:
        return {
            "出行方式": TravelMode(self.mode).display_name,
            "起点": self.origin.address,
            "起点经度": self.origin.lon,
            "起点纬度": self.origin.lat,
            "终点": self.destination.address,
            "终点经度": self.destination.lon,
            "终点纬度": self.destination.lat,
            "总距离(公里)": round(self.total_distance_km, 2),
            "预计时间": self.total_duration_text,
            "分段数": len(self.segments),
            "数据来源": self.provider,
        }

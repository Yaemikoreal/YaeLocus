"""
AI 优先路线规划器

AI 模式（默认，零外部 API 成本）或付费 API 模式。
RoutePlanner 自动选择估算引擎，返回统一的 RouteResult。
"""

from typing import Dict, List, Optional, Tuple

from geocode.ai import AIClient
from geocode.ai.prompts import (
    MULTI_POINT_ANALYSIS_PROMPT,
    ROUTE_ANALYSIS_PROMPT,
    ROUTE_COMPARISON_PROMPT,
)
from geocode.config import Config
from .ai_engine import AIDirectionEngine
from .directions import DirectionsClient
from .models import TravelMode, RoutePoint, RouteResult

# 中国主要城市名称列表（用于地址识别）
_MAJOR_CITIES = [
    "北京", "上海", "广州", "深圳", "天津", "重庆", "杭州", "南京", "武汉",
    "成都", "西安", "郑州", "沈阳", "青岛", "宁波", "东莞", "佛山", "苏州",
    "长沙", "合肥", "大连", "福州", "厦门", "哈尔滨", "昆明", "贵阳", "南宁",
    "呼和浩特", "银川", "西宁", "兰州", "拉萨", "乌鲁木齐", "海口", "三亚",
    "秦皇岛", "淄博", "烟台", "潍坊", "济宁", "临沂", "洛阳", "襄阳", "宜昌",
    "柳州", "桂林", "珠海", "中山", "惠州", "温州", "绍兴", "嘉兴", "金华",
    "泉州", "漳州", "南昌", "九江", "太原", "大同", "唐山", "鞍山", "吉林",
    "大庆", "齐齐哈尔", "无锡", "常州", "徐州", "南通", "镇江", "扬州",
    "香港", "澳门", "台北",
]


class RoutePlanner:
    """路线规划器

    AI 模式为默认（零外部 API 成本），
    付费 API 模式仅在明确指定时启用。

    Usage:
        # AI 模式（默认）
        planner = RoutePlanner()
        result = planner.plan(
            points=[{"lat": 39.9, "lon": 116.4, "address": "北京"},
                    {"lat": 31.2, "lon": 121.5, "address": "上海"}],
        )

        # 付费 API 模式
        planner = RoutePlanner(directions_client=DirectionsClient("amap"))
        result = planner.plan(points=..., force_api=True)
    """

    def __init__(
        self,
        directions_client: Optional[DirectionsClient] = None,
        ai_client: Optional[AIClient] = None,
        prefer_ai: bool = True,
    ):
        """
        Args:
            directions_client: 付费 API 客户端（可选）
            ai_client: AI 客户端（可选，未提供时自动创建）
            prefer_ai: 是否优先使用 AI 模式
        """
        self.directions = directions_client
        self.ai = ai_client or Config.get_ai_client()
        self.ai_engine = AIDirectionEngine(self.ai) if self.ai else AIDirectionEngine()
        self.prefer_ai = prefer_ai

    def _should_use_ai(self, use_ai: Optional[bool], force_api: bool) -> bool:
        """决策是否使用 AI 模式"""
        if force_api:
            return False
        if use_ai is not None:
            return use_ai
        return self.prefer_ai

    def plan(
        self,
        points: List[Dict],
        mode: str = "driving",
        use_ai: Optional[bool] = None,
        force_api: bool = False,
    ) -> Optional[RouteResult]:
        """两点或多点路线规划

        Args:
            points: 途经点列表，每项含 lat/lon/address
                    至少 2 个点，第1个为起点，最后1个为终点
            mode: 出行方式 (driving/walking/bicycling/transit)
            use_ai: 是否使用 AI 模式（None=根据 prefer_ai 自动选择）
            force_api: 强制使用付费 API 模式

        Returns:
            RouteResult 或 None
        """
        if len(points) < 2:
            raise ValueError("至少需要 2 个点进行路线规划")

        TravelMode.from_str(mode)  # 验证出行方式

        origin = (points[0]["lat"], points[0]["lon"])
        destination = (points[-1]["lat"], points[-1]["lon"])
        origin_addr = points[0].get("address", "")
        dest_addr = points[-1].get("address", "")

        # 途经点
        waypoints_coords = None
        waypoint_addrs = None
        if len(points) > 2:
            waypoints_coords = [(p["lat"], p["lon"]) for p in points[1:-1]]
            waypoint_addrs = [p.get("address", "") for p in points[1:-1]]

        ai_mode = self._should_use_ai(use_ai, force_api)

        if ai_mode:
            return self._plan_with_ai(
                origin, destination, mode,
                waypoints_coords, origin_addr, dest_addr, waypoint_addrs,
                points,
            )

        # 非 AI 模式，检查 API 客户端
        if self.directions:
            return self._plan_with_api(
                origin, destination, mode,
                waypoints_coords, origin_addr, dest_addr, waypoint_addrs,
                points,
            )

        # 没有 API 客户端时使用纯 Haversine 估算（不调用 AI）
        from .ai_engine import AIDirectionEngine
        haversine_engine = AIDirectionEngine(ai_client=None)
        result = haversine_engine.estimate(
            origin=origin,
            destination=destination,
            mode=mode,
            waypoints=waypoints_coords,
            origin_address=origin_addr or self._extract_location_name(points[0]),
            destination_address=dest_addr or self._extract_location_name(points[-1]),
            waypoint_addresses=waypoint_addrs,
        )
        if result is None:
            return None
        # 填充地址信息
        result.origin = RoutePoint(
            lat=points[0]["lat"], lon=points[0]["lon"],
            address=points[0].get("address", ""), order=0,
        )
        result.destination = RoutePoint(
            lat=points[-1]["lat"], lon=points[-1]["lon"],
            address=points[-1].get("address", ""), order=len(points) - 1,
        )
        if len(points) > 2:
            result.waypoints = [
                RoutePoint(lat=p["lat"], lon=p["lon"], address=p.get("address", ""), order=i + 1)
                for i, p in enumerate(points[1:-1])
            ]
        return result

    def _plan_with_ai(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints_coords: Optional[List[Tuple[float, float]]],
        origin_addr: str,
        dest_addr: str,
        waypoint_addrs: Optional[List[str]],
        points: List[Dict],
    ) -> Optional[RouteResult]:
        """AI 模式规划路线"""
        result = self.ai_engine.estimate(
            origin=origin,
            destination=destination,
            mode=mode,
            waypoints=waypoints_coords,
            origin_address=origin_addr or self._extract_location_name(points[0]),
            destination_address=dest_addr or self._extract_location_name(points[-1]),
            waypoint_addresses=waypoint_addrs,
        )

        if result is None:
            return None

        # 填充地址信息
        result.origin = RoutePoint(
            lat=points[0]["lat"], lon=points[0]["lon"],
            address=points[0].get("address", ""), order=0,
        )
        result.destination = RoutePoint(
            lat=points[-1]["lat"], lon=points[-1]["lon"],
            address=points[-1].get("address", ""), order=len(points) - 1,
        )
        if len(points) > 2:
            result.waypoints = [
                RoutePoint(lat=p["lat"], lon=p["lon"], address=p.get("address", ""), order=i + 1)
                for i, p in enumerate(points[1:-1])
            ]

        return result

    def _plan_with_api(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints_coords: Optional[List[Tuple[float, float]]],
        origin_addr: str,
        dest_addr: str,
        waypoint_addrs: Optional[List[str]],
        points: List[Dict],
    ) -> Optional[RouteResult]:
        """付费 API 模式规划路线"""
        if not self.directions:
            raise ValueError(
                "付费 API 模式需要 DirectionsClient。\n"
                "请配置高德或百度 API 密钥，或使用 AI 模式（默认）。"
            )

        result = self.directions.get_directions(
            origin=origin,
            destination=destination,
            mode=mode,
            waypoints=waypoints_coords,
        )

        if result is None:
            return None

        # 填充地址信息
        result.origin = RoutePoint(
            lat=points[0]["lat"], lon=points[0]["lon"],
            address=points[0].get("address", ""), order=0,
        )
        result.destination = RoutePoint(
            lat=points[-1]["lat"], lon=points[-1]["lon"],
            address=points[-1].get("address", ""), order=len(points) - 1,
        )
        if len(points) > 2:
            result.waypoints = [
                RoutePoint(lat=p["lat"], lon=p["lon"], address=p.get("address", ""), order=i + 1)
                for i, p in enumerate(points[1:-1])
            ]

        # AI 增强分析（付费 API 模式下可选）
        if self.ai:
            result.ai_summary = self._enhance_with_ai(result)

        return result

    # ==================== 批量 & 比较 ====================

    def batch_plan_from_csv(
        self,
        csv_path: str,
        from_col: str = "起点",
        to_col: str = "终点",
        from_lat_col: str = "纬度",
        from_lon_col: str = "经度",
        to_lat_col: str = "终点纬度",
        to_lon_col: str = "终点经度",
        mode: str = "driving",
        use_ai: bool = True,
        force_api: bool = False,
    ) -> List[RouteResult]:
        """从 CSV 文件批量规划路线"""
        import pandas as pd

        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        results = []

        for _, row in df.iterrows():
            points = [
                {
                    "lat": row[from_lat_col],
                    "lon": row[from_lon_col],
                    "address": str(row.get(from_col, "")),
                },
                {
                    "lat": row[to_lat_col],
                    "lon": row[to_lon_col],
                    "address": str(row.get(to_col, "")),
                },
            ]
            result = self.plan(points, mode=mode, use_ai=use_ai, force_api=force_api)
            if result:
                results.append(result)

        return results

    def compare_modes(
        self,
        origin: Dict,
        destination: Dict,
        modes: List[str] = None,
        use_ai: bool = True,
        force_api: bool = False,
    ) -> List[RouteResult]:
        """比较多种出行方式"""
        if modes is None:
            modes = ["driving", "transit", "walking", "bicycling"]

        results = []
        points = [origin, destination]

        for mode in modes:
            try:
                result = self.plan(points, mode=mode, use_ai=use_ai, force_api=force_api)
                if result:
                    results.append(result)
            except Exception:
                continue

        return results

    # ==================== AI 增强（API 模式） ====================

    def _enhance_with_ai(self, result: RouteResult) -> str:
        """使用 AI 分析路线结果（仅用于付费 API 模式）"""
        if not self.ai:
            return ""

        segments_text = []
        for i, seg in enumerate(result.segments[:20]):
            segments_text.append(
                f"  第{i+1}段: {seg.instruction} "
                f"({seg.distance_km:.2f}km, {seg.duration_minutes:.0f}分钟)"
            )

        waypoints_text = "无"
        if result.waypoints:
            waypoints_text = " -> ".join(
                [f"{p.address}({p.order})" for p in result.waypoints]
            )

        prompt = ROUTE_ANALYSIS_PROMPT.format(
            origin=result.origin.address or f"({result.origin.lat}, {result.origin.lon})",
            destination=result.destination.address or f"({result.destination.lat}, {result.destination.lon})",
            mode_name=TravelMode(result.mode).display_name,
            distance=result.total_distance_km,
            duration=result.total_duration_minutes,
            waypoints_text=waypoints_text,
            segments_text="\n".join(segments_text) if segments_text else "  无详细分段信息",
        )

        try:
            return self.ai.chat_with_prompt(
                system_prompt="你是一个路线分析专家。请用简洁的中文回答。",
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=800,
            )
        except Exception as e:
            return f"[AI 分析失败: {e}]"

    # ==================== 地址识别 ====================

    @staticmethod
    def _extract_location_name(point: Dict) -> str:
        """从地址中提取位置名称

        优先提取已知的中国城市名，否则返回地址原文。
        """
        address = point.get("address", "")
        if not address:
            return ""

        for city in _MAJOR_CITIES:
            if city in address:
                return city
        return address.split("市")[0] if "市" in address else address.split("区")[0] if "区" in address else address

    # ==================== 资源管理 ====================

    def close(self):
        """关闭资源"""
        if self.directions:
            self.directions.close()
        if self.ai:
            self.ai.close()

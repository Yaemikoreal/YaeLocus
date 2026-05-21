"""
方向 API 客户端

调用高德/百度路径规划 API 获取实际道路路线。
复用项目已有的 API 密钥和 HTTP Session 模式。
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

from geocode.config import Config

from .models import RoutePoint, RouteResult, RouteSegment

logger = logging.getLogger(__name__)


class DirectionsClient:
    """路径规划 API 客户端

    支持高德和百度地图的驾车/步行/骑行/公交路径规划。

    Usage:
        client = DirectionsClient(provider="amap")
        result = client.get_directions(
            origin=(39.9, 116.4),
            destination=(31.2, 121.5),
            mode="driving"
        )
    """

    # 高德路径规划 API 端点
    AMAP_DIRECTION_URLS = {
        "driving": "https://restapi.amap.com/v3/direction/driving",
        "walking": "https://restapi.amap.com/v3/direction/walking",
        "bicycling": "https://restapi.amap.com/v3/direction/bicycling",
        "transit": "https://restapi.amap.com/v3/direction/transit/integrated",
    }

    # 百度路径规划 API 端点
    BAIDU_DIRECTION_URLS = {
        "driving": "https://api.map.baidu.com/direction/v2/driving",
        "walking": "https://api.map.baidu.com/direction/v2/walking",
        "riding": "https://api.map.baidu.com/direction/v2/riding",
        "transit": "https://api.map.baidu.com/direction/v2/transit",
    }

    # 出行方式映射（百度用 riding 而非 bicycling）
    BAIDU_MODE_MAP = {
        "bicycling": "riding",
    }

    def __init__(self, provider: str = "amap"):
        if provider not in ("amap", "baidu"):
            raise ValueError(f"不支持的路径规划供应商: {provider}，可选: amap, baidu")
        self.provider = provider
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._last_request_time = 0.0

    def _rate_limit(self):
        """请求限流，复用 Geocoder 的限流逻辑"""
        elapsed = time.time() - self._last_request_time
        if elapsed < Config.REQUEST_DELAY:
            time.sleep(Config.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get_amap_params(
        self, origin: Tuple[float, float], destination: Tuple[float, float],
        mode: str, waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict:
        """构建高德 API 请求参数"""
        params = {
            "key": Config.AMAP_KEY,
            "origin": f"{origin[1]},{origin[0]}",
            "destination": f"{destination[1]},{destination[0]}",
            "output": "JSON",
        }
        if mode == "driving":
            params["strategy"] = "0"  # 速度优先
            params["extensions"] = "all"  # 返回详细信息
        if waypoints:
            params["waypoints"] = ";".join(f"{p[1]},{p[0]}" for p in waypoints)
        return params

    def _get_baidu_params(
        self, origin: Tuple[float, float], destination: Tuple[float, float],
        mode: str, waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict:
        """构建百度 API 请求参数"""
        baidu_mode = self.BAIDU_MODE_MAP.get(mode, mode)
        params = {
            "ak": Config.BAIDU_AK,
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "output": "json",
        }
        if baidu_mode == "driving":
            params["tactics"] = "0"  # 速度优先
        if waypoints:
            params["waypoints"] = "|".join(f"{p[0]},{p[1]}" for p in waypoints)
        return params

    def _parse_amap_polyline(self, line_str: str) -> List[Tuple[float, float]]:
        """解析高德 polyline 字符串为坐标列表"""
        # 格式: "116.397,39.907;116.398,39.908;..."
        coords = []
        for point in line_str.split(";"):
            if not point.strip():
                continue
            parts = point.split(",")
            if len(parts) == 2:
                coords.append((float(parts[1]), float(parts[0])))  # (lat, lon)
        return coords

    def _parse_amap_route(self, data: Dict, mode: str) -> Optional[RouteResult]:
        """解析高德 API 响应"""
        if data.get("status") != "1" or not data.get("route"):
            logger.warning("高德 API 返回非成功状态: status=%s, info=%s", data.get("status"), data.get("info", ""))
            return None

        route = data["route"]
        paths = route.get("paths", [])
        if not paths:
            logger.info("高德 API 返回空路径列表")
            return None

        main_path = paths[0]
        segments = []
        for step in main_path.get("steps", []):
            segments.append(RouteSegment(
                mode=mode,
                distance_meters=float(step.get("distance", 0)),
                duration_seconds=float(step.get("duration", 0)),
                instruction=step.get("instruction", ""),
                polyline=self._parse_amap_polyline(step.get("polyline", "")),
                road_name=step.get("road", ""),
            ))

        result = RouteResult(
            mode=mode,
            origin=RoutePoint(lat=0, lon=0, address="", order=0),
            destination=RoutePoint(lat=0, lon=0, address="", order=0),
            total_distance_meters=float(main_path.get("distance", 0)),
            total_duration_seconds=float(main_path.get("duration", 0)),
            segments=segments,
            toll_meters=float(main_path.get("tolls", 0)),
            toll_fee=main_path.get("toll_distance", ""),
            provider="amap",
        )

        # 解析备选路线（最多 2 条）
        for alt_path in paths[1:3]:
            alt_segments = []
            for step in alt_path.get("steps", []):
                alt_segments.append(RouteSegment(
                    mode=mode,
                    distance_meters=float(step.get("distance", 0)),
                    duration_seconds=float(step.get("duration", 0)),
                    instruction=step.get("instruction", ""),
                    polyline=self._parse_amap_polyline(step.get("polyline", "")),
                ))
            result.alternatives.append(RouteResult(
                mode=mode,
                origin=RoutePoint(lat=0, lon=0, address="", order=0),
                destination=RoutePoint(lat=0, lon=0, address="", order=0),
                total_distance_meters=float(alt_path.get("distance", 0)),
                total_duration_seconds=float(alt_path.get("duration", 0)),
                segments=alt_segments,
                provider="amap",
            ))

        return result

    def _parse_baidu_polyline(self, line_str: str) -> List[Tuple[float, float]]:
        """解析百度 polyline 字符串为坐标列表"""
        # 百度使用以逗号分隔的经纬度对: "lng,lat;lng,lat;..."
        # 或使用 base64 编码的路线点串
        coords = []
        if not line_str:
            return coords
        if ";" in line_str:
            for point in line_str.split(";"):
                if not point.strip():
                    continue
                parts = point.split(",")
                if len(parts) == 2:
                    coords.append((float(parts[1]), float(parts[0])))
        return coords

    def _parse_baidu_route(self, data: Dict, mode: str) -> Optional[RouteResult]:
        """解析百度 API 响应"""
        if data.get("status") != 0:
            logger.warning("百度 API 返回非成功状态: status=%s, message=%s", data.get("status"), data.get("message", ""))
            return None

        result_data = data.get("result", {})
        routes = result_data.get("routes", [])
        if not routes:
            logger.info("百度 API 返回空路线列表")
            return None

        main_route = routes[0]
        baidu_mode = self.BAIDU_MODE_MAP.get(mode, mode)
        segments = []

        for step in main_route.get("steps", []):
            path_coords = []
            path_str = ""
            if baidu_mode == "driving":
                path_str = step.get("path", "")
                # 驾车路径的 instruction 在 step 的各个子路段中
                instr_parts = [s.get("instruction", "") for s in step.get("traffic_conditions", [])]
                instruction = "; ".join(filter(None, instr_parts)) or step.get("area_name", "")
            else:
                path_str = step.get("path", "")
                instruction = step.get("direction", "")

            path_coords = self._parse_baidu_polyline(path_str)
            segments.append(RouteSegment(
                mode=mode,
                distance_meters=float(step.get("distance", 0)),
                duration_seconds=float(step.get("duration", 0)),
                instruction=step.get("instruction", ""),
                polyline=path_coords,
            ))

        result = RouteResult(
            mode=mode,
            origin=RoutePoint(lat=0, lon=0, address="", order=0),
            destination=RoutePoint(lat=0, lon=0, address="", order=0),
            total_distance_meters=float(main_route.get("distance", 0)),
            total_duration_seconds=float(main_route.get("duration", 0)),
            segments=segments,
            provider="baidu",
        )

        return result

    def get_directions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
        waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> Optional[RouteResult]:
        """获取两点间路线规划

        Args:
            origin: 起点坐标 (lat, lon)
            destination: 终点坐标 (lat, lon)
            mode: 出行方式 (driving/walking/bicycling/transit)
            waypoints: 途经点坐标列表 [(lat, lon), ...]

        Returns:
            RouteResult 或 None（API 调用失败时）
        """
        self._rate_limit()

        if self.provider == "amap":
            params = self._get_amap_params(origin, destination, mode, waypoints)
            url = self.AMAP_DIRECTION_URLS.get(mode)
            if not url:
                raise ValueError(f"高德不支持 {mode} 出行方式")
        elif self.provider == "baidu":
            params = self._get_baidu_params(origin, destination, mode, waypoints)
            baidu_mode = self.BAIDU_MODE_MAP.get(mode, mode)
            url = self.BAIDU_DIRECTION_URLS.get(baidu_mode)
            if not url:
                raise ValueError(f"百度不支持 {mode} 出行方式")

        try:
            resp = self._session.get(url, params=params, timeout=Config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if self.provider == "amap":
                return self._parse_amap_route(data, mode)
            else:
                return self._parse_baidu_route(data, mode)
        except requests.RequestException as e:
            raise ConnectionError(f"路径规划 API 请求失败: {e}")

    def close(self):
        """关闭 HTTP 会话"""
        self._session.close()

"""
AI 路线估算引擎

纯 AI + Haversine 数学后备的路线估算，绝不调用付费方向 API。
AI 模式使用大模型的地理知识估算距离/时间/路线描述，
失败时自动降级到 Haversine 纯数学计算（零成本）。
"""

import json
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from geocode.ai import AIClient
from geocode.ai.prompts import ROUTE_ESTIMATION_PROMPT
from .models import RoutePoint, RouteResult, RouteSegment, TravelMode


class AIDirectionEngine:
    """AI 驱动的路线估算引擎

    不调用任何付费方向 API，使用 AI 地理知识 + Haversine 后备。

    Usage:
        engine = AIDirectionEngine(ai_client)
        result = engine.estimate(
            origin=(39.9, 116.4),
            destination=(31.2, 121.5),
            mode="driving",
            origin_address="北京",
            destination_address="上海",
        )
    """

    # 出行方式参考速度 (km/h) — 用于 Haversine 后备
    MODE_SPEEDS: Dict[str, float] = {
        "driving": 50.0,
        "transit": 25.0,
        "walking": 5.0,
        "bicycling": 15.0,
    }

    # 道路系数 (Haversine 直线距离 → 实际道路距离估算)
    MODE_ROAD_FACTORS: Dict[str, float] = {
        "driving": 1.4,
        "transit": 1.5,
        "walking": 1.0,
        "bicycling": 1.2,
    }

    def __init__(
        self,
        ai_client: Optional[AIClient] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ):
        """
        Args:
            ai_client: AI 客户端，为 None 时纯 Haversine 模式
            max_retries: AI 调用最大重试次数
            retry_delay: 重试基础延迟（秒），指数退避
        """
        self.ai = ai_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # ==================== 公开接口 ====================

    def estimate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
        waypoints: Optional[List[Tuple[float, float]]] = None,
        origin_address: str = "",
        destination_address: str = "",
        waypoint_addresses: Optional[List[str]] = None,
    ) -> RouteResult:
        """估算两点间路线

        Args:
            origin: 起点坐标 (lat, lon)
            destination: 终点坐标 (lat, lon)
            mode: 出行方式 (driving/walking/bicycling/transit)
            waypoints: 途经点坐标列表
            origin_address: 起点地址描述
            destination_address: 终点地址描述
            waypoint_addresses: 途经点地址描述列表

        Returns:
            始终返回有效的 RouteResult（AI 估算或 Haversine 后备）
        """
        # 1. 输入验证
        self._validate_coords(origin[0], origin[1], "起点")
        self._validate_coords(destination[0], destination[1], "终点")
        if waypoints:
            for i, wp in enumerate(waypoints):
                self._validate_coords(wp[0], wp[1], f"途经点 {i+1}")

        mode = mode.lower()
        if mode not in self.MODE_SPEEDS:
            mode = "driving"

        # 2. 尝试 AI 估算
        if self.ai:
            try:
                ai_data = self._estimate_with_ai(
                    origin, destination, mode,
                    waypoints or [],
                    origin_address, destination_address,
                    waypoint_addresses or [],
                )
                if ai_data and self._sanity_check(ai_data, origin, destination, waypoints):
                    return self._build_route_result(
                        ai_data, origin, destination, mode,
                        waypoints, origin_address, destination_address,
                        waypoint_addresses,
                    )
            except Exception:
                pass

        # 3. Haversine 后备（零成本）
        return self._haversine_estimate(
            origin, destination, mode,
            waypoints, origin_address, destination_address,
            waypoint_addresses,
        )

    # ==================== AI 估算 ====================

    def _estimate_with_ai(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints: List[Tuple[float, float]],
        origin_address: str,
        destination_address: str,
        waypoint_addresses: List[str],
    ) -> Optional[Dict[str, Any]]:
        """调用 AI 估算路线，带重试和指数退避"""
        prompt = self._build_prompt(
            origin, destination, mode,
            waypoints, origin_address, destination_address,
            waypoint_addresses,
        )

        last_error = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.ai.chat_with_prompt(
                    system_prompt=(
                        "你是一个专业的路线规划引擎。"
                        "请基于地理知识估算路线，仅返回 JSON，不要包含其他文字。"
                        "确保 JSON 格式严格正确，数值合理。"
                    ),
                    user_prompt=prompt,
                    temperature=0.1,
                    max_tokens=1000,
                )
                return self._parse_ai_response(resp)
            except json.JSONDecodeError as e:
                last_error = e
            except (ConnectionError, TimeoutError) as e:
                last_error = e
            except Exception as e:
                last_error = e

            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= 2  # 指数退避

        return None

    def _build_prompt(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints: List[Tuple[float, float]],
        origin_address: str,
        destination_address: str,
        waypoint_addresses: List[str],
    ) -> str:
        """构造 AI 估算 prompt"""
        origin_desc = origin_address or f"({origin[0]}, {origin[1]})"
        dest_desc = destination_address or f"({destination[0]}, {destination[1]})"
        mode_display = TravelMode(mode).display_name

        waypoints_section = "无"
        if waypoints:
            wp_descs = []
            for i, wp in enumerate(waypoints):
                addr = waypoint_addresses[i] if i < len(waypoint_addresses) else ""
                desc = addr or f"({wp[0]}, {wp[1]})"
                wp_descs.append(f"  途经点{i+1}: {desc}")
            waypoints_section = "\n".join(wp_descs)

        return ROUTE_ESTIMATION_PROMPT.format(
            origin_desc=origin_desc,
            origin_lat=origin[0],
            origin_lon=origin[1],
            dest_desc=dest_desc,
            dest_lat=destination[0],
            dest_lon=destination[1],
            mode_display=mode_display,
            waypoints_section=waypoints_section,
        )

    def _parse_ai_response(self, resp: str) -> Optional[Dict[str, Any]]:
        """三级解析 AI 返回的 JSON

        1. Markdown 代码块 (```json ... ```)
        2. 全文 JSON
        3. 正则匹配 {} 括号内容
        """
        if not resp:
            return None

        text = resp.strip()

        # Level 1: 代码块
        for pattern in [r"```json\s*\n?(.*?)```", r"```\s*\n?(.*?)```"]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    continue

        # Level 2: 全文 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Level 3: 查找第一个 { 到最后一个 }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    # ==================== 合理性检查 ====================

    def _sanity_check(
        self,
        data: Dict[str, Any],
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> bool:
        """检查 AI 估算结果是否合理"""
        try:
            ai_dist = float(data.get("total_distance_km", 0))
            ai_duration = float(data.get("total_duration_minutes", 0))
        except (TypeError, ValueError):
            return False

        if ai_dist <= 0 or ai_duration <= 0:
            return False

        # Haverine 基线距离
        haversine_dist = self._haversine(
            origin[0], origin[1], destination[0], destination[1]
        )
        if waypoints:
            pts = [origin] + waypoints + [destination]
            haversine_dist = sum(
                self._haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                for i in range(len(pts) - 1)
            )

        # AI 距离不应低于直线距离的 0.8 倍（不可能）
        if ai_dist < haversine_dist * 0.8:
            return False
        # AI 距离不应超过直线距离的 4 倍（不合理）
        if ai_dist > haversine_dist * 4.0:
            return False

        return True

    # ==================== 结果构建 ====================

    def _build_route_result(
        self,
        data: Dict[str, Any],
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints: Optional[List[Tuple[float, float]]],
        origin_address: str,
        destination_address: str,
        waypoint_addresses: Optional[List[str]],
    ) -> RouteResult:
        """从 AI 解析数据构建 RouteResult"""
        total_dist_km = float(data.get("total_distance_km", 0))
        total_dur_min = float(data.get("total_duration_minutes", 0))
        segments_raw = data.get("segments", [])

        # 构建摘要
        summary_parts = []
        route_desc = data.get("route_description", "")
        if route_desc:
            summary_parts.append(f"路线概况: {route_desc}")
        travel_tips = data.get("travel_tips", "")
        if travel_tips:
            summary_parts.append(f"出行建议: {travel_tips}")
        ai_summary = "\n".join(summary_parts)

        # 构建分段
        segments = []
        for seg in segments_raw:
            seg_dist = float(seg.get("distance_km", 0))
            seg_dur = float(seg.get("duration_minutes", 0))
            seg_desc = seg.get("description", "")
            segments.append(RouteSegment(
                mode=mode,
                distance_meters=seg_dist * 1000,
                duration_seconds=seg_dur * 60,
                instruction=seg_desc,
            ))

        if not segments:
            segments.append(RouteSegment(
                mode=mode,
                distance_meters=total_dist_km * 1000,
                duration_seconds=total_dur_min * 60,
                instruction=f"从{origin_address or '起点'}到{destination_address or '终点'}",
            ))

        # 构建途经点
        wp_list = []
        if waypoints:
            for i, wp in enumerate(waypoints):
                addr = waypoint_addresses[i] if waypoint_addresses and i < len(waypoint_addresses) else ""
                wp_list.append(RoutePoint(
                    lat=wp[0], lon=wp[1], address=addr, order=i + 1,
                ))

        return RouteResult(
            mode=mode,
            origin=RoutePoint(lat=origin[0], lon=origin[1], address=origin_address, order=0),
            destination=RoutePoint(lat=destination[0], lon=destination[1], address=destination_address, order=len(waypoints) + 1 if waypoints else 1),
            total_distance_meters=total_dist_km * 1000,
            total_duration_seconds=total_dur_min * 60,
            segments=segments,
            waypoints=wp_list,
            ai_summary=ai_summary,
            provider="ai",
        )

    # ==================== Haversine 后备 ====================

    def _haversine_estimate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        waypoints: Optional[List[Tuple[float, float]]],
        origin_address: str,
        destination_address: str,
        waypoint_addresses: Optional[List[str]],
    ) -> RouteResult:
        """纯 Haversine 数学估算（零成本后备）"""
        # 构建坐标点序列
        pts = [origin]
        if waypoints:
            pts.extend(waypoints)
        pts.append(destination)

        # 地址序列
        addrs = [origin_address]
        if waypoint_addresses:
            addrs.extend(waypoint_addresses)
        addrs.append(destination_address)

        road_factor = self.MODE_ROAD_FACTORS.get(mode, 1.3)
        speed = self.MODE_SPEEDS.get(mode, 50.0)

        total_dist = 0.0
        segments = []

        for i in range(len(pts) - 1):
            d = self._haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            road_dist = d * road_factor
            duration_h = road_dist / speed if speed > 0 else 0

            total_dist += road_dist

            from_desc = addrs[i] if i < len(addrs) else f"({pts[i][0]}, {pts[i][1]})"
            to_desc = addrs[i + 1] if i + 1 < len(addrs) else f"({pts[i+1][0]}, {pts[i+1][1]})"
            segments.append(RouteSegment(
                mode=mode,
                distance_meters=road_dist * 1000,
                duration_seconds=duration_h * 3600,
                instruction=f"从{from_desc}到{to_desc}，约{road_dist:.1f}公里",
            ))

        total_duration_h = total_dist / speed if speed > 0 else 0

        wp_list = []
        if waypoints:
            for i, wp in enumerate(waypoints):
                addr = waypoint_addresses[i] if waypoint_addresses and i < len(waypoint_addresses) else ""
                wp_list.append(RoutePoint(lat=wp[0], lon=wp[1], address=addr, order=i + 1))

        mode_display = TravelMode(mode).display_name
        ai_summary = (
            f"[直线估算] 基于 Haversine 公式 × {road_factor} 道路系数估算。\n"
            f"出行方式: {mode_display}，平均速度 {speed} km/h。\n"
            f"注意: 此结果为数学估算，非实际道路数据。"
        )

        return RouteResult(
            mode=mode,
            origin=RoutePoint(lat=origin[0], lon=origin[1], address=origin_address, order=0),
            destination=RoutePoint(lat=destination[0], lon=destination[1], address=destination_address, order=len(pts) - 1),
            total_distance_meters=total_dist * 1000,
            total_duration_seconds=total_duration_h * 3600,
            segments=segments,
            waypoints=wp_list,
            ai_summary=ai_summary,
            provider="haversine",
        )

    # ==================== 工具方法 ====================

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine 距离（公里）"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _validate_coords(lat: float, lon: float, name: str = "坐标") -> None:
        """验证坐标范围"""
        if not (-90 <= lat <= 90):
            raise ValueError(f"{name}纬度超出范围: {lat}，有效范围 [-90, 90]")
        if not (-180 <= lon <= 180):
            raise ValueError(f"{name}经度超出范围: {lon}，有效范围 [-180, 180]")

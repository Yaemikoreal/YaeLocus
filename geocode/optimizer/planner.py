"""
多策略路线推荐

基于频次密度分析和地理聚类结果，生成多种策略的推荐路线。
支持 AI 增强路线描述。
"""

import math
from typing import Dict, List, Optional, Tuple

from .tsp import solve_tsp, tour_distance, _build_distance_matrix, _haversine as tsp_haversine

from geocode.ai import AIClient
from geocode.ai.prompts import ROUTE_DESCRIPTION_PROMPT
from .models import LocationCluster, LocationStat, RecommendedRoute


class RouteRecommender:
    """路线推荐器

    支持 4 种策略：密度优先、距离优先、区域聚合、均衡推荐
    """

    # 策略中文名映射
    STRATEGY_NAMES = {
        "density_first": "密度优先",
        "distance_first": "距离优先",
        "cluster_first": "区域聚合",
        "balanced": "均衡推荐",
    }

    # 策略描述
    STRATEGY_DESCRIPTIONS = {
        "density_first": "优先访问出现频次最高的位置，适合优先处理高频热点",
        "distance_first": "按地理邻近性依次访问，路线总距离最短",
        "cluster_first": "按区域聚类依次访问，同一区域内优化访问顺序",
        "balanced": "综合平衡频次密度与地理距离，推荐整体最优方案",
    }

    def __init__(
        self,
        start_point: Optional[Tuple[float, float]] = None,
        top_n: int = 3,
        max_waypoints: int = 20,
    ):
        """
        Args:
            start_point: 总起点坐标 (lat, lon)，为 None 时从第一个位置开始
            top_n: 返回推荐路线数量
            max_waypoints: 单条路线最大途经点数
        """
        self.start_point = start_point
        self.top_n = min(top_n, 4)
        self.max_waypoints = max_waypoints

    def recommend(
        self,
        locations: List[LocationStat],
        clusters: List[LocationCluster],
        strategy: str = "",
        ai_client: Optional[AIClient] = None,
    ) -> List[RecommendedRoute]:
        """生成推荐路线

        Args:
            locations: 分析后的位置列表（含密度评分和聚类ID）
            clusters: 聚类列表
            strategy: 指定策略，为空则生成所有策略
            ai_client: AI 客户端（可选），用于生成路线描述

        Returns:
            按 priority_score 降序排列的推荐路线列表
        """
        if not locations:
            return []

        routes = []
        strategies = [strategy] if strategy else ["density_first", "distance_first", "cluster_first", "balanced"]

        builders = {
            "density_first": self._build_density_first,
            "distance_first": self._build_distance_first,
            "cluster_first": self._build_cluster_first,
            "balanced": self._build_balanced,
        }

        for s in strategies:
            if s in builders:
                route = builders[s](locations, clusters)
                if route and route.waypoints:
                    route.strategy = s
                    self._calculate_route_score(route, locations)
                    routes.append(route)

        routes.sort(key=lambda r: r.priority_score, reverse=True)
        routes = routes[:self.top_n]

        # AI 增强描述
        if ai_client:
            for route in routes:
                self._ai_enhance_description(route, ai_client)

        return routes

    def _haversine(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
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

    def _make_waypoint(
        self, loc: LocationStat, order: int
    ) -> Dict:
        """创建途经点字典"""
        return {
            "address": loc.address,
            "lat": loc.lat,
            "lon": loc.lon,
            "order": order,
            "frequency": loc.frequency,
            "density_score": round(loc.density_score, 2),
            "cluster_id": loc.cluster_id,
        }

    def _estimate_distance(self, waypoints: List[Dict]) -> float:
        """估算路线总距离（累加 Haversine）"""
        if len(waypoints) < 2:
            return 0.0
        total = 0.0
        for i in range(len(waypoints) - 1):
            total += self._haversine(
                waypoints[i]["lat"], waypoints[i]["lon"],
                waypoints[i + 1]["lat"], waypoints[i + 1]["lon"],
            )
        return round(total, 2)

    def _calculate_route_score(
        self, route: RecommendedRoute, all_locations: List[LocationStat]
    ) -> None:
        """计算路线综合评分"""
        if not all_locations:
            return

        total_freq_all = sum(loc.frequency for loc in all_locations)
        total_locs_all = len(all_locations)

        coverage_rate = route.total_locations / total_locs_all if total_locs_all > 0 else 0
        freq_coverage = route.total_frequency / total_freq_all if total_freq_all > 0 else 0

        # 路线效率：1 - (实际距离 / 最差情况距离)
        # 最差情况 = 将所有位置按经纬度范围对角线排列
        if total_locs_all > 1:
            lats = [loc.lat for loc in all_locations]
            lons = [loc.lon for loc in all_locations]
            max_dist = self._haversine(
                min(lats), min(lons), max(lats), max(lons)
            ) * total_locs_all
            efficiency = 1 - (route.total_distance_km / max_dist) if max_dist > 0 else 0.5
        else:
            efficiency = 0.5

        route.priority_score = round(
            coverage_rate * 0.4 + freq_coverage * 0.3 + efficiency * 0.3,
            4,
        )

    # ========== 四种策略 ==========

    def _build_density_first(
        self,
        locations: List[LocationStat],
        clusters: List[LocationCluster],
    ) -> RecommendedRoute:
        """密度优先：从起点出发，依次访问 density_score 最高的位置"""
        sorted_locs = sorted(locations, key=lambda loc: loc.density_score, reverse=True)
        waypoints = self._apply_start_point(sorted_locs)
        waypoints = waypoints[:self.max_waypoints]

        wp_list = []
        for i, loc in enumerate(waypoints):
            wp_list.append(self._make_waypoint(loc, i))

        total_dist = self._estimate_distance(wp_list)
        total_freq = sum(w["frequency"] for w in wp_list)

        return RecommendedRoute(
            name=self.STRATEGY_NAMES["density_first"],
            description=self.STRATEGY_DESCRIPTIONS["density_first"],
            waypoints=wp_list,
            total_distance_km=total_dist,
            total_locations=len(wp_list),
            total_frequency=total_freq,
            coverage_rate=round(len(wp_list) / max(len(locations), 1), 4),
        )

    def _build_distance_first(
        self,
        locations: List[LocationStat],
        clusters: List[LocationCluster],
    ) -> RecommendedRoute:
        """距离优先：贪心 TSP + 2-opt 局部搜索优化"""
        if not locations:
            return RecommendedRoute(
                name=self.STRATEGY_NAMES["distance_first"],
                description=self.STRATEGY_DESCRIPTIONS["distance_first"],
                waypoints=[],
            )

        capped = locations[:self.max_waypoints]
        n = len(capped)

        # 确定起点索引
        start_idx = 0
        if self.start_point:
            start_lat, start_lon = self.start_point
            best_d = float("inf")
            for idx, loc in enumerate(capped):
                d = self._haversine(start_lat, start_lon, loc.lat, loc.lon)
                if d < best_d:
                    best_d = d
                    start_idx = idx

        # 构建坐标列表和距离矩阵
        coords = [(loc.lat, loc.lon) for loc in capped]
        dist_matrix = _build_distance_matrix(coords, dist_func=tsp_haversine)

        # 使用贪心 + 2-opt 求解 TSP
        if n >= 3:
            order = solve_tsp(coords, method="2opt", start_idx=start_idx, dist_matrix=dist_matrix)
        else:
            order = list(range(n))

        ordered = [capped[i] for i in order]
        wp_list = [self._make_waypoint(loc, i) for i, loc in enumerate(ordered)]
        total_dist = tour_distance(order, dist_matrix)
        total_freq = sum(w["frequency"] for w in wp_list)

        return RecommendedRoute(
            name=self.STRATEGY_NAMES["distance_first"],
            description=self.STRATEGY_DESCRIPTIONS["distance_first"],
            waypoints=wp_list,
            total_distance_km=round(total_dist, 2),
            total_locations=len(wp_list),
            total_frequency=total_freq,
            coverage_rate=round(len(wp_list) / max(len(locations), 1), 4),
        )

    def _build_cluster_first(
        self,
        locations: List[LocationStat],
        clusters: List[LocationCluster],
    ) -> RecommendedRoute:
        """区域聚合：按聚类依次访问，同簇内按距离优化"""
        if not clusters:
            return self._build_distance_first(locations, clusters)

        # 按聚类评分降序
        sorted_clusters = sorted(clusters, key=lambda c: c.score, reverse=True)
        ordered = []

        # 依次访问各聚类
        assigned = set()
        for cluster in sorted_clusters:
            # 簇内位置按与上个位置的距离排序（贪心）
            cluster_locs = sorted(
                cluster.locations,
                key=lambda loc: loc.density_score,
                reverse=True,
            )
            for loc in cluster_locs:
                if id(loc) not in assigned:
                    ordered.append(loc)
                    assigned.add(id(loc))
                    if len(ordered) >= self.max_waypoints:
                        break
            if len(ordered) >= self.max_waypoints:
                break

        wp_list = [self._make_waypoint(loc, i) for i, loc in enumerate(ordered)]
        total_dist = self._estimate_distance(wp_list)
        total_freq = sum(w["frequency"] for w in wp_list)

        return RecommendedRoute(
            name=self.STRATEGY_NAMES["cluster_first"],
            description=self.STRATEGY_DESCRIPTIONS["cluster_first"],
            waypoints=wp_list,
            total_distance_km=total_dist,
            total_locations=len(wp_list),
            total_frequency=total_freq,
            coverage_rate=round(len(wp_list) / max(len(locations), 1), 4),
        )

    def _build_balanced(
        self,
        locations: List[LocationStat],
        clusters: List[LocationCluster],
    ) -> RecommendedRoute:
        """均衡推荐：综合 density_score 和距离的加权排序"""
        if not locations:
            return RecommendedRoute(
                name=self.STRATEGY_NAMES["balanced"],
                description=self.STRATEGY_DESCRIPTIONS["balanced"],
                waypoints=[],
            )

        # 综合评分 = density_score × 0.6 + (1 - 距离权重) × 0.4
        unvisited = list(locations)
        ordered = []

        if self.start_point:
            current_lat, current_lon = self.start_point
        else:
            first = unvisited.pop(0)
            ordered.append(first)
            current_lat, current_lon = first.lat, first.lon

        while unvisited and len(ordered) < self.max_waypoints:
            # 对每个未访问位置计算综合评分
            c_lat, c_lon = current_lat, current_lon

            def combined_score(loc: LocationStat, _lat=c_lat, _lon=c_lon) -> float:
                dist = self._haversine(_lat, _lon, loc.lat, loc.lon)
                # 距离归一化（最大 100km，超过视为 1）
                dist_weight = min(dist / 100.0, 1.0)
                # 频次密度归一化
                max_freq = max(loc.frequency for loc in unvisited) if unvisited else 1
                freq_weight = loc.frequency / max_freq if max_freq > 0 else 0
                return freq_weight * 0.6 + (1 - dist_weight) * 0.4

            best = max(unvisited, key=combined_score)
            ordered.append(best)
            unvisited.remove(best)
            current_lat, current_lon = best.lat, best.lon

        wp_list = [self._make_waypoint(loc, i) for i, loc in enumerate(ordered)]
        total_dist = self._estimate_distance(wp_list)
        total_freq = sum(w["frequency"] for w in wp_list)

        return RecommendedRoute(
            name=self.STRATEGY_NAMES["balanced"],
            description=self.STRATEGY_DESCRIPTIONS["balanced"],
            waypoints=wp_list,
            total_distance_km=total_dist,
            total_locations=len(wp_list),
            total_frequency=total_freq,
            coverage_rate=round(len(wp_list) / max(len(locations), 1), 4),
        )

    def _apply_start_point(
        self, locations: List[LocationStat]
    ) -> List[LocationStat]:
        """将起点插入路线开头"""
        if not self.start_point:
            return locations
        # 创建虚拟起点并前置
        start_loc = LocationStat(
            address=f"起点({self.start_point[0]:.4f},{self.start_point[1]:.4f})",
            lat=self.start_point[0],
            lon=self.start_point[1],
            frequency=1,
            density_score=999999.0,  # 密度优先策略中排第一位
            cluster_id=-1,
        )
        return [start_loc] + locations

    def _ai_enhance_description(
        self, route: RecommendedRoute, ai_client: AIClient
    ) -> None:
        """使用 AI 生成路线描述"""
        waypoints_text = " -> ".join(
            [wp["address"][:20] for wp in route.waypoints[:5]]
        )
        if len(route.waypoints) > 5:
            waypoints_text += f" ...等{len(route.waypoints)}处"

        prompt = ROUTE_DESCRIPTION_PROMPT.format(
            route_name=route.name,
            waypoints_text=waypoints_text,
            total_distance_km=route.total_distance_km,
            total_locations=route.total_locations,
            strategy=route.strategy,
        )

        try:
            description = ai_client.chat_with_prompt(
                system_prompt="你是一个旅游路线描述专家。请用简洁的中文回答。",
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=200,
            )
            # 将 AI 描述附加到原有描述后
            route.description = f"{route.description}\n[AI建议] {description}"
        except Exception:
            pass

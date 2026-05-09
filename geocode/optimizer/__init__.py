"""
行程优化模块

在地理编码结果和路线规划之间，提供频次密度分析、地理聚类、
和多策略路线推荐功能。

Usage:
    from geocode.optimizer import ItineraryOptimizer

    optimizer = ItineraryOptimizer(cluster_radius_km=5.0)
    result = optimizer.optimize(
        csv_path="output/地址_经纬度_结果.csv",
        start_address="北京",
        top_n=3,
    )
    for route in result["recommended_routes"]:
        print(f"[{route.name}] {route.total_locations} 处, "
              f"{route.total_distance_km}km, 评分: {route.priority_score}")
"""

from typing import Any, Dict, List, Optional, Tuple

from .analyzer import LocationAnalyzer
from .models import LocationCluster, LocationStat, RecommendedRoute
from .planner import RouteRecommender


class ItineraryOptimizer:
    """行程优化器

    整合频次分析、密度评分、地理聚类和路线推荐。

    Usage:
        optimizer = ItineraryOptimizer(cluster_radius_km=5.0)
        result = optimizer.optimize(
            csv_path="output/地址_经纬度_结果.csv",
            start_address="北京",
        )
    """

    def __init__(self, cluster_radius_km: float = 5.0, min_samples: int = 2):
        self.analyzer = LocationAnalyzer(
            cluster_radius_km=cluster_radius_km,
            min_samples=min_samples,
        )

    def optimize(
        self,
        csv_path: Optional[str] = None,
        results: Optional[List[Dict]] = None,
        start_point: Optional[Tuple[float, float]] = None,
        start_address: Optional[str] = None,
        top_n: int = 3,
        strategy: str = "",
        max_waypoints: int = 20,
        ai_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """执行完整行程优化流程

        Args:
            csv_path: 地理编码结果 CSV 路径
            results: 地理编码结果字典列表（与 csv_path 二选一）
            start_point: 总起点坐标 (lat, lon)
            start_address: 总起点地址（自动地理编码）
            top_n: 返回推荐路线数量
            strategy: 指定策略（空=全部）
            max_waypoints: 单条路线最大途经点数
            ai_client: AI 客户端（可选），用于生成路线描述

        Returns:
            {
                "stats": {...},
                "locations": [...],
                "clusters": [...],
                "recommended_routes": [RecommendedRoute, ...],
            }
        """
        # 1. 加载数据
        if csv_path:
            locations = self.analyzer.load_from_csv(csv_path)
        elif results:
            locations = self.analyzer.load_from_results(results)
        else:
            raise ValueError("必须提供 csv_path 或 results")

        if not locations:
            return {
                "stats": {"total_unique": 0, "total_locations": 0, "clusters": 0},
                "locations": [],
                "clusters": [],
                "recommended_routes": [],
            }

        total_raw = sum(loc.frequency for loc in locations)

        # 2. 分析（密度评分 + DBSCAN 聚类）
        locations, clusters, noise = self.analyzer.analyze(locations)

        # 3. 解析起点
        final_start = start_point
        if start_address and not final_start:
            try:
                from geocode.cache import CacheManager
                from geocode.geocoder import Geocoder

                geo = Geocoder(CacheManager())
                result = geo.geocode(start_address)
                geo.close()
                if result.get("success"):
                    final_start = (result["latitude"], result["longitude"])
            except Exception:
                pass

        # 4. 推荐路线
        recommender = RouteRecommender(
            start_point=final_start,
            top_n=top_n,
            max_waypoints=max_waypoints,
        )
        routes = recommender.recommend(locations, clusters, strategy=strategy, ai_client=ai_client)

        # 5. 统计数据
        stats = {
            "total_unique": len(locations),
            "total_raw_entries": total_raw,
            "total_clusters": len(clusters),
            "cluster_radius_km": self.analyzer.cluster_radius_km,
            "has_start_point": final_start is not None,
        }
        if final_start:
            stats["start_point"] = {"lat": final_start[0], "lon": final_start[1]}

        return {
            "stats": stats,
            "locations": [loc.to_dict() for loc in locations],
            "clusters": [c.to_dict() for c in clusters],
            "noise_locations": [loc.to_dict() for loc in noise],
            "recommended_routes": routes,
        }

    def get_summary(self, result: Dict) -> str:
        """生成优化摘要文本"""
        stats = result["stats"]
        routes = result["recommended_routes"]

        lines = [
            f"共 {stats['total_unique']} 个独立位置（{stats['total_raw_entries']} 条原始记录），"
            f"{stats['total_clusters']} 个聚类",
        ]
        if routes:
            lines.append(f"生成 {len(routes)} 条推荐路线:")
            for r in routes:
                lines.append(
                    f"  - {r.name}: {r.total_locations} 处位置, "
                    f"{r.total_distance_km}km, "
                    f"覆盖频次 {r.total_frequency}, "
                    f"评分 {r.priority_score:.3f}"
                )
        return "\n".join(lines)


__all__ = [
    "ItineraryOptimizer",
    "LocationStat",
    "LocationCluster",
    "RecommendedRoute",
    "LocationAnalyzer",
    "RouteRecommender",
]

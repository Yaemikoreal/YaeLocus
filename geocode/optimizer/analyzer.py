"""
频次分析、密度评分与地理聚类
"""

import math
from typing import Dict, List, Tuple

from .models import LocationCluster, LocationStat


class LocationAnalyzer:
    """位置分析器

    对地理编码结果进行频次统计、密度评分和空间聚类。
    """

    def __init__(self, cluster_radius_km: float = 5.0, min_samples: int = 2):
        """
        Args:
            cluster_radius_km: 聚类半径（公里）
            min_samples: DBSCAN 最小邻居数，默认 2
        """
        self.cluster_radius_km = cluster_radius_km
        self.min_samples = min_samples

    def load_from_csv(
        self,
        csv_path: str,
        addr_col: str = "原始地址",
        lat_col: str = "纬度",
        lon_col: str = "经度",
    ) -> List[LocationStat]:
        """从地理编码结果 CSV 或 JSON 文件加载数据，自动检测格式

        Args:
            csv_path: 文件路径（支持 .csv 或 .json）
            addr_col: 地址列名
            lat_col: 纬度列名
            lon_col: 经度列名

        Returns:
            LocationStat 列表（已合并频次）
        """
        import pandas as pd

        # 自动检测格式：尝试 JSON 解析，失败则按 CSV 处理
        raw = None
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                first_char = f.read(1)
                f.seek(0)
                if first_char == "[":
                    import json
                    raw = json.load(f)
        except Exception:
            pass

        if raw is not None:
            # JSON 格式
            df = pd.DataFrame(raw)
            records = []
            for _, row in df.iterrows():
                if row.get("状态") != "成功":
                    continue
                try:
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                    if not lat or not lon:
                        continue
                    records.append({
                        "address": str(row.get(addr_col, "")).strip(),
                        "lat": lat,
                        "lon": lon,
                    })
                except (ValueError, TypeError):
                    continue
            return self._merge_by_address(records)

        # CSV 格式
        df = pd.read_csv(csv_path, encoding="utf-8-sig")

        status_col = "状态"
        if status_col in df.columns:
            df = df[df[status_col] == "成功"]

        records = []
        for _, row in df.iterrows():
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                if not lat or not lon:
                    continue
                records.append({
                    "address": str(row.get(addr_col, "")).strip(),
                    "lat": lat,
                    "lon": lon,
                })
            except (ValueError, TypeError):
                continue

        return self._merge_by_address(records)

    def load_from_results(self, results: List[Dict]) -> List[LocationStat]:
        """从地理编码结果字典列表加载

        Args:
            results: 地理编码结果列表，每项含 original_address / latitude / longitude

        Returns:
            LocationStat 列表（已合并频次）
        """
        records = []
        for r in results:
            if not r.get("success"):
                continue
            try:
                lat = float(r["latitude"])
                lon = float(r["longitude"])
                records.append({
                    "address": str(r.get("original_address", "")).strip(),
                    "lat": lat,
                    "lon": lon,
                })
            except (ValueError, TypeError, KeyError):
                continue

        return self._merge_by_address(records)

    def _normalize(self, address: str) -> str:
        """标准化地址用于频次匹配"""
        return address.strip().lower().replace(" ", "").replace("，", ",")

    def _merge_by_address(self, records: List[Dict]) -> List[LocationStat]:
        """按标准化地址合并频次"""
        merged = {}

        for rec in records:
            key = self._normalize(rec["address"])
            if key in merged:
                stat = merged[key]
                stat.frequency += 1
                if rec["address"] not in stat.original_addresses:
                    stat.original_addresses.append(rec["address"])
                # 取平均坐标（同名地址可能略有偏移）
                n = stat.frequency
                stat.lat = stat.lat * (n - 1) / n + rec["lat"] / n
                stat.lon = stat.lon * (n - 1) / n + rec["lon"] / n
            else:
                merged[key] = LocationStat(
                    address=rec["address"],
                    lat=rec["lat"],
                    lon=rec["lon"],
                    frequency=1,
                    original_addresses=[rec["address"]],
                )

        result = list(merged.values())
        result.sort(key=lambda s: s.frequency, reverse=True)
        return result

    def analyze(
        self, locations: List[LocationStat]
    ) -> Tuple[List[LocationStat], List[LocationCluster], List[LocationStat]]:
        """执行完整分析：密度评分 + DBSCAN 聚类

        Args:
            locations: 位置统计列表（来自 load_from_*）

        Returns:
            (locations_with_scores, clusters, noise_locations)
            noise_locations 为无法归入任何聚类的孤立点
        """
        if not locations:
            return [], [], []

        self._calculate_density_scores(locations)
        clusters, noise = self._cluster_locations(locations, min_samples=self.min_samples)
        return locations, clusters, noise

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine 公式计算两点间距离（公里）"""
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

    def _calculate_density_scores(self, locations: List[LocationStat]) -> None:
        """计算每个位置的密度评分

        密度评分 = frequency × 0.6 + nearby_count × 0.4
        nearby_count 为半径 cluster_radius_km 内的其他位置数量
        """
        for loc in locations:
            nearby = 0
            for other in locations:
                if other is loc:
                    continue
                dist = self._haversine(loc.lat, loc.lon, other.lat, other.lon)
                if dist <= self.cluster_radius_km:
                    nearby += 1
            loc.density_score = loc.frequency * 0.6 + nearby * 0.4

    def _cluster_locations(
        self, locations: List[LocationStat], min_samples: int = 2
    ) -> Tuple[List[LocationCluster], List[LocationStat]]:
        """DBSCAN 密度聚类

        标准 DBSCAN 算法：
        - 核心点：eps 半径内至少有 min_samples 个邻居（含自身）
        - 边界点：在核心点邻域内但邻居数不足 min_samples
        - 噪声点：既非核心点也非边界点

        Args:
            locations: 待聚类的位置列表
            min_samples: 成为核心点的最小邻居数

        Returns:
            (clusters, noise): 聚类列表和噪声点列表
        """
        n = len(locations)
        if n == 0:
            return [], []

        eps = self.cluster_radius_km

        # 预计算邻域
        neighbors = {}
        for i, loc in enumerate(locations):
            nbrs = []
            for j, other in enumerate(locations):
                if i == j:
                    continue
                if self._haversine(loc.lat, loc.lon, other.lat, other.lon) <= eps:
                    nbrs.append(j)
            neighbors[i] = nbrs

        # 识别核心点
        is_core = [len(neighbors[i]) >= min_samples for i in range(n)]

        # DBSCAN 聚类
        visited = [False] * n
        labels = [-1] * n  # -1 = 噪声
        cluster_id = -1

        for i in range(n):
            if visited[i]:
                continue
            visited[i] = True

            if not is_core[i]:
                continue  # 非核心点暂不处理

            cluster_id += 1
            labels[i] = cluster_id

            # BFS 扩展聚类
            queue = list(neighbors[i])
            for q in queue:
                if visited[q]:
                    continue
                visited[q] = True
                if is_core[q]:
                    # 核心点：将其邻居也加入队列
                    for nbr in neighbors[q]:
                        if nbr not in queue and nbr != i:
                            queue.append(nbr)
                # 边界点或核心点都归入本聚类
                labels[q] = cluster_id

        # 组装结果
        clusters = []
        noise = []
        for cid in range(cluster_id + 1):
            cluster_locs = [locations[i] for i in range(n) if labels[i] == cid]
            if not cluster_locs:
                continue
            for loc in cluster_locs:
                loc.cluster_id = cid

            center_lat = sum(loc.lat for loc in cluster_locs) / len(cluster_locs)
            center_lon = sum(loc.lon for loc in cluster_locs) / len(cluster_locs)
            total_freq = sum(loc.frequency for loc in cluster_locs)
            max_dist = max(
                self._haversine(center_lat, center_lon, loc.lat, loc.lon)
                for loc in cluster_locs
            )

            cluster = LocationCluster(
                cluster_id=cid,
                center_lat=center_lat,
                center_lon=center_lon,
                locations=cluster_locs,
                total_frequency=total_freq,
                radius_km=round(max_dist, 2),
                score=round(total_freq + len(cluster_locs) * 0.5, 2),
            )
            clusters.append(cluster)

        # 收集噪声点
        noise = [locations[i] for i in range(n) if labels[i] == -1]

        clusters.sort(key=lambda c: c.score, reverse=True)
        return clusters, noise

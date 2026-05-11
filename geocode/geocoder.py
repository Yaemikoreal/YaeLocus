"""
地理编码核心模块

支持高德、天地图、百度三个API的智能轮换
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter

from .cache import CacheManager
from .config import Config
from .coords import gcj02_to_wgs84, bd09_to_wgs84
from .logger import APILogger
from .models import GeocodeResult
from .preprocessing import InvalidAddressFilter, AddressNormalizer
from .validation import ConfidenceValidator


class Geocoder:
    """
    地理编码器

    支持多API轮换、智能缓存、限流控制、HTTP连接复用、重试机制
    """

    # 各 API 的每秒最大并发请求数（尊重免费配额）
    _API_RATE_LIMITS = {
        "amap": 5,       # 高德: 5 QPS
        "tianditu": 10,  # 天地图: 10 QPS
        "baidu": 5,      # 百度: 5 QPS
    }

    def __init__(
        self,
        cache_manager: CacheManager = None,
        api_logger: APILogger = None,
        cache_ttl: float = None
    ):
        """
        初始化地理编码器

        Args:
            cache_manager: 缓存管理器
            api_logger: API日志记录器
            cache_ttl: 缓存过期时间(秒)，None表示永不过期
        """
        self.cache = cache_manager if cache_manager is not None else CacheManager()
        self.logger = api_logger if api_logger is not None else APILogger()
        self._cache_ttl = cache_ttl
        self._request_count = 0
        self._success_count = 0
        self._counter_lock = threading.Lock()

        # 各 API 独立限流状态
        self._api_last_request: Dict[str, float] = {}
        self._api_locks: Dict[str, threading.Lock] = {}

        # 预处理和验证组件 — 单例化避免重复 I/O
        self.normalizer = AddressNormalizer()
        self.filter_obj = InvalidAddressFilter()
        self.validator = ConfidenceValidator()

        # 各 API 限流信号量
        self._api_semaphores = {
            name: threading.BoundedSemaphore(limit)
            for name, limit in self._API_RATE_LIMITS.items()
        }

        # HTTP Session 复用（性能优化）
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # 重试逻辑在内部实现
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def _rate_limit(self, api_name: str = "amap") -> None:
        """各 API 独立请求限流"""
        if api_name not in self._api_locks:
            self._api_locks[api_name] = threading.Lock()
        lock = self._api_locks[api_name]

        min_interval = 1.0 / self._API_RATE_LIMITS.get(api_name, 5)

        with lock:
            if api_name in self._api_last_request:
                elapsed = time.time() - self._api_last_request[api_name]
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            self._api_last_request[api_name] = time.time()

    def _api_call_with_retry(
        self,
        url: str,
        params: dict,
        api_name: str = "amap",
        max_retries: int = 3
    ) -> Optional[requests.Response]:
        """
        带重试的 API 调用

        仅对网络错误重试，不对 API 返回错误重试

        Args:
            url: API 端点 URL
            params: 请求参数
            api_name: API 名称，用于限流
            max_retries: 最大重试次数

        Returns:
            Response 对象或 None
        """
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                self._rate_limit(api_name)
                response = self._session.get(url, params=params, timeout=Config.REQUEST_TIMEOUT)
                return response
            except (requests.Timeout, requests.ConnectionError):
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    raise
        return None

    def _build_result(
        self,
        address: str,
        lat: float,
        lon: float,
        formatted_address: str,
        source: str,
        coordinate_system: str,
        province: str = None,
        city: str = None,
        district: str = None,
        original_lat: float = None,
        original_lon: float = None
    ) -> GeocodeResult:
        """构建结果对象"""
        return GeocodeResult(
            latitude=lat,
            longitude=lon,
            original_address=address,
            formatted_address=formatted_address,
            province=province,
            city=city,
            district=district,
            source=source,
            coordinate_system=coordinate_system,
            original_lat=original_lat,
            original_lon=original_lon
        )

    def _geocode_amap(self, address: str) -> Optional[GeocodeResult]:
        """高德地图地理编码"""
        if not Config.AMAP_KEY:
            return None

        start_time = time.time()

        try:
            params = {"key": Config.AMAP_KEY, "address": address, "output": "json"}
            response = self._api_call_with_retry(Config.AMAP_URL, params, api_name="amap")
            data = response.json()
            time_cost = time.time() - start_time

            if data.get("status") == "1" and data.get("geocodes"):
                geo = data["geocodes"][0]
                location = geo.get("location", "").split(",")
                if len(location) == 2:
                    lon, lat = float(location[0]), float(location[1])
                    wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

                    self.logger.log(
                        address=address, api_name="amap", status="success",
                        latitude=wgs_lat, longitude=wgs_lon,
                        formatted_address=geo.get("formatted_address"),
                        time_cost=time_cost
                    )
                    return self._build_result(
                        address, wgs_lat, wgs_lon,
                        geo.get("formatted_address"), "amap", "GCJ-02",
                        geo.get("province"), geo.get("city"), geo.get("district"),
                        lat, lon
                    )

            self.logger.log(
                address=address, api_name="amap", status="failed",
                time_cost=time_cost,
                error_message=data.get("info", "Unknown error")
            )
            return None

        except Exception as e:
            self.logger.log(
                address=address, api_name="amap", status="error",
                time_cost=time.time() - start_time,
                error_message=str(e)
            )
            return None

    def _geocode_tianditu(self, address: str) -> Optional[GeocodeResult]:
        """天地图地理编码"""
        if not Config.TIANDITU_TK:
            return None

        start_time = time.time()

        try:
            params = {"ds": f'{{"keyWord":"{address}"}}', "tk": Config.TIANDITU_TK}
            response = self._api_call_with_retry(Config.TIANDITU_URL, params, api_name="tianditu")
            data = response.json()
            time_cost = time.time() - start_time

            if data.get("status") == "0" and data.get("location"):
                loc = data["location"]
                lon = float(loc.get("lon", 0))
                lat = float(loc.get("lat", 0))

                self.logger.log(
                    address=address, api_name="tianditu", status="success",
                    latitude=lat, longitude=lon,
                    formatted_address=loc.get("address"),
                    time_cost=time_cost
                )
                return self._build_result(
                    address, lat, lon,
                    loc.get("address"), "tianditu", "CGCS2000",
                    loc.get("province"), loc.get("city"), loc.get("county")
                )

            self.logger.log(
                address=address, api_name="tianditu", status="failed",
                time_cost=time_cost,
                error_message=data.get("msg", "Unknown error")
            )
            return None

        except Exception as e:
            self.logger.log(
                address=address, api_name="tianditu", status="error",
                time_cost=time.time() - start_time,
                error_message=str(e)
            )
            return None

    def _geocode_baidu(self, address: str) -> Optional[GeocodeResult]:
        """百度地图地理编码"""
        if not Config.BAIDU_AK:
            return None

        start_time = time.time()

        try:
            params = {"address": address, "output": "json", "ak": Config.BAIDU_AK}
            response = self._api_call_with_retry(Config.BAIDU_URL, params, api_name="baidu")
            data = response.json()
            time_cost = time.time() - start_time

            if data.get("status") == 0 and data.get("result"):
                result_data = data["result"]
                location = result_data.get("location", {})
                lat = location.get("lat", 0)
                lon = location.get("lng", 0)
                wgs_lat, wgs_lon = bd09_to_wgs84(lat, lon)

                self.logger.log(
                    address=address, api_name="baidu", status="success",
                    latitude=wgs_lat, longitude=wgs_lon,
                    formatted_address=result_data.get("formatted_address"),
                    time_cost=time_cost
                )
                return self._build_result(
                    address, wgs_lat, wgs_lon,
                    result_data.get("formatted_address"), "baidu", "BD-09",
                    original_lat=lat, original_lon=lon
                )

            self.logger.log(
                address=address, api_name="baidu", status="failed",
                time_cost=time_cost,
                error_message=str(data.get("status", "Unknown error"))
            )
            return None

        except Exception as e:
            self.logger.log(
                address=address, api_name="baidu", status="error",
                time_cost=time.time() - start_time,
                error_message=str(e)
            )
            return None

    def geocode(self, address: str) -> Dict:
        """
        地理编码单个地址（集成预处理和验证）

        Args:
            address: 地址字符串

        Returns:
            地理编码结果字典（含 confidence 字段）
        """
        # === 预处理阶段 ===
        # 1. 无效数据检查
        is_valid, reason = self.filter_obj.is_valid(address)
        if not is_valid:
            return {
                "success": False,
                "original_address": str(address),
                "error": f"无效地址: {reason}",
                "confidence": {"total": 0, "issues": [reason], "is_trustworthy": False}
            }

        # 2. 地址标准化和省份推断
        normalized, meta = self.normalizer.normalize(str(address))
        province_hint = meta.get("province_hint")

        if not normalized or not normalized.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address"}

        with self._counter_lock:
            self._request_count += 1

        # 检查缓存（使用标准化地址）
        cached = self.cache.get(normalized)
        if cached is not None:
            # 添加置信度标记（缓存结果视为可信）
            if "confidence" not in cached:
                cached["confidence"] = {"total": 100, "issues": [], "is_trustworthy": True}
            return cached

        # 按优先级尝试各API（使用标准化地址）
        for api_name in Config.API_PRIORITY:
            method = getattr(self, f"_geocode_{api_name}", None)
            if method:
                result = method(normalized)  # 使用标准化地址调用API
                if result:
                    result.success = True
                    with self._counter_lock:
                        self._success_count += 1
                    result_dict = result.to_dict()

                    # === 结果验证阶段 ===
                    confidence = self.validator.validate(
                        str(address),  # 原始地址
                        result_dict,
                        province_hint
                    )

                    # 添加置信度字段
                    result_dict["confidence"] = {
                        "total": confidence.total,
                        "issues": confidence.issues,
                        "is_trustworthy": confidence.is_trustworthy
                    }

                    # 低置信度警告
                    if not confidence.is_trustworthy:
                        result_dict["warning"] = "置信度较低，建议人工核实"

                    # 写入缓存（仅使用标准化地址作为键，智能缓存键会处理变体）
                    self.cache.set(normalized, result_dict, self._cache_ttl)
                    return result_dict

        # 所有API都失败
        return {
            "success": False,
            "original_address": str(address),
            "normalized_address": normalized,
            "province_hint": province_hint,
            "error": "All APIs failed",
            "confidence": {"total": 0, "issues": ["All APIs failed"], "is_trustworthy": False}
        }

    def batch_geocode(
        self, addresses: List[str], progress: bool = True, workers: int = 3
    ) -> List[Dict]:
        """
        批量地理编码（并行处理）

        Args:
            addresses: 地址列表
            progress: 是否显示进度条
            workers: 并行线程数，默认 3

        Returns:
            结果列表（保持原始顺序）
        """
        if not addresses:
            return []

        total = len(addresses)

        # 少于 3 条不启用并行
        if workers < 2 or total < 3:
            results = []
            iterator = addresses
            if progress and not os.environ.get('YAELOCUS_TUI'):
                try:
                    from tqdm import tqdm
                    iterator = tqdm(addresses, desc="地理编码中", unit="条")
                except ImportError:
                    pass
            for address in iterator:
                results.append(self.geocode(address))
            self.cache.flush()
            self.logger.save()
            return results

        results: List[Optional[Dict]] = [None] * total

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.geocode, addr): idx
                for idx, addr in enumerate(addresses)
            }

            completed = 0
            if progress and not os.environ.get('YAELOCUS_TUI'):
                try:
                    from tqdm import tqdm
                    pbar = tqdm(total=total, desc="地理编码中", unit="条")
                except ImportError:
                    pbar = None
            else:
                pbar = None

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {
                        "success": False,
                        "original_address": addresses[idx],
                        "error": str(e),
                        "confidence": {"total": 0, "issues": [str(e)], "is_trustworthy": False}
                    }
                completed += 1
                if pbar:
                    pbar.update(1)

            if pbar:
                pbar.close()

        self.cache.flush()
        self.logger.save()

        return [r for r in results if r is not None]

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return self.cache.get_stats()

    def get_stats(self) -> Dict:
        """获取运行统计信息"""
        return {
            "total_requests": self._request_count,
            "successful_requests": self._success_count,
            "failed_requests": self._request_count - self._success_count,
            "cache_stats": self.cache.get_stats()
        }

    def cleanup_cache(self) -> int:
        """清理过期缓存"""
        return self.cache.cleanup()

    def reverse_geocode(self, lat: float, lon: float) -> Dict:
        """
        逆地理编码：经纬度转地址

        Args:
            lat: 纬度（WGS-84坐标系）
            lon: 经度（WGS-84坐标系）

        Returns:
            逆地理编码结果字典
        """
        if not lat or not lon:
            return {"success": False, "latitude": lat, "longitude": lon, "error": "Invalid coordinates"}

        with self._counter_lock:
            self._request_count += 1

        # 检查缓存（使用坐标作为键）
        cache_key = f"reverse_{lat:.6f}_{lon:.6f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # 按优先级尝试各API
        for api_name in Config.API_PRIORITY:
            method = getattr(self, f"_reverse_geocode_{api_name}", None)
            if method:
                result = method(lat, lon)
                if result:
                    result.success = True
                    with self._counter_lock:
                        self._success_count += 1
                    result_dict = result.to_dict()
                    # 写入缓存
                    self.cache.set(cache_key, result_dict, self._cache_ttl)
                    return result_dict

        # 所有API都失败
        return {
            "success": False,
            "latitude": lat,
            "longitude": lon,
            "error": "All APIs failed"
        }

    def _reverse_geocode_amap(self, lat: float, lon: float) -> Optional[GeocodeResult]:
        """高德逆地理编码"""
        if not Config.AMAP_KEY:
            return None

        # 转换坐标：WGS-84 -> GCJ-02
        from .coords import wgs84_to_gcj02
        gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)

        start_time = time.time()

        try:
            params = {
                "key": Config.AMAP_KEY,
                "location": f"{gcj_lon},{gcj_lat}",
                "output": "json",
                "radius": "1000",
                "extensions": "base"
            }
            response = self._api_call_with_retry(Config.AMAP_REGEO_URL, params)
            data = response.json()
            time_cost = time.time() - start_time

            if data.get("status") == "1" and data.get("regeocode"):
                regeo = data["regeocode"]
                address_component = regeo.get("addressComponent", {})
                formatted_address = regeo.get("formatted_address", "")

                self.logger.log(
                    address=f"{lat},{lon}",
                    api_name="amap",
                    status="success",
                    latitude=lat,
                    longitude=lon,
                    formatted_address=formatted_address,
                    time_cost=time_cost
                )
                return self._build_result(
                    f"{lat},{lon}",
                    lat, lon,
                    formatted_address,
                    "amap",
                    "WGS-84",
                    province=address_component.get("province"),
                    city=address_component.get("city"),
                    district=address_component.get("district")
                )

            self.logger.log(
                address=f"{lat},{lon}",
                api_name="amap",
                status="failed",
                time_cost=time_cost,
                error_message=data.get("info", "Unknown error")
            )
            return None

        except Exception as e:
            self.logger.log(
                address=f"{lat},{lon}",
                api_name="amap",
                status="error",
                time_cost=time.time() - start_time,
                error_message=str(e)
            )
            return None

    def _reverse_geocode_tianditu(self, lat: float, lon: float) -> Optional[GeocodeResult]:
        """天地图逆地理编码"""
        if not Config.TIANDITU_TK:
            return None

        start_time = time.time()

        try:
            # 天地图逆地理编码参数
            post_str = f'{{"lon":{lon},"lat":{lat},"ver":1}}'
            params = {"postStr": post_str, "type": "geodecode", "tk": Config.TIANDITU_TK}
            response = self._api_call_with_retry(Config.TIANDITU_REGEO_URL, params)
            data = response.json()
            time_cost = time.time() - start_time

            if data.get("status") == "0" and data.get("result"):
                result_data = data["result"]
                formatted_address = result_data.get("formatted_address", "")

                self.logger.log(
                    address=f"{lat},{lon}",
                    api_name="tianditu",
                    status="success",
                    latitude=lat,
                    longitude=lon,
                    formatted_address=formatted_address,
                    time_cost=time_cost
                )
                return self._build_result(
                    f"{lat},{lon}",
                    lat, lon,
                    formatted_address,
                    "tianditu",
                    "CGCS2000",
                    province=result_data.get("province"),
                    city=result_data.get("city"),
                    district=result_data.get("county")
                )

            self.logger.log(
                address=f"{lat},{lon}",
                api_name="tianditu",
                status="failed",
                time_cost=time_cost,
                error_message=data.get("msg", "Unknown error")
            )
            return None

        except Exception as e:
            self.logger.log(
                address=f"{lat},{lon}",
                api_name="tianditu",
                status="error",
                time_cost=time.time() - start_time,
                error_message=str(e)
            )
            return None

    def close(self) -> None:
        """关闭资源"""
        self._session.close()
        self.cache.close()
        self.logger.save()
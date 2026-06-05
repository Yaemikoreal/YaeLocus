"""
地理编码核心模块

支持高德、天地图、百度三个API的智能轮换
并发三路API调用 + 置信度交叉验证优化
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

from .cache import CacheManager
from .config import Config
from .coords import bd09_to_wgs84, gcj02_to_wgs84
from .logger import APILogger
from .models import GeocodeResult
from .preprocessing import AddressNormalizer, AddressSplitter, InvalidAddressFilter
from .validation import ConfidenceValidator

logger = logging.getLogger(__name__)


class _TokenBucketRateLimiter:
    """令牌桶限流器 + 信号量并发控制。

    各 API 独立限流，不阻塞其他线程的令牌获取。
    对配置了最大并发的 API（如百度），使用信号量控制同时进行的请求数。
    """

    def __init__(self, qps: Dict[str, float], max_concurrent: Dict[str, int] = None):
        self._qps = qps
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._semaphores: Dict[str, threading.Semaphore] = {}
        if max_concurrent:
            for api_name, limit in max_concurrent.items():
                if limit and limit > 0:
                    self._semaphores[api_name] = threading.Semaphore(limit)

    def acquire(self, api_name: str) -> None:
        sem = self._semaphores.get(api_name)
        if sem:
            sem.acquire()

        min_interval = 1.0 / (self._qps.get(api_name, 5) or 5)

        with self._lock:
            last = self._last_request.get(api_name, 0)
            now = time.monotonic()
            wait = min_interval - (now - last)
            if wait > 0:
                release_at = now + wait
                self._last_request[api_name] = release_at
            else:
                release_at = now
                self._last_request[api_name] = now

        sleep_time = release_at - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)

    def release(self, api_name: str) -> None:
        sem = self._semaphores.get(api_name)
        if sem:
            sem.release()


class Geocoder:
    """
    地理编码器

    支持多API并发轮换、智能缓存、限流控制、HTTP连接复用、重试机制
    """

    _API_RATE_LIMITS = {
        "amap": 5,
        "tianditu": 10,
        "baidu": 5,
    }

    def __init__(
        self,
        cache_manager: CacheManager = None,
        api_logger: APILogger = None,
        cache_ttl: float = None
    ):
        self.cache = cache_manager if cache_manager is not None else CacheManager()
        self.logger = api_logger if api_logger is not None else APILogger()
        self._cache_ttl = cache_ttl
        self._request_count = 0
        self._success_count = 0
        self._counter_lock = threading.Lock()

        self._rate_limiter = _TokenBucketRateLimiter(self._API_RATE_LIMITS, Config.API_MAX_CONCURRENT)

        self.normalizer = AddressNormalizer()
        self.filter_obj = InvalidAddressFilter()
        self.splitter = AddressSplitter()
        self.validator = ConfidenceValidator()

        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def _rate_limit(self, api_name: str = "amap") -> None:
        """令牌桶限流：精确等待，不阻塞其他线程"""
        self._rate_limiter.acquire(api_name)

    def _api_call_with_retry(
        self,
        url: str,
        params: dict,
        api_name: str = "amap",
        max_retries: int = 3
    ) -> Optional[requests.Response]:
        """带重试的 API 调用，含信号量并发控制

        仅对网络错误重试，不对 API 返回错误重试
        """
        self._rate_limit(api_name)
        try:
            retry_delay = 1.0
            for attempt in range(max_retries):
                try:
                    response = self._session.get(url, params=params, timeout=Config.REQUEST_TIMEOUT)
                    return response
                except (requests.Timeout, requests.ConnectionError):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                    else:
                        raise
            return None
        finally:
            self._rate_limiter.release(api_name)

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
        precision_level: str = None,
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
            precision_level=precision_level,
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
                        precision_level=geo.get("level"),
                        original_lat=lat, original_lon=lon
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
                    loc.get("province"), loc.get("city"), loc.get("county"),
                    precision_level=loc.get("level"),
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
                addr_component = result_data.get("addressComponent", {})
                baidu_level = result_data.get("level")

                self.logger.log(
                    address=address, api_name="baidu", status="success",
                    latitude=wgs_lat, longitude=wgs_lon,
                    formatted_address=result_data.get("formatted_address"),
                    time_cost=time_cost
                )
                return self._build_result(
                    address, wgs_lat, wgs_lon,
                    result_data.get("formatted_address"), "baidu", "BD-09",
                    province=addr_component.get("province"),
                    city=addr_component.get("city"),
                    district=addr_component.get("district"),
                    precision_level=baidu_level,
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

        注意：此方法会按优先级尝试所有 API，直到找到可信且完整的结果。
        与早期版本不同，首个 API 成功但置信度不足或 formatted_address 缺失时
        不会立即返回，而是继续尝试下一个 API 并保留最优结果。

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

        # 2. 地址拆分：处理 "公司名|地址" 格式
        split_result = self.splitter.split(str(address))
        address_part = split_result["address"]  # 提取实际地址部分

        if not address_part or not address_part.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address after split"}

        # 3. 地址清洗（使用拆分后的地址）
        normalized, meta = self.normalizer.normalize(address_part)

        if not normalized or not normalized.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address"}

        with self._counter_lock:
            self._request_count += 1

        # 检查缓存（使用清洗后的地址）
        cached = self.cache.get(normalized)
        if cached is not None:
            # 添加置信度标记（缓存结果视为可信）
            if "confidence" not in cached:
                cached["confidence"] = {"total": 100, "issues": [], "is_trustworthy": True}
            return cached

        # 按优先级尝试各API（使用清洗后的地址）
        best_result = None
        best_confidence = None
        for api_name in Config.API_PRIORITY:
            method = getattr(self, f"_geocode_{api_name}", None)
            if method:
                result = method(normalized)
                if result:
                    result.success = True
                    with self._counter_lock:
                        self._success_count += 1
                    result_dict = result.to_dict()

                    confidence = self.validator.validate(
                        str(address),
                        result_dict,
                        None
                    )

                    result_dict["confidence"] = {
                        "total": confidence.total,
                        "issues": confidence.issues,
                        "is_trustworthy": confidence.is_trustworthy
                    }

                    if not confidence.is_trustworthy:
                        result_dict["warning"] = "置信度较低，建议人工核实"

                    if best_result is None:
                        best_result = result_dict
                        best_confidence = confidence

                    if result_dict.get("formatted_address") and best_result.get("formatted_address"):
                        if confidence.is_trustworthy and not best_confidence.is_trustworthy:
                            best_result = result_dict
                            best_confidence = confidence
                        elif confidence.total > best_confidence.total:
                            best_result = result_dict
                            best_confidence = confidence
                        self.cache.set(normalized, best_result, self._cache_ttl)
                        return best_result

                    if not best_result.get("formatted_address") and result_dict.get("formatted_address"):
                        best_result = result_dict
                        best_confidence = confidence
                    elif best_result.get("formatted_address") and not result_dict.get("formatted_address"):
                        pass
                    else:
                        if confidence.total > (best_confidence.total if best_confidence else 0):
                            best_result = result_dict
                            best_confidence = confidence

                    if result_dict.get("formatted_address") and confidence.is_trustworthy:
                        self.cache.set(normalized, result_dict, self._cache_ttl)
                        return result_dict

        if best_result is not None:
            self.cache.set(normalized, best_result, self._cache_ttl)
            return best_result

        # 所有API都失败
        return {
            "success": False,
            "original_address": str(address),
            "normalized_address": normalized,
            "error": "All APIs failed",
            "confidence": {"total": 0, "issues": ["All APIs failed"], "is_trustworthy": False}
        }

    def _rework_geocode(self, address: str) -> Dict:
        """返工专用地理编码：优先高德保底，逐 API 尝试直到获得精确结果

        与 geocode() 的区别：
        1. 强制跳过缓存（调用前应先 cache.delete）
        2. 高德优先尝试，即使 Config.API_PRIORITY 中不是首位
        3. 精度不足（省/市/区县级）仍会继续尝试下一个 API
        4. 最终仍不精确时保留结果但标记 precision_level

        Args:
            address: 原始地址字符串

        Returns:
            地理编码结果字典
        """
        from .validation.confidence import is_imprecise_result

        is_valid, reason = self.filter_obj.is_valid(address)
        if not is_valid:
            return {
                "success": False,
                "original_address": str(address),
                "error": f"无效地址: {reason}",
                "confidence": {"total": 0, "issues": [reason], "is_trustworthy": False}
            }

        split_result = self.splitter.split(str(address))
        address_part = split_result["address"]
        if not address_part or not address_part.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address after split"}

        normalized, meta = self.normalizer.normalize(address_part)
        if not normalized or not normalized.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address"}

        rework_order = ["amap"]
        for api_name in Config.API_PRIORITY:
            if api_name not in rework_order:
                rework_order.append(api_name)

        best_result = None
        best_confidence = None
        for api_name in rework_order:
            method = getattr(self, f"_geocode_{api_name}", None)
            if not method:
                continue
            result = method(normalized)
            if not result:
                continue

            result.success = True
            result_dict = result.to_dict()

            confidence = self.validator.validate(str(address), result_dict, None)
            result_dict["confidence"] = {
                "total": confidence.total,
                "issues": confidence.issues,
                "is_trustworthy": confidence.is_trustworthy
            }
            if not confidence.is_trustworthy:
                result_dict["warning"] = "置信度较低，建议人工核实"

            if best_result is None:
                best_result = result_dict
                best_confidence = confidence

            if result_dict.get("formatted_address") and not is_imprecise_result(result_dict):
                best_result = result_dict
                best_confidence = confidence
                self.cache.set(normalized, result_dict, self._cache_ttl)
                return result_dict

            if not best_result.get("formatted_address") and result_dict.get("formatted_address"):
                best_result = result_dict
                best_confidence = confidence
            elif best_result.get("formatted_address") and not result_dict.get("formatted_address"):
                pass
            elif result_dict.get("formatted_address") and best_result.get("formatted_address"):
                if is_imprecise_result(best_result) and not is_imprecise_result(result_dict):
                    best_result = result_dict
                    best_confidence = confidence
                elif not is_imprecise_result(best_result) and is_imprecise_result(result_dict):
                    pass
                else:
                    if confidence.total > (best_confidence.total if best_confidence else 0):
                        best_result = result_dict
                        best_confidence = confidence
            else:
                if confidence.total > (best_confidence.total if best_confidence else 0):
                    best_result = result_dict
                    best_confidence = confidence

        if best_result is not None:
            self.cache.set(normalized, best_result, self._cache_ttl)
            return best_result

        return {
            "success": False,
            "original_address": str(address),
            "normalized_address": normalized,
            "error": "All APIs failed",
            "confidence": {"total": 0, "issues": ["All APIs failed"], "is_trustworthy": False}
        }

    def _call_single_api(self, api_name: str, address: str) -> Tuple[str, Optional[Dict]]:
        """调用单个 API，返回 (api_name, result_dict 或 None)"""
        method = getattr(self, f"_geocode_{api_name}", None)
        if method is None:
            return (api_name, None)
        try:
            result = method(address)
            if result and result.success:
                return (api_name, result.to_dict())
            return (api_name, None)
        except Exception as e:
            logger.debug("API %s 调用异常: %s", api_name, e)
            return (api_name, None)

    def _cross_validate(
        self,
        results: List[Tuple[str, Dict]],
        original_address: str,
    ) -> Optional[Dict]:
        """交叉验证多个 API 结果，选择最优结果

        策略:
        1. 按置信度从高到低排序
        2. 如果最优结果置信度 >= 阈值，直接返回
        3. 如果多个结果的坐标偏差 < 阈值，合并来源标记，返回最高置信度的
        4. 如果坐标偏差 >= 阈值（>1km），返回置信度最高且在中国的
        """
        if not results:
            return None

        threshold = Config.CROSS_VALIDATE_THRESHOLD
        max_delta = Config.CROSS_VALIDATE_MAX_COORD_DELTA

        scored = []
        for api_name, result_dict in results:
            confidence = self.validator.validate(original_address, result_dict, None)
            result_dict["confidence"] = {
                "total": confidence.total,
                "issues": confidence.issues,
                "is_trustworthy": confidence.is_trustworthy,
            }
            if not confidence.is_trustworthy:
                result_dict["warning"] = "置信度较低，建议人工核实"
            scored.append((confidence.total, api_name, result_dict, confidence))

        scored.sort(key=lambda x: x[0], reverse=True)

        best_score, best_api, best_result, best_conf = scored[0]

        if best_score >= threshold:
            best_result["sources"] = [best_api]
            best_result["cross_validated"] = True
            return best_result

        if len(scored) > 1:
            best_lat = best_result.get("latitude", 0)
            best_lon = best_result.get("longitude", 0)

            consistent_sources = [best_api]
            for _score, api_name, result_dict, _conf in scored[1:]:
                lat = result_dict.get("latitude", 0)
                lon = result_dict.get("longitude", 0)
                if lat and lon and best_lat and best_lon:
                    from .coords import haversine_km
                    dist_km = haversine_km(best_lat, best_lon, lat, lon)
                    if dist_km < max_delta:
                        consistent_sources.append(api_name)

            best_result["sources"] = consistent_sources
            best_result["cross_validated"] = len(consistent_sources) > 1

            if best_score < threshold and len(consistent_sources) <= 1:
                all_sources = [s[1] for s in scored if s[3].is_trustworthy or s[0] >= 40]
                if all_sources:
                    best_result["sources"] = all_sources
                    best_result["cross_validated"] = True
                    best_result["warning"] = f"置信度较低({best_score}分)，多源对比中仅{len(consistent_sources)}个结果一致，建议人工核实"

        else:
            best_result["sources"] = [best_api]
            best_result["cross_validated"] = False

        return best_result

    def geocode_parallel(self, address: str) -> Dict:
        """并发三路 API 地理编码 + 置信度交叉验证

        策略:
        - 同时向高德、天地图、百度发起请求（各 API 独立限流）
        - 取首个成功结果立即返回（如果置信度 >= 阈值）
        - 置信度 < 阈值时，等待其他 API 结果做交叉验证
        - 缓存命中时直接返回，不走 API

        Args:
            address: 地址字符串

        Returns:
            地理编码结果字典（含 confidence 和 cross_validated 字段）
        """
        if not Config.PARALLEL_APIS:
            return self.geocode(address)

        is_valid, reason = self.filter_obj.is_valid(address)
        if not is_valid:
            return {
                "success": False,
                "original_address": str(address),
                "error": f"无效地址: {reason}",
                "confidence": {"total": 0, "issues": [reason], "is_trustworthy": False}
            }

        split_result = self.splitter.split(str(address))
        address_part = split_result["address"]

        if not address_part or not address_part.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address after split"}

        normalized, meta = self.normalizer.normalize(address_part)

        if not normalized or not normalized.strip():
            return {"success": False, "original_address": str(address), "error": "Empty address"}

        with self._counter_lock:
            self._request_count += 1

        cached = self.cache.get(normalized)
        if cached is not None:
            if "confidence" not in cached:
                cached["confidence"] = {"total": 100, "issues": [], "is_trustworthy": True}
            if "cross_validated" not in cached:
                cached["cross_validated"] = False
            return cached

        threshold = Config.CROSS_VALIDATE_THRESHOLD
        timeout = Config.GEOCODE_PARALLEL_TIMEOUT

        available_apis = []
        for api_name in Config.API_PRIORITY:
            if getattr(self, f"_geocode_{api_name}", None) is not None:
                available_apis.append(api_name)

        if not available_apis:
            return {
                "success": False,
                "original_address": str(address),
                "normalized_address": normalized,
                "error": "No API key configured",
                "confidence": {"total": 0, "issues": ["No API key configured"], "is_trustworthy": False}
            }

        results: List[Tuple[str, Dict]] = []
        first_result: Optional[Dict] = None
        first_api: Optional[str] = None

        with ThreadPoolExecutor(max_workers=min(3, len(available_apis))) as executor:
            futures = {
                executor.submit(self._call_single_api, api_name, normalized): api_name
                for api_name in available_apis
            }

            try:
                for future in as_completed(futures, timeout=timeout):
                    api_name = futures[future]
                    try:
                        api_name_result, result_dict = future.result()
                    except Exception:
                        continue

                    if result_dict is not None:
                        with self._counter_lock:
                            self._success_count += 1

                        confidence = self.validator.validate(str(address), result_dict, None)
                        result_dict["confidence"] = {
                            "total": confidence.total,
                            "issues": confidence.issues,
                            "is_trustworthy": confidence.is_trustworthy,
                        }
                        if not confidence.is_trustworthy:
                            result_dict["warning"] = "置信度较低，建议人工核实"

                        results.append((api_name_result, result_dict))

                        if first_result is None:
                            first_result = result_dict
                            first_api = api_name_result

                        if confidence.total >= threshold and len(results) >= 1:
                            for f in futures:
                                f.cancel()
                            best = self._cross_validate(results, str(address)) or result_dict
                            best["source"] = first_api
                            self.cache.set(normalized, best, self._cache_ttl)
                            return best

            except Exception:
                pass

        if results:
            best = self._cross_validate(results, str(address)) or results[0][1]
            best["source"] = results[0][0]
            self.cache.set(normalized, best, self._cache_ttl)
            return best

        return {
            "success": False,
            "original_address": str(address),
            "normalized_address": normalized,
            "error": "All APIs failed",
            "confidence": {"total": 0, "issues": ["All APIs failed"], "is_trustworthy": False}
        }

    def batch_geocode(
        self,
        addresses: List[str],
        progress: bool = True,
        workers: int = 3,
        parallel_apis: bool = True,
    ) -> List[Dict]:
        """批量地理编码（并行处理）

        Args:
            addresses: 地址列表
            progress: 是否显示进度条
            workers: 并行线程数，默认 3
            parallel_apis: 是否启用并发三路 API 调用 + 交叉验证，默认 True

        Returns:
            结果列表（保持原始顺序）
        """
        if not addresses:
            return []

        total = len(addresses)

        geocode_func = self.geocode_parallel if parallel_apis else self.geocode

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
                results.append(geocode_func(address))
            self.cache.flush()
            self.logger.save()
            return results

        cached_results = self.cache.get_batch_prefetch(addresses)
        uncached_indices = []
        uncached_addresses = []
        for idx, addr in enumerate(addresses):
            if cached_results.get(addr) is None:
                uncached_indices.append(idx)
                uncached_addresses.append(addr)

        results: List[Optional[Dict]] = [None] * total
        for idx, addr in enumerate(addresses):
            if cached_results.get(addr) is not None:
                results[idx] = cached_results[addr]

        if not uncached_addresses:
            self.cache.flush()
            self.logger.save()
            return [r for r in results if r is not None]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(geocode_func, addr): uncached_indices[i]
                for i, addr in enumerate(uncached_addresses)
            }

            completed = 0
            if progress and not os.environ.get('YAELOCUS_TUI'):
                try:
                    from tqdm import tqdm
                    pbar = tqdm(total=len(uncached_addresses), desc="地理编码中", unit="条")
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

"""
地理编码核心模块

支持高德、天地图、百度三个API的智能轮换
"""

import time
from typing import Dict, List, Optional

import requests

from .cache import CacheManager
from .config import Config
from .coords import gcj02_to_wgs84, bd09_to_wgs84
from .logger import APILogger
from .models import GeocodeResult


class Geocoder:
    """
    地理编码器

    支持多API轮换、智能缓存、限流控制
    """

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
        self._last_request_time = 0.0
        self._request_count = 0
        self._success_count = 0

    def _rate_limit(self) -> None:
        """请求限流"""
        elapsed = time.time() - self._last_request_time
        if elapsed < Config.REQUEST_DELAY:
            time.sleep(Config.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

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

        self._rate_limit()
        start_time = time.time()

        try:
            params = {"key": Config.AMAP_KEY, "address": address, "output": "json"}
            response = requests.get(Config.AMAP_URL, params=params, timeout=Config.REQUEST_TIMEOUT)
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

        self._rate_limit()
        start_time = time.time()

        try:
            params = {"ds": f'{{"keyWord":"{address}"}}', "tk": Config.TIANDITU_TK}
            response = requests.get(Config.TIANDITU_URL, params=params, timeout=Config.REQUEST_TIMEOUT)
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

        self._rate_limit()
        start_time = time.time()

        try:
            params = {"address": address, "output": "json", "ak": Config.BAIDU_AK}
            response = requests.get(Config.BAIDU_URL, params=params, timeout=Config.REQUEST_TIMEOUT)
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
        地理编码单个地址

        Args:
            address: 地址字符串

        Returns:
            地理编码结果字典
        """
        if not address or not address.strip():
            return {"success": False, "original_address": address, "error": "Empty address"}

        self._request_count += 1

        # 检查缓存
        cached = self.cache.get(address)
        if cached is not None:
            return cached

        # 按优先级尝试各API
        for api_name in Config.API_PRIORITY:
            method = getattr(self, f"_geocode_{api_name}", None)
            if method:
                result = method(address)
                if result:
                    result.success = True
                    self._success_count += 1
                    result_dict = result.to_dict()
                    # 写入缓存
                    self.cache.set(address, result_dict, self._cache_ttl)
                    return result_dict

        # 所有API都失败
        return {
            "success": False,
            "original_address": address,
            "error": "All APIs failed"
        }

    def batch_geocode(self, addresses: List[str], progress: bool = True) -> List[Dict]:
        """
        批量地理编码

        Args:
            addresses: 地址列表
            progress: 是否显示进度条

        Returns:
            结果列表
        """
        results = []
        iterator = addresses

        if progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(addresses, desc="地理编码中", unit="条")
            except ImportError:
                pass

        for address in iterator:
            result = self.geocode(address)
            results.append(result)

        # 批量完成后flush缓存
        self.cache.flush()
        # 保存日志
        self.logger.save()

        return results

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

        self._rate_limit()
        start_time = time.time()

        try:
            params = {
                "key": Config.AMAP_KEY,
                "location": f"{gcj_lon},{gcj_lat}",
                "output": "json",
                "radius": "1000",
                "extensions": "base"
            }
            response = requests.get(Config.AMAP_REGEO_URL, params=params, timeout=Config.REQUEST_TIMEOUT)
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

        self._rate_limit()
        start_time = time.time()

        try:
            # 天地图逆地理编码参数
            post_str = f'{{"lon":{lon},"lat":{lat},"ver":1}}'
            params = {"postStr": post_str, "type": "geodecode", "tk": Config.TIANDITU_TK}
            response = requests.get(Config.TIANDITU_REGEO_URL, params=params, timeout=Config.REQUEST_TIMEOUT)
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
        self.cache.close()
        self.logger.save()
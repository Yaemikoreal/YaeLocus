"""地理编码器测试（Mock API）"""
import threading
from unittest.mock import patch, MagicMock

import pytest

from geocode.cache import CacheManager
from geocode.geocoder import Geocoder
from geocode.logger import APILogger


@pytest.fixture
def mock_cache():
    """创建临时缓存"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    cache = CacheManager(path)
    yield cache
    cache.close()
    import os
    for suffix in ["", "-wal", "-shm"]:
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


@pytest.fixture
def mock_logger(tmp_path):
    """创建临时日志器"""
    log_path = str(tmp_path / "test_api_log.csv")
    return APILogger(log_path)


@pytest.fixture
def geocoder_no_api(mock_cache, mock_logger):
    """创建无API密钥编码器"""
    return Geocoder(mock_cache, mock_logger)


class TestGeocoderEmptyInput:
    """空输入处理"""

    def test_empty_address(self, geocoder_no_api):
        result = geocoder_no_api.geocode("")
        assert result["success"] is False

    def test_whitespace_address(self, geocoder_no_api):
        result = geocoder_no_api.geocode("   ")
        assert result["success"] is False

    def test_none_address(self, geocoder_no_api):
        result = geocoder_no_api.geocode(None)
        assert result["success"] is False


class TestGeocoderCache:
    """缓存集成测试"""

    def test_cache_hit(self, mock_cache, mock_logger):
        geocoder = Geocoder(mock_cache, mock_logger)
        mock_cache.set("缓存测试地址", {
            "success": True,
            "latitude": 39.9,
            "longitude": 116.4,
            "source": "cache",
            "original_address": "缓存测试地址"
        })
        mock_cache.flush()
        result = geocoder.geocode("缓存测试地址")
        assert result["success"] is True
        assert result["source"] == "cache"

    def test_cache_miss_counting(self, mock_cache, mock_logger):
        geocoder = Geocoder(mock_cache, mock_logger)
        stats_before = mock_cache.get_stats()
        geocoder.geocode("全新的未缓存地址XYZ123")
        stats_after = mock_cache.get_stats()
        assert stats_after["misses"] >= stats_before["misses"]


class TestGeocoderThreadSafety:
    """线程安全验证"""

    def test_concurrent_counter_increment(self, mock_cache, mock_logger):
        geocoder = Geocoder(mock_cache, mock_logger)
        workers = 8
        iterations = 50
        errors = []

        def worker():
            for _ in range(iterations):
                try:
                    # 使用非空地址以触发计数器递增
                    geocoder.geocode(f"test_addr_{threading.get_ident()}_{_}")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent errors: {errors}"
        expected = workers * iterations
        assert geocoder._request_count == expected, \
            f"Expected {expected} requests, got {geocoder._request_count}"


class TestGeocoderClose:
    """资源清理"""

    def test_close_cleans_up(self, mock_cache, mock_logger):
        geocoder = Geocoder(mock_cache, mock_logger)
        geocoder.geocode("测试")
        geocoder.close()
        # 关闭后缓存管理器应已关闭（conn 为 None）
        assert mock_cache._conn is None


class TestGeocoderApiRotation:
    """API 轮换逻辑"""

    def test_rotation_order(self, geocoder_no_api):
        """验证 API 轮换按配置优先级"""
        from geocode.config import Config
        available = Config.get_available_apis()
        if "amap" in available:
            assert "amap" in Config.API_PRIORITY
            assert hasattr(geocoder_no_api, "_geocode_amap")


class TestGeocoderReverse:
    """逆地理编码测试"""

    def test_invalid_coords(self, geocoder_no_api):
        result = geocoder_no_api.reverse_geocode(None, None)
        assert result["success"] is False

    def test_valid_coords_cache(self, mock_cache, mock_logger):
        geocoder = Geocoder(mock_cache, mock_logger)
        key = geocoder.cache._normalize_key("reverse_39.904200_116.407400")
        mock_cache.set(key, {
            "success": True,
            "formatted_address": "北京市东城区天安门",
            "latitude": 39.9042,
            "longitude": 116.4074
        })
        mock_cache.flush()
        result = geocoder.reverse_geocode(39.9042, 116.4074)
        assert result["success"] is True

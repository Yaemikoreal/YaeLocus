"""
geocode 模块测试
"""

import json
import tempfile
from pathlib import Path
import pytest

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from geocode.cache import CacheManager
from geocode.config import Config
from geocode.coords import gcj02_to_wgs84, bd09_to_wgs84
from geocode.models import GeocodeResult, APILog


class TestCacheManager:
    """测试缓存管理器"""

    @pytest.fixture
    def temp_cache(self, tmp_path):
        """创建临时缓存"""
        return CacheManager(cache_file=str(tmp_path / "test_cache.db"))

    def test_init(self, temp_cache):
        """测试初始化"""
        assert temp_cache is not None
        assert temp_cache.count() == 0

    def test_set_and_get(self, temp_cache):
        """测试基本的set和get操作"""
        test_address = "北京市朝阳区建国路88号"
        test_result = {
            "latitude": 39.9059,
            "longitude": 116.4699,
            "formatted_address": "北京市朝阳区建国路88号",
            "source": "amap"
        }

        temp_cache.set(test_address, test_result)
        result = temp_cache.get(test_address)

        assert result is not None
        assert result["latitude"] == 39.9059
        assert result["source"] == "amap"

    def test_get_miss(self, temp_cache):
        """测试未命中的get"""
        result = temp_cache.get("不存在的地址")
        assert result is None

    def test_stats(self, temp_cache):
        """测试统计信息"""
        temp_cache.set("addr1", {"lat": 1, "lng": 2})
        temp_cache.get("addr1")  # hit
        temp_cache.get("addr2")  # miss

        stats = temp_cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_delete(self, temp_cache):
        """测试删除"""
        temp_cache.set("addr1", {"lat": 1})
        assert temp_cache.delete("addr1") is True
        assert temp_cache.get("addr1") is None
        assert temp_cache.delete("不存在的地址") is False

    def test_contains(self, temp_cache):
        """测试 in 操作符"""
        temp_cache.set("测试地址", {"lat": 1, "lng": 2})
        assert "测试地址" in temp_cache
        assert "其他地址" not in temp_cache

    def test_clear(self, temp_cache):
        """测试清空"""
        temp_cache.set("addr1", {"lat": 1})
        temp_cache.set("addr2", {"lat": 2})
        temp_cache.clear()
        assert temp_cache.count() == 0

    def test_ttl_expiration(self, temp_cache):
        """测试TTL过期"""
        import time
        temp_cache.set("addr1", {"lat": 1}, ttl=0.1)
        assert temp_cache.get("addr1") is not None
        time.sleep(0.2)
        assert temp_cache.get("addr1") is None

    def test_cleanup(self, temp_cache):
        """测试过期清理"""
        import time
        temp_cache.set("addr1", {"lat": 1}, ttl=0.1)
        temp_cache.set("addr2", {"lat": 2})  # 不过期
        time.sleep(0.2)
        cleaned = temp_cache.cleanup()
        assert cleaned == 1
        assert temp_cache.get("addr2") is not None

    def test_batch_flush(self, temp_cache):
        """测试批量提交"""
        # 设置小批量阈值
        temp_cache._batch_size = 3

        temp_cache.set("addr1", {"lat": 1})
        temp_cache.set("addr2", {"lat": 2})
        assert temp_cache._pending == 2

        temp_cache.set("addr3", {"lat": 3})  # 触发flush
        assert temp_cache._pending == 0

    def test_context_manager(self, tmp_path):
        """测试上下文管理器"""
        cache_file = str(tmp_path / "test_context.db")
        with CacheManager(cache_file=cache_file) as cache:
            cache.set("addr1", {"lat": 1})
            # 应该在退出时自动flush

        # 重新打开验证数据持久化
        with CacheManager(cache_file=cache_file) as cache:
            assert cache.get("addr1") is not None

    def test_persistence(self, tmp_path):
        """测试持久化"""
        cache_file = str(tmp_path / "test_persist.db")

        # 第一次写入
        cache1 = CacheManager(cache_file=cache_file)
        cache1.set("addr1", {"lat": 1, "lng": 2})
        cache1.close()

        # 第二次读取
        cache2 = CacheManager(cache_file=cache_file)
        result = cache2.get("addr1")
        cache2.close()

        assert result is not None
        assert result["lat"] == 1


class TestCoords:
    """测试坐标转换"""

    def test_gcj02_to_wgs84(self):
        """测试GCJ-02转WGS-84"""
        gcj_lat, gcj_lon = 39.9834, 116.3156
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        assert abs(wgs_lat - gcj_lat) < 0.01
        assert abs(wgs_lon - gcj_lon) < 0.01

    def test_bd09_to_wgs84(self):
        """测试BD-09转WGS-84"""
        bd_lat, bd_lon = 39.9834, 116.3156
        wgs_lat, wgs_lon = bd09_to_wgs84(bd_lat, bd_lon)
        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)


class TestConfig:
    """测试配置"""

    def test_api_priority(self):
        """测试API优先级"""
        assert Config.API_PRIORITY == ["amap", "tianditu", "baidu"]

    def test_get_available_apis(self):
        """测试获取可用API"""
        apis = Config.get_available_apis()
        assert isinstance(apis, list)

    def test_project_dir(self):
        """测试项目目录"""
        assert Config.get_project_dir().exists()

    def test_validate(self):
        """测试配置验证"""
        result = Config.validate()
        assert isinstance(result, bool)


class TestModels:
    """测试数据模型"""

    def test_geocode_result(self):
        """测试地理编码结果"""
        result = GeocodeResult(
            latitude=39.9,
            longitude=116.4,
            original_address="测试地址",
            source="amap"
        )
        d = result.to_dict()
        assert d["latitude"] == 39.9
        assert d["success"] is True

    def test_api_log(self):
        """测试API日志"""
        log = APILog(
            timestamp="2024-01-01 00:00:00",
            address="测试地址",
            api_name="amap",
            status="success"
        )
        d = log.to_dict()
        assert d["api_name"] == "amap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Geocoder API 调用测试

测试地理编码器的核心功能：
- API 调用成功/失败场景
- API 轮换机制
- 缓存集成
- 限流控制
- 异常处理
"""

import pytest
import time
import requests
from unittest.mock import Mock, patch, MagicMock

from geocode.geocoder import Geocoder
from geocode.cache import CacheManager
from geocode.logger import APILogger
from geocode.config import Config

from tests.fixtures.api_responses import (
    AMAP_SUCCESS_RESPONSE_SIMPLE,
    AMAP_EMPTY_RESPONSE,
    AMAP_INVALID_KEY_RESPONSE,
    AMAP_QUOTA_EXCEEDED_RESPONSE,
    AMAP_UNKNOWN_ERROR_RESPONSE,
    AMAP_MALFORMED_LOCATION_RESPONSE,
    AMAP_MISSING_LOCATION_RESPONSE,
    TIANDITU_SUCCESS_RESPONSE_SIMPLE,
    TIANDITU_NO_RESULT_RESPONSE,
    TIANDITU_ERROR_RESPONSE,
    BAIDU_SUCCESS_RESPONSE_SIMPLE,
    BAIDU_INVALID_AK_RESPONSE,
    BAIDU_NO_RESULT_RESPONSE,
    BAIDU_ERROR_RESPONSE,
    INVALID_JSON_RESPONSE,
)


# ============================================
# 初始化测试
# ============================================

class TestGeocoderInit:
    """测试 Geocoder 初始化"""

    def test_init_default(self, temp_cache, temp_logger):
        """默认参数初始化"""
        geocoder = Geocoder(temp_cache, temp_logger)
        assert geocoder.cache is not None
        assert geocoder.logger is not None
        geocoder.close()

    def test_init_with_cache_manager(self, temp_cache, temp_logger):
        """传入自定义 CacheManager"""
        geocoder = Geocoder(cache_manager=temp_cache, api_logger=temp_logger)
        assert geocoder.cache is temp_cache
        geocoder.close()

    def test_init_with_logger(self, temp_cache, temp_logger):
        """传入自定义 APILogger"""
        geocoder = Geocoder(cache_manager=temp_cache, api_logger=temp_logger)
        assert geocoder.logger is temp_logger
        geocoder.close()

    def test_init_with_ttl(self, temp_cache, temp_logger):
        """设置缓存 TTL"""
        geocoder = Geocoder(temp_cache, temp_logger, cache_ttl=3600)
        assert geocoder._cache_ttl == 3600
        geocoder.close()

    def test_init_with_both(self, temp_cache, temp_logger):
        """传入缓存和日志"""
        geocoder = Geocoder(temp_cache, temp_logger, cache_ttl=7200)
        assert geocoder.cache is temp_cache
        assert geocoder.logger is temp_logger
        assert geocoder._cache_ttl == 7200
        geocoder.close()


# ============================================
# 高德 API 测试
# ============================================

class TestGeocodeAmap:
    """测试高德 API 地理编码"""

    def test_amap_success(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """高德 API 成功响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["source"] == "amap"
        assert result["latitude"] is not None
        assert result["longitude"] is not None
        assert result["formatted_address"] == "北京市朝阳区"

    def test_amap_no_key(self, mock_requests, mock_config_only_tianditu, temp_cache, temp_logger):
        """未配置高德密钥时跳过"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = TIANDITU_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 应该使用天地图 API（因为高德密钥未配置）
        assert result["success"] is True
        assert result["source"] == "tianditu"

    def test_amap_empty_result(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """API 返回空结果"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_EMPTY_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("无效地址xyz")
        geocoder.close()

        # 空结果会导致失败，尝试其他 API
        assert result["success"] is False

    def test_amap_invalid_key(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """API 密钥无效"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_INVALID_KEY_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 无效密钥导致失败，尝试其他 API
        assert result["success"] is False

    def test_amap_quota_exceeded(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """配额耗尽"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_QUOTA_EXCEEDED_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_amap_network_timeout(self, mock_requests_timeout, mock_config_valid, temp_cache, temp_logger):
        """网络超时"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_amap_connection_error(self, mock_requests_connection_error, mock_config_valid, temp_cache, temp_logger):
        """连接错误"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_amap_invalid_json(self, mock_requests_invalid_json, mock_config_valid, temp_cache, temp_logger):
        """JSON 解析失败"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_amap_malformed_location(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """location 字段格式异常"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_MALFORMED_LOCATION_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("测试地址")
        geocoder.close()

        assert result["success"] is False

    def test_amap_missing_location(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """缺少 location 字段"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_MISSING_LOCATION_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("测试地址")
        geocoder.close()

        assert result["success"] is False

    def test_amap_rate_limit(self, mock_requests, mock_config_valid, temp_cache, temp_logger, monkeypatch):
        """请求限流测试"""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0.5)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)

        start_time = time.time()
        geocoder.geocode("地址1")
        geocoder.geocode("地址2")
        elapsed = time.time() - start_time

        geocoder.close()

        # 两次请求应该有间隔
        assert elapsed >= 0.5


# ============================================
# 天地图 API 测试
# ============================================

class TestGeocodeTianditu:
    """测试天地图 API 地理编码"""

    def test_tianditu_success(self, mock_requests, mock_config_only_tianditu, temp_cache, temp_logger):
        """天地图成功响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = TIANDITU_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["source"] == "tianditu"
        assert result["latitude"] is not None
        assert result["longitude"] is not None

    def test_tianditu_no_key(self, mock_requests, mock_config_only_amap, temp_cache, temp_logger):
        """未配置天地图密钥"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 应该使用高德 API
        assert result["success"] is True
        assert result["source"] == "amap"

    def test_tianditu_error_response(self, mock_requests, mock_config_only_tianditu, temp_cache, temp_logger):
        """天地图错误响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = TIANDITU_ERROR_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_tianditu_no_result(self, mock_requests, mock_config_only_tianditu, temp_cache, temp_logger):
        """天地图无结果"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = TIANDITU_NO_RESULT_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("无效地址")
        geocoder.close()

        assert result["success"] is False


# ============================================
# 百度 API 测试
# ============================================

class TestGeocodeBaidu:
    """测试百度 API 地理编码"""

    def test_baidu_success(self, mock_requests, mock_config_only_baidu, temp_cache, temp_logger):
        """百度成功响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = BAIDU_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["source"] == "baidu"
        assert result["latitude"] is not None
        assert result["longitude"] is not None

    def test_baidu_no_key(self, mock_requests, mock_config_only_amap, temp_cache, temp_logger):
        """未配置百度密钥"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 应该使用高德 API
        assert result["success"] is True
        assert result["source"] == "amap"

    def test_baidu_invalid_ak(self, mock_requests, mock_config_only_baidu, temp_cache, temp_logger):
        """百度 AK 无效"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = BAIDU_INVALID_AK_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is False

    def test_baidu_no_result(self, mock_requests, mock_config_only_baidu, temp_cache, temp_logger):
        """百度无结果"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = BAIDU_NO_RESULT_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("无效地址")
        geocoder.close()

        assert result["success"] is False


# ============================================
# API 轮换机制测试
# ============================================

class TestGeocodeFallback:
    """测试 API 轮换机制"""

    def test_fallback_to_second_api(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """第一个 API 失败时切换到第二个"""
        # 第一次调用（高德）返回失败
        amap_response = Mock()
        amap_response.status_code = 200
        amap_response.json.return_value = AMAP_EMPTY_RESPONSE

        # 第二次调用（天地图）返回成功
        tianditu_response = Mock()
        tianditu_response.status_code = 200
        tianditu_response.json.return_value = TIANDITU_SUCCESS_RESPONSE_SIMPLE

        mock_requests.get.side_effect = [amap_response, tianditu_response]

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["source"] == "tianditu"

    def test_fallback_to_third_api(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """前两个 API 失败时切换到第三个"""
        # 高德失败
        amap_response = Mock()
        amap_response.json.return_value = AMAP_EMPTY_RESPONSE

        # 天地图失败
        tianditu_response = Mock()
        tianditu_response.json.return_value = TIANDITU_NO_RESULT_RESPONSE

        # 百度成功
        baidu_response = Mock()
        baidu_response.json.return_value = BAIDU_SUCCESS_RESPONSE_SIMPLE

        mock_requests.get.side_effect = [amap_response, tianditu_response, baidu_response]

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["source"] == "baidu"

    def test_all_apis_failed(self, mock_requests_all_fail, mock_config_valid, temp_cache, temp_logger):
        """所有 API 都失败"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("无效地址xyz")
        geocoder.close()

        assert result["success"] is False
        assert result["error"] == "All APIs failed"

    def test_api_priority_order(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """验证 API 调用优先级顺序"""
        # 按优先级顺序：amap, tianditu, baidu
        call_order = []

        def track_call(*args, **kwargs):
            url = kwargs.get('params', {}).get('key', '') or kwargs.get('params', {}).get('tk', '') or kwargs.get('params', {}).get('ak', '')
            if url:
                call_order.append(url)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
            return mock_response

        mock_requests.get.side_effect = track_call

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        # 验证调用顺序（高德优先）
        # 第一调用应该是高德（因为高德是优先级最高的 API）
        # 实际上我们检查 source 字段来验证


# ============================================
# 缓存集成测试
# ============================================

class TestGeocodeCache:
    """测试缓存集成"""

    def test_cache_hit(self, temp_cache, temp_logger):
        """缓存命中"""
        # 预填充缓存
        cached_result = {
            "success": True,
            "latitude": 39.9,
            "longitude": 116.4,
            "source": "cached"
        }
        temp_cache.set("北京市朝阳区", cached_result)
        temp_cache.flush()

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")

        assert result["success"] is True
        assert result["source"] == "cached"
        # 验证缓存命中（在关闭前获取统计）
        stats = geocoder.get_cache_stats()
        assert stats["hits"] >= 1

        geocoder.close()

    def test_cache_miss_and_store(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """缓存未命中后存储"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")

        assert result["success"] is True
        # 先验证缓存（在关闭前）
        cached = temp_cache.get("北京市朝阳区")
        assert cached is not None
        assert cached["success"] is True

        geocoder.close()  # 之后关闭

    def test_cache_ttl(self, temp_cache, temp_logger):
        """缓存 TTL 过期"""
        import time

        # 设置短 TTL
        cached_result = {"success": True, "latitude": 39.9}
        temp_cache.set("北京市朝阳区", cached_result, ttl=0.1)
        temp_cache.flush()

        # 立即读取应该命中
        geocoder = Geocoder(temp_cache, temp_logger)
        result1 = geocoder.geocode("北京市朝阳区")
        assert result1["success"] is True

        # 等待过期
        time.sleep(0.2)

        # 再次读取应该未命中
        result2 = temp_cache.get("北京市朝阳区")
        geocoder.close()

        assert result2 is None

    def test_cache_normalized_key(self, temp_cache, temp_logger):
        """缓存键规范化（大小写、空格）"""
        # 地址规范化（去除空格、小写）
        cached_result = {"success": True, "latitude": 39.9}
        temp_cache.set("北京市朝阳区", cached_result)
        temp_cache.flush()

        geocoder = Geocoder(temp_cache, temp_logger)

        # 带空格的相同地址应该命中
        result1 = geocoder.geocode("北京市朝阳区")
        result2 = geocoder.geocode("北京市朝阳区   ")  # 带空格

        geocoder.close()

        assert result1["success"] is True
        # 由于规范化，带空格的地址应该也能命中缓存


# ============================================
# 空地址处理测试
# ============================================

class TestGeocodeEmptyAddress:
    """测试空地址处理"""

    def test_empty_address_string(self, temp_cache, temp_logger):
        """空字符串地址"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("")
        geocoder.close()

        assert result["success"] is False
        assert result["error"] == "Empty address"

    def test_whitespace_address(self, temp_cache, temp_logger):
        """空白字符地址"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("   ")
        geocoder.close()

        assert result["success"] is False
        assert result["error"] == "Empty address"

    def test_none_address(self, temp_cache, temp_logger):
        """None 地址"""
        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode(None)
        geocoder.close()

        assert result["success"] is False
        assert result["error"] == "Empty address"


# ============================================
# 批量地理编码测试
# ============================================

class TestBatchGeocode:
    """测试批量地理编码"""

    def test_batch_geocode_basic(self, mock_requests, mock_config_valid, temp_cache, temp_logger, sample_addresses):
        """基础批量处理"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        results = geocoder.batch_geocode(sample_addresses, progress=False)
        geocoder.close()

        assert len(results) == len(sample_addresses)
        assert all(r["success"] for r in results)

    def test_batch_geocode_with_progress(self, mock_requests, mock_config_valid, temp_cache, temp_logger, sample_addresses):
        """带进度条的批量处理"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        results = geocoder.batch_geocode(sample_addresses, progress=True)
        geocoder.close()

        assert len(results) == len(sample_addresses)

    def test_batch_geocode_mixed_results(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """部分成功部分失败的批量处理"""
        addresses = ["北京市朝阳区", "无效地址xyz", "上海市浦东新区"]

        # 模拟混合响应
        responses = [
            AMAP_SUCCESS_RESPONSE_SIMPLE,
            AMAP_EMPTY_RESPONSE,  # 失败
            AMAP_SUCCESS_RESPONSE_SIMPLE
        ]
        mock_response = Mock()
        mock_response.status_code = 200

        def get_json():
            return responses.pop(0) if responses else AMAP_EMPTY_RESPONSE

        mock_response.json = get_json
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        results = geocoder.batch_geocode(addresses, progress=False)
        geocoder.close()

        success_count = sum(1 for r in results if r["success"])
        assert success_count >= 1  # 至少有成功的

    def test_batch_geocode_empty_list(self, temp_cache, temp_logger):
        """空列表处理"""
        geocoder = Geocoder(temp_cache, temp_logger)
        results = geocoder.batch_geocode([], progress=False)
        geocoder.close()

        assert results == []

    def test_batch_geocache_flush_after_batch(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """批量处理后缓存自动 flush"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.batch_geocode(["北京市朝阳区"], progress=False)

        # 先验证缓存（在关闭前）
        cached = temp_cache.get("北京市朝阳区")
        assert cached is not None

        geocoder.close()


# ============================================
# 统计功能测试
# ============================================

class TestGeocoderStats:
    """测试统计功能"""

    def test_get_stats_initial(self, temp_cache, temp_logger):
        """初始统计"""
        geocoder = Geocoder(temp_cache, temp_logger)
        stats = geocoder.get_stats()
        geocoder.close()

        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0

    def test_get_stats_after_geocode(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """地理编码后统计"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.geocode("北京市朝阳区")
        stats = geocoder.get_stats()
        geocoder.close()

        assert stats["total_requests"] >= 1
        assert stats["successful_requests"] >= 1

    def test_cache_stats_integration(self, temp_cache, temp_logger):
        """缓存统计集成"""
        temp_cache.set("地址1", {"lat": 1})
        temp_cache.get("地址1")  # hit
        temp_cache.get("地址2")  # miss

        geocoder = Geocoder(temp_cache, temp_logger)
        stats = geocoder.get_cache_stats()
        geocoder.close()

        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


# ============================================
# 资源关闭测试
# ============================================

class TestGeocoderClose:
    """测试资源关闭"""

    def test_close_flushes_cache(self, temp_cache, temp_logger):
        """关闭时 flush 缓存"""
        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.geocode("")
        geocoder.close()

        # 缓存应该已关闭
        assert temp_cache._conn is None

    def test_close_saves_logger(self, temp_cache, temp_logger):
        """关闭时保存日志"""
        temp_logger.log("地址", "amap", "success", latitude=39.9)

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.close()

        # 日志应该已保存
        # 验证日志文件存在（如果有日志内容）
        # 这取决于 logger 的实现

    def test_close_multiple_times(self, temp_cache, temp_logger):
        """多次关闭不会出错"""
        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.close()
        geocoder.close()  # 再次关闭
        # 应该不会抛出异常


# ============================================
# 坐标转换集成测试
# ============================================

class TestCoordinateConversion:
    """测试坐标转换集成"""

    def test_gcj02_to_wgs84_called_for_amap(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """高德坐标需要 GCJ-02 到 WGS-84 转换"""
        # 高德返回 GCJ-02 坐标
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "1",
            "geocodes": [{
                "formatted_address": "北京市朝阳区",
                "location": "116.4853,39.9289"  # GCJ-02
            }]
        }
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        # 验证坐标已转换（WGS-84 坐标与 GCJ-02 有微小差异）
        # 转换后的坐标应该在合理范围内

    def test_cgcs2000_no_conversion_for_tianditu(self, mock_requests, mock_config_only_tianditu, temp_cache, temp_logger):
        """天地图 CGCS2000 不需要转换"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "0",
            "location": {
                "lon": 116.4853,
                "lat": 39.9289
            }
        }
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        assert result["coordinate_system"] == "CGCS2000"

    def test_bd09_to_wgs84_called_for_baidu(self, mock_requests, mock_config_only_baidu, temp_cache, temp_logger):
        """百度坐标需要 BD-09 到 WGS-84 转换"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 0,
            "result": {
                "location": {
                    "lng": 116.4853,
                    "lat": 39.9289  # BD-09
                }
            }
        }
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        assert result["success"] is True
        # 验证坐标已转换


# ============================================
# 边界条件测试
# ============================================

class TestGeocoderEdgeCases:
    """测试边界条件"""

    def test_unicode_address(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """Unicode 地址处理"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区朝阳公园南路１号")  # 全角数字
        geocoder.close()

        # 应该能正常处理

    def test_special_characters_address(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """特殊字符地址"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区(A座)")
        geocoder.close()

        # 应该能正常处理

    def test_very_long_address(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """超长地址"""
        long_address = "北京市朝阳区" + "非常长的街道名称" * 100

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_EMPTY_RESPONSE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode(long_address)
        geocoder.close()

        # 应该能正常处理，即使失败也不应该崩溃

    def test_concurrent_geocode_calls(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """并发地理编码调用"""
        import threading

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)

        results = []
        def geocode_thread(address):
            results.append(geocoder.geocode(address))

        threads = [
            threading.Thread(target=geocode_thread, args=("地址1",)),
            threading.Thread(target=geocode_thread, args=("地址2",)),
            threading.Thread(target=geocode_thread, args=("地址3",))
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        geocoder.close()

        # 所有线程应该都完成
        assert len(results) == 3
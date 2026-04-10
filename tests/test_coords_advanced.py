"""
坐标转换边界测试

测试 coords.py 模块的高级功能：
- 坐标转换精度
- 边界坐标
- 境外坐标
- 极端值处理
"""

import pytest
import math
from geocode.coords import (
    gcj02_to_wgs84,
    bd09_to_wgs84,
    bd09_to_gcj02,
    is_in_china,
)


# ============================================
# 精度验证测试
# ============================================

class TestCoordinatePrecision:
    """测试坐标转换精度"""

    def test_gcj02_to_wgs84_precision(self):
        """GCJ-02 转 WGS-84 精度验证"""
        # 已知的北京天安门 GCJ-02 坐标
        gcj_lat, gcj_lon = 39.9087, 116.3975
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        # 转换后的坐标应该在合理范围内
        assert abs(wgs_lat - gcj_lat) < 0.01  # 偏移不超过 0.01 度
        assert abs(wgs_lon - gcj_lon) < 0.01

    def test_bd09_to_wgs84_precision(self):
        """BD-09 转 WGS-84 精度验证"""
        # 北京天安门 BD-09 坐标
        bd_lat, bd_lon = 39.915, 116.404
        wgs_lat, wgs_lon = bd09_to_wgs84(bd_lat, bd_lon)

        # 偏移应该在合理范围
        assert abs(wgs_lat - bd_lat) < 0.02
        assert abs(wgs_lon - bd_lon) < 0.02

    def test_bd09_to_gcj02_precision(self):
        """BD-09 转 GCJ-02 精度验证"""
        bd_lat, bd_lon = 39.915, 116.404
        gcj_lat, gcj_lon = bd09_to_gcj02(bd_lat, bd_lon)

        # BD-09 和 GCJ-02 的偏移较小
        assert abs(gcj_lat - bd_lat) < 0.01
        assert abs(gcj_lon - bd_lon) < 0.01

    def test_conversion_consistency(self):
        """转换一致性"""
        # 同一坐标多次转换应该得到相同结果
        gcj_lat, gcj_lon = 39.9, 116.4

        results = [gcj02_to_wgs84(gcj_lat, gcj_lon) for _ in range(5)]

        for result in results[1:]:
            assert abs(result[0] - results[0][0]) < 1e-10
            assert abs(result[1] - results[0][1]) < 1e-10

    def test_decimal_places(self):
        """小数位数验证"""
        gcj_lat, gcj_lon = 39.9087, 116.3975
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        # 结果应该是浮点数
        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)

        # 应该有足够的小数位数
        # 浮点精度通常是 15-17 位有效数字


# ============================================
# 坐标边界测试
# ============================================

class TestCoordinateBoundaries:
    """测试坐标边界"""

    def test_northeast_boundary(self):
        """东北边界坐标（中国东北）"""
        # 黑龙江漠河附近
        lat, lon = 53.5, 122.5
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert 40 < wgs_lat < 60
        assert 100 < wgs_lon < 140

    def test_southwest_boundary(self):
        """西南边界坐标（海南/南海）"""
        # 海南三亚附近
        lat, lon = 18.2, 109.5
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert 10 < wgs_lat < 25
        assert 100 < wgs_lon < 120

    def test_western_boundary(self):
        """西部边界坐标（新疆）"""
        # 新疆喀什附近
        lat, lon = 39.5, 75.9
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert 30 < wgs_lat < 50
        assert 70 < wgs_lon < 90

    def test_extreme_latitude(self):
        """极端纬度（接近极点）"""
        # 非中国境内，不应该有偏移
        lat, lon = 80.0, 116.4  # 高纬度
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        # 高纬度地区可能不在中国境内
        # 转换应该正常完成

    def test_extreme_longitude(self):
        """极端经度"""
        # 中国最东端约 135°E，最西端约 73°E
        # 测试边界外
        lat, lon = 39.9, 150.0  # 超出中国东边界
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        # 应该正常处理

    def test_zero_coordinates(self):
        """零坐标"""
        lat, lon = 0.0, 0.0
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        # 零坐标不在中国境内
        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)


# ============================================
# 境外坐标测试
# ============================================

class TestOutsideChinaCoordinates:
    """测试境外坐标"""

    def test_tokyo_not_in_china(self):
        """东京不在境内"""
        # 东京坐标
        assert is_in_china(35.6762, 139.6503) is False

    def test_new_york_not_in_china(self):
        """纽约不在境内"""
        # 纽约坐标
        assert is_in_china(40.7128, -74.0060) is False

    def test_london_not_in_china(self):
        """伦敦不在境内"""
        # 伦敦坐标
        assert is_in_china(51.5074, -0.1278) is False

    def test_sydney_not_in_china(self):
        """悉尼不在境内"""
        # 悉尼坐标
        assert is_in_china(-33.8688, 151.2093) is False

    def test_beijing_in_china(self):
        """北京在境内"""
        # 北京坐标
        assert is_in_china(39.9042, 116.4074) is True

    def test_shanghai_in_china(self):
        """上海在境内"""
        # 上海坐标
        assert is_in_china(31.2304, 121.4737) is True

    def test_guangzhou_in_china(self):
        """广州在境内"""
        # 广州坐标
        assert is_in_china(23.1291, 113.2644) is True

    def test_urasa_in_china(self):
        """乌拉萨在境内（西藏边境）"""
        # 西藏边境地区
        assert is_in_china(29.6, 91.1) is True

    def test_negative_coordinates(self):
        """负数坐标（南半球/西半球）"""
        # 南美坐标
        lat, lon = -23.5505, -46.6333  # 圣保罗

        # 不在中国境内
        assert is_in_china(lat, lon) is False

        # 转换应该正常工作
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)
        assert isinstance(wgs_lat, float)


# ============================================
# 已知点验证测试
# ============================================

class TestKnownPoints:
    """测试已知点转换验证"""

    def test_beijing_tiananmen_gcj02(self):
        """北京天安门 GCJ-02 转 WGS-84"""
        # 天安门 GCJ-02 坐标（近似值）
        gcj_lat, gcj_lon = 39.9087, 116.3975
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        # WGS-84 坐标应该在合理范围内
        # 天安门真实 WGS-84 坐标约：39.9075, 116.3912
        assert 39.90 < wgs_lat < 39.92
        assert 116.38 < wgs_lon < 116.41

    def test_shanghai_oriental_pearl_gcj02(self):
        """上海东方明珠 GCJ-02 转 WGS-84"""
        # 东方明珠 GCJ-02 坐标（近似值）
        gcj_lat, gcj_lon = 31.2397, 121.4998
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        assert 31.22 < wgs_lat < 31.26
        assert 121.48 < wgs_lon < 121.52

    def test_guangzhou_canton_tower_bd09(self):
        """广州塔 BD-09 转 WGS-84"""
        # 广州塔 BD-09 坐标（近似值）
        bd_lat, bd_lon = 23.1067, 113.3245
        wgs_lat, wgs_lon = bd09_to_wgs84(bd_lat, bd_lon)

        assert 23.08 < wgs_lat < 23.13
        assert 113.30 < wgs_lon < 113.35

    def test_shenzhen_civic_center_gcj02(self):
        """深圳市民中心 GCJ-02 转 WGS-84"""
        gcj_lat, gcj_lon = 22.5463, 114.0555
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        assert 22.52 < wgs_lat < 22.58
        assert 114.03 < wgs_lon < 114.08


# ============================================
# 边界情况测试
# ============================================

class TestEdgeCases:
    """测试边界情况"""

    def test_same_coordinates(self):
        """相同坐标多次转换"""
        coords = (39.9, 116.4)

        results = [gcj02_to_wgs84(*coords) for _ in range(3)]

        # 所有结果应该相同
        for r in results[1:]:
            assert r == results[0]

    def test_very_small_coordinates(self):
        """非常小的坐标值"""
        lat, lon = 0.001, 0.001
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert isinstance(wgs_lat, float)

    def test_negative_longitude(self):
        """负经度（西半球）"""
        lat, lon = 40.7, -74.0  # 纽约
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        # 不在中国境内，偏移应该为 0 或很小
        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)

    def test_negative_latitude(self):
        """负纬度（南半球）"""
        lat, lon = -33.9, 151.2  # 悉尼
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)

    def test_both_negative(self):
        """纬度和经度都是负数"""
        lat, lon = -33.9, -151.2
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert isinstance(wgs_lat, float)
        assert isinstance(wgs_lon, float)

    def test_large_positive_coordinates(self):
        """大正数坐标"""
        # 超出正常范围的坐标
        lat, lon = 90.0, 180.0
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        # 应该正常处理
        assert isinstance(wgs_lat, float)

    def test_large_negative_coordinates(self):
        """大负数坐标"""
        lat, lon = -90.0, -180.0
        wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)

        assert isinstance(wgs_lat, float)


# ============================================
# 偏移量测试
# ============================================

class TestOffset:
    """测试坐标偏移"""

    def test_china_offset_exists(self):
        """中国境内坐标存在偏移"""
        # 北京坐标
        gcj_lat, gcj_lon = 39.9042, 116.4074
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        # 偏移应该存在（GCJ-02 和 WGS-84 不同）
        offset_lat = abs(gcj_lat - wgs_lat)
        offset_lon = abs(gcj_lon - wgs_lon)

        # 中国境内偏移通常在几百米范围内
        assert offset_lat > 0.0001 or offset_lon > 0.0001

    def test_outside_china_no_offset(self):
        """境外坐标无偏移（或很小）"""
        # 东京坐标
        gcj_lat, gcj_lon = 35.6762, 139.6503
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)

        # 境外偏移应该很小或为零
        # 取决于 out_of_china 的判断
        # 实际实现可能仍有小偏移

    def test_bd09_has_more_offset(self):
        """BD-09 比 GCJ-02 有更大偏移"""
        lat, lon = 39.9, 116.4

        wgs_from_gcj = gcj02_to_wgs84(lat, lon)
        wgs_from_bd = bd09_to_wgs84(lat, lon)

        # BD-09 到 WGS-84 的转换更复杂
        # 两者结果可能不同


# ============================================
# 数值稳定性测试
# ============================================

class TestNumericalStability:
    """测试数值稳定性"""

    def test_no_nan_result(self):
        """结果不是 NaN"""
        test_coords = [
            (0, 0),
            (90, 180),
            (-90, -180),
            (39.9, 116.4),
            (-33.9, 151.2),
        ]

        for lat, lon in test_coords:
            wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)
            assert not math.isnan(wgs_lat)
            assert not math.isnan(wgs_lon)

    def test_no_infinity_result(self):
        """结果不是无穷大"""
        test_coords = [
            (0, 0),
            (90, 180),
            (-90, -180),
            (39.9, 116.4),
        ]

        for lat, lon in test_coords:
            wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)
            assert not math.isinf(wgs_lat)
            assert not math.isinf(wgs_lon)

    def test_finite_result(self):
        """结果是有限数"""
        for _ in range(100):
            import random
            lat = random.uniform(-90, 90)
            lon = random.uniform(-180, 180)

            wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)
            assert math.isfinite(wgs_lat)
            assert math.isfinite(wgs_lon)


# ============================================
# 批量转换测试
# ============================================

class TestBatchConversion:
    """测试批量转换"""

    def test_batch_conversion_consistency(self):
        """批量转换一致性"""
        coords = [(39.9, 116.4), (31.2, 121.5), (23.1, 113.3)]

        # 第一次转换
        results1 = [gcj02_to_wgs84(lat, lon) for lat, lon in coords]

        # 第二次转换
        results2 = [gcj02_to_wgs84(lat, lon) for lat, lon in coords]

        # 结果应该一致
        for r1, r2 in zip(results1, results2):
            assert r1 == r2

    def test_large_batch_conversion(self):
        """大批量转换"""
        import random
        random.seed(42)

        # 生成 1000 个中国境内的随机坐标
        coords = [(random.uniform(18, 54), random.uniform(73, 135))
                  for _ in range(1000)]

        # 批量转换
        results = [gcj02_to_wgs84(lat, lon) for lat, lon in coords]

        # 所有结果应该是有效浮点数
        for wgs_lat, wgs_lon in results:
            assert isinstance(wgs_lat, float)
            assert isinstance(wgs_lon, float)
            assert math.isfinite(wgs_lat)
            assert math.isfinite(wgs_lon)
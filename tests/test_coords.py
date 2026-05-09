"""坐标转换模块测试"""
import math

import pytest

from geocode.coords import (
    gcj02_to_wgs84,
    wgs84_to_gcj02,
    bd09_to_gcj02,
    bd09_to_wgs84,
    is_in_china,
)

# 往返容差：约 2 米（0.00002 度）
ROUNDTRIP_TOL = 0.00002


class TestGCJ02WGS84Roundtrip:
    """GCJ-02 <-> WGS-84 往返转换测试"""

    def test_roundtrip_beijing(self):
        wgs_lat, wgs_lon = 39.9042, 116.4074
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        back_lat, back_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        assert abs(back_lat - wgs_lat) < ROUNDTRIP_TOL
        assert abs(back_lon - wgs_lon) < ROUNDTRIP_TOL

    def test_roundtrip_shanghai(self):
        wgs_lat, wgs_lon = 31.2304, 121.4737
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        back_lat, back_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        assert abs(back_lat - wgs_lat) < ROUNDTRIP_TOL
        assert abs(back_lon - wgs_lon) < ROUNDTRIP_TOL

    def test_roundtrip_shenzhen(self):
        wgs_lat, wgs_lon = 22.5431, 114.0579
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        back_lat, back_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        assert abs(back_lat - wgs_lat) < ROUNDTRIP_TOL
        assert abs(back_lon - wgs_lon) < ROUNDTRIP_TOL

    def test_roundtrip_multiple_points(self):
        """批量往返测试"""
        test_points = [
            (39.9042, 116.4074),   # 北京
            (31.2304, 121.4737),   # 上海
            (23.1291, 113.2644),   # 广州
            (30.5728, 104.0668),   # 成都
            (34.3416, 108.9398),   # 西安
        ]
        for wgs_lat, wgs_lon in test_points:
            gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
            back_lat, back_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
            assert abs(back_lat - wgs_lat) < ROUNDTRIP_TOL, f"Failed for ({wgs_lat}, {wgs_lon})"
            assert abs(back_lon - wgs_lon) < ROUNDTRIP_TOL, f"Failed for ({wgs_lat}, {wgs_lon})"


class TestGCJ02ToWGS84:
    """GCJ-02 -> WGS-84 转换测试"""

    def test_offset_magnitude(self):
        """中国境内偏移量应在合理范围 (100-700米)"""
        gcj_lat, gcj_lon = 39.90569, 116.41355
        wgs_lat, wgs_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        dlat = (gcj_lat - wgs_lat) * 111320
        dlon = (gcj_lon - wgs_lon) * 111320 * math.cos(math.radians(gcj_lat))
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        assert 100 < dist < 700, f"Offset {dist:.0f}m out of expected range"

    def test_wgs84_to_gcj02_offset_direction(self):
        """WGS-84 -> GCJ-02 应产生正向偏移（中国境内）"""
        wgs_lat, wgs_lon = 39.9042, 116.4074
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        # GCJ-02 应比 WGS-84 偏东北方向
        assert gcj_lat > wgs_lat
        assert gcj_lon > wgs_lon
        # 偏移量应在合理范围内
        dlat = (gcj_lat - wgs_lat) * 111320
        dlon = (gcj_lon - wgs_lon) * 111320 * math.cos(math.radians(wgs_lat))
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        assert 100 < dist < 700, f"Offset {dist:.0f}m out of expected range"


class TestBD09Conversion:
    """百度坐标系转换测试"""

    def test_bd09_to_gcj02_roundtrip(self):
        bd_lat, bd_lon = 39.91195, 116.41990
        gcj_lat, gcj_lon = bd09_to_gcj02(bd_lat, bd_lon)
        assert abs(gcj_lat - 39.90569) < 0.01
        assert abs(gcj_lon - 116.41355) < 0.01

    def test_bd09_to_wgs84_roundtrip(self):
        bd_lat, bd_lon = 39.91195, 116.41990
        wgs_lat, wgs_lon = bd09_to_wgs84(bd_lat, bd_lon)
        assert abs(wgs_lat - 39.9042) < 0.01
        assert abs(wgs_lon - 116.4074) < 0.01


class TestIsInChina:
    """中国境内判断测试"""

    def test_beijing_is_china(self):
        assert is_in_china(39.9042, 116.4074) is True

    def test_london_not_china(self):
        assert is_in_china(51.5074, -0.1278) is False

    def test_new_york_not_china(self):
        assert is_in_china(40.7128, -74.0060) is False

    def test_boundary_south_china_sea(self):
        """南海边界点"""
        assert is_in_china(3.97, 112.34) is True

    def test_boundary_north(self):
        """漠河附近"""
        assert is_in_china(53.5, 122.3) is True

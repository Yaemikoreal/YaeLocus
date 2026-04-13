"""
坐标转换工具模块

支持的坐标系转换:
- WGS-84: GPS原始坐标系, 国际标准
- GCJ-02: 国测局坐标(火星坐标), 高德/天地图使用
- BD-09: 百度偏移坐标, 百度地图使用
"""

import math
from typing import Tuple


# 椭球参数
A = 6378245.0  # 长半轴
EE = 0.00669342162296594323  # 扁率


def _transform_lat(x: float, y: float) -> float:
    """纬度转换"""
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    """经度转换"""
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lat: float, lon: float) -> Tuple[float, float]:
    """
    GCJ-02 坐标转 WGS-84 坐标

    Args:
        lat: GCJ-02 纬度
        lon: GCJ-02 经度

    Returns:
        (wgs_lat, wgs_lon): WGS-84 坐标
    """
    d_lat = _transform_lat(lon - 105.0, lat - 35.0)
    d_lon = _transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * math.pi)
    d_lon = (d_lon * 180.0) / (A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lat - d_lat, lon - d_lon


def bd09_to_gcj02(lat: float, lon: float) -> Tuple[float, float]:
    """
    BD-09 坐标转 GCJ-02 坐标

    Args:
        lat: BD-09 纬度
        lon: BD-09 经度

    Returns:
        (gcj_lat, gcj_lon): GCJ-02 坐标
    """
    x = lon - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * math.pi * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * math.pi * 3000.0 / 180.0)
    return z * math.sin(theta), z * math.cos(theta)


def bd09_to_wgs84(lat: float, lon: float) -> Tuple[float, float]:
    """
    BD-09 坐标转 WGS-84 坐标

    Args:
        lat: BD-09 纬度
        lon: BD-09 经度

    Returns:
        (wgs_lat, wgs_lon): WGS-84 坐标
    """
    gcj_lat, gcj_lon = bd09_to_gcj02(lat, lon)
    return gcj02_to_wgs84(gcj_lat, gcj_lon)


def wgs84_to_gcj02(lat: float, lon: float) -> Tuple[float, float]:
    """
    WGS-84 坐标转 GCJ-02 坐标（逆地理编码需要）

    Args:
        lat: WGS-84 纬度
        lon: WGS-84 经度

    Returns:
        (gcj_lat, gcj_lon): GCJ-02 坐标
    """
    # 反向计算：WGS-84 + 偏移 = GCJ-02
    d_lat = _transform_lat(lon - 105.0, lat - 35.0)
    d_lon = _transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * math.pi)
    d_lon = (d_lon * 180.0) / (A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lat + d_lat, lon + d_lon


def is_in_china(lat: float, lon: float) -> bool:
    """
    判断坐标是否在中国境内

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        是否在中国境内
    """
    return 0.8293 <= lat <= 55.8271 and 72.004 <= lon <= 137.8347
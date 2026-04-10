"""
共享测试配置和 fixtures

提供测试所需的通用 fixtures 和 Mock 配置
"""

import pytest
import json
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import sqlite3
import os

# 导入项目模块
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geocode.cache import CacheManager
from geocode.logger import APILogger
from geocode.config import Config
from geocode.geocoder import Geocoder


# ============================================
# 自动清理全局缓存
# ============================================

@pytest.fixture(autouse=True)
def clean_global_cache():
    """
    每个测试前后自动清理全局缓存文件

    防止测试之间通过全局缓存污染
    """
    global_cache = PROJECT_ROOT / "output" / "geocache.db"
    global_log = PROJECT_ROOT / "output" / "api调用日志.csv"

    # 测试前清理
    for f in [global_cache, global_log,
              Path(str(global_cache) + "-wal"),
              Path(str(global_cache) + "-shm")]:
        if f.exists():
            try:
                os.unlink(f)
            except PermissionError:
                pass  # 文件被占用，跳过

    yield

    # 测试后清理
    for f in [global_cache, global_log,
              Path(str(global_cache) + "-wal"),
              Path(str(global_cache) + "-shm")]:
        if f.exists():
            try:
                os.unlink(f)
            except PermissionError:
                pass


# ============================================
# 临时文件 fixtures
# ============================================

@pytest.fixture
def temp_cache(tmp_path):
    """
    创建临时缓存管理器

    使用方法:
        def test_example(self, temp_cache):
            temp_cache.set("地址", {"lat": 1, "lng": 2})
            result = temp_cache.get("地址")
    """
    cache_file = tmp_path / "test_cache.db"
    cache = CacheManager(cache_file=str(cache_file))
    yield cache
    cache.close()


@pytest.fixture
def temp_logger(tmp_path):
    """
    创建临时 API 日志记录器

    使用方法:
        def test_example(self, temp_logger):
            temp_logger.log("地址", "amap", "success")
            temp_logger.save()
    """
    log_file = tmp_path / "test_api_log.csv"
    logger = APILogger(log_file=str(log_file))
    yield logger
    logger.save()


@pytest.fixture
def temp_dir(tmp_path):
    """
    临时目录 fixture

    返回一个临时 Path 对象，用于存放测试文件
    """
    return tmp_path


@pytest.fixture
def temp_env_file(tmp_path, monkeypatch):
    """
    创建临时 .env 文件

    用于测试配置加载
    """
    env_file = tmp_path / ".env"
    # 临时修改 PROJECT_DIR
    monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
    monkeypatch.setattr("geocode.config.ENV_FILE", env_file)
    return env_file


# ============================================
# Mock 配置 fixtures
# ============================================

@pytest.fixture
def mock_config_valid(monkeypatch):
    """
    Mock 有效配置 - 设置测试 API 密钥

    使所有 API 密钥可用
    """
    monkeypatch.setattr(Config, 'AMAP_KEY', 'test_amap_key_32_characters_length')
    monkeypatch.setattr(Config, 'BAIDU_AK', 'test_baidu_ak_key')
    monkeypatch.setattr(Config, 'TIANDITU_TK', 'test_tianditu_tk_key')


@pytest.fixture
def mock_config_no_keys(monkeypatch):
    """
    Mock 无密钥配置

    模拟未配置任何 API 密钥的场景
    """
    monkeypatch.setattr(Config, 'AMAP_KEY', '')
    monkeypatch.setattr(Config, 'BAIDU_AK', '')
    monkeypatch.setattr(Config, 'TIANDITU_TK', '')


@pytest.fixture
def mock_config_only_amap(monkeypatch):
    """
    Mock 仅高德密钥配置

    只有高德 API 可用
    """
    monkeypatch.setattr(Config, 'AMAP_KEY', 'test_amap_key_32_characters_length')
    monkeypatch.setattr(Config, 'BAIDU_AK', '')
    monkeypatch.setattr(Config, 'TIANDITU_TK', '')


@pytest.fixture
def mock_config_only_tianditu(monkeypatch):
    """
    Mock 仅天地图密钥配置

    只有天地图 API 可用
    """
    monkeypatch.setattr(Config, 'AMAP_KEY', '')
    monkeypatch.setattr(Config, 'BAIDU_AK', '')
    monkeypatch.setattr(Config, 'TIANDITU_TK', 'test_tianditu_tk_key')


@pytest.fixture
def mock_config_only_baidu(monkeypatch):
    """
    Mock 仅百度密钥配置

    只有百度 API 可用
    """
    monkeypatch.setattr(Config, 'AMAP_KEY', '')
    monkeypatch.setattr(Config, 'BAIDU_AK', 'test_baidu_ak_key')
    monkeypatch.setattr(Config, 'TIANDITU_TK', '')


# ============================================
# Mock requests fixtures
# ============================================

@pytest.fixture
def mock_requests():
    """
    Mock requests 模块

    使用方法:
        def test_example(self, mock_requests):
            mock_requests.get.return_value.json.return_value = {"status": "1"}
    """
    with patch('geocode.geocoder.requests') as mock:
        yield mock


@pytest.fixture
def mock_requests_success(mock_requests):
    """
    Mock 成功的 API 请求

    默认返回高德成功响应
    """
    from tests.fixtures.api_responses import AMAP_SUCCESS_RESPONSE_SIMPLE

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
    mock_requests.get.return_value = mock_response
    return mock_requests


@pytest.fixture
def mock_requests_timeout(mock_requests):
    """
    Mock 超时请求

    模拟网络超时异常
    """
    import requests
    mock_requests.get.side_effect = requests.Timeout("Connection timeout")
    return mock_requests


@pytest.fixture
def mock_requests_connection_error(mock_requests):
    """
    Mock 连接错误

    模拟网络连接失败
    """
    import requests
    mock_requests.get.side_effect = requests.ConnectionError("Connection failed")
    return mock_requests


@pytest.fixture
def mock_requests_invalid_json(mock_requests):
    """
    Mock 无效 JSON 响应

    模拟 JSON 解析失败
    """
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    mock_requests.get.return_value = mock_response
    return mock_requests


@pytest.fixture
def mock_requests_all_fail(mock_requests):
    """
    Mock 所有 API 失败

    模拟所有 API 返回错误
    """
    from tests.fixtures.api_responses import AMAP_UNKNOWN_ERROR_RESPONSE

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = AMAP_UNKNOWN_ERROR_RESPONSE
    mock_requests.get.return_value = mock_response
    return mock_requests


# ============================================
# 测试数据 fixtures
# ============================================

@pytest.fixture
def sample_addresses():
    """
    测试地址列表
    """
    return [
        "北京市朝阳区建国路88号",
        "上海市浦东新区陆家嘴",
        "广州市天河区天河路385号",
        "深圳市南山区科技园",
        "成都市武侯区天府大道"
    ]


@pytest.fixture
def sample_address_single():
    """
    单个测试地址
    """
    return "北京市朝阳区建国路88号"


@pytest.fixture
def sample_geocode_result_success():
    """
    成功的地理编码结果
    """
    return {
        "success": True,
        "original_address": "北京市朝阳区建国路88号",
        "formatted_address": "北京市朝阳区建国路88号",
        "latitude": 39.9059,
        "longitude": 116.4699,
        "province": "北京市",
        "city": "朝阳区",
        "district": "",
        "source": "amap",
        "coordinate_system": "GCJ-02"
    }


@pytest.fixture
def sample_geocode_result_failed():
    """
    失败的地理编码结果
    """
    return {
        "success": False,
        "original_address": "无效地址xyz",
        "error": "All APIs failed"
    }


@pytest.fixture
def sample_geocode_results_mixed():
    """
    混合成功/失败的地理编码结果列表
    """
    return [
        {
            "success": True,
            "original_address": "北京市朝阳区",
            "latitude": 39.9289,
            "longitude": 116.4853,
            "source": "amap"
        },
        {
            "success": False,
            "original_address": "无效地址1",
            "error": "All APIs failed"
        },
        {
            "success": True,
            "original_address": "上海市浦东新区",
            "latitude": 31.2397,
            "longitude": 121.4998,
            "source": "tianditu"
        },
        {
            "success": False,
            "original_address": "无效地址2",
            "error": "All APIs failed"
        }
    ]


@pytest.fixture
def sample_map_data():
    """
    用于地图可视化的测试数据
    """
    return [
        {"latitude": 39.9059, "longitude": 116.4699, "original_address": "北京"},
        {"latitude": 31.2397, "longitude": 121.4998, "original_address": "上海"},
        {"latitude": 23.1291, "longitude": 113.2644, "original_address": "广州"}
    ]


# ============================================
# 测试文件 fixtures
# ============================================

@pytest.fixture
def sample_csv(tmp_path):
    """
    创建测试 CSV 文件

    包含地址列的标准 CSV
    """
    df = pd.DataFrame({
        "地址": ["北京市朝阳区建国路88号", "上海市浦东新区陆家嘴", "广州市天河区天河路385号"],
        "名称": ["地点1", "地点2", "地点3"],
        "备注": ["备注A", "备注B", "备注C"]
    })
    file_path = tmp_path / "test_input.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


@pytest.fixture
def sample_csv_utf8_bom(tmp_path):
    """
    创建 UTF-8 BOM 编码的 CSV
    """
    df = pd.DataFrame({
        "地址": ["北京市朝阳区", "上海市浦东新区"]
    })
    file_path = tmp_path / "test_utf8_bom.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


@pytest.fixture
def sample_csv_gbk(tmp_path):
    """
    创建 GBK 编码的 CSV
    """
    df = pd.DataFrame({
        "地址": ["北京市朝阳区", "上海市浦东新区"]
    })
    file_path = tmp_path / "test_gbk.csv"
    df.to_csv(file_path, index=False, encoding="gbk")
    return file_path


@pytest.fixture
def sample_excel(tmp_path):
    """
    创建测试 Excel 文件 (xlsx)
    """
    df = pd.DataFrame({
        "地址": ["北京市朝阳区建国路88号", "上海市浦东新区陆家嘴"],
        "名称": ["地点1", "地点2"]
    })
    file_path = tmp_path / "test_input.xlsx"
    df.to_excel(file_path, index=False, engine="openpyxl")
    return file_path


@pytest.fixture
def sample_excel_xls(tmp_path):
    """
    创建测试 Excel 文件 (xls) - 需要 xlrd
    """
    df = pd.DataFrame({
        "地址": ["北京市朝阳区", "上海市浦东新区"]
    })
    file_path = tmp_path / "test_input.xls"
    # 注意: xls 需要 xlrd 库
    try:
        df.to_excel(file_path, index=False, engine="xlwt")
    except Exception:
        # 如果 xlwt 不可用，使用 xlsx
        file_path = tmp_path / "test_input.xlsx"
        df.to_excel(file_path, index=False, engine="openpyxl")
    return file_path


@pytest.fixture
def malformed_csv(tmp_path):
    """
    创建损坏的 CSV 文件
    """
    file_path = tmp_path / "malformed.csv"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("地址,名称\n")
        f.write("北京市朝阳区,地点1\n")
        f.write("上海市浦东新区,地点2,额外列\n")  # 多了一列
        f.write("广州市天河区\n")  # 少了一列
    return file_path


@pytest.fixture
def csv_missing_column(tmp_path):
    """
    创建不含地址列的 CSV
    """
    df = pd.DataFrame({
        "名称": ["地点1", "地点2"],
        "备注": ["备注A", "备注B"]
    })
    file_path = tmp_path / "missing_column.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


@pytest.fixture
def csv_empty_addresses(tmp_path):
    """
    创建地址列为空的 CSV
    """
    df = pd.DataFrame({
        "地址": [None, "", "   "],
        "名称": ["地点1", "地点2", "地点3"]
    })
    file_path = tmp_path / "empty_addresses.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


@pytest.fixture
def large_csv(tmp_path):
    """
    创建大型 CSV 文件 (1000条)
    """
    addresses = [f"测试地址{i}号" for i in range(1000)]
    df = pd.DataFrame({
        "地址": addresses,
        "序号": range(1000)
    })
    file_path = tmp_path / "large_input.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


# ============================================
# Geocoder fixtures
# ============================================

@pytest.fixture
def geocoder_with_mock(mock_config_valid, temp_cache, temp_logger):
    """
    创建带 Mock 配置的 Geocoder
    """
    return Geocoder(temp_cache, temp_logger)


@pytest.fixture
def geocoder_no_api_key(mock_config_no_keys, temp_cache, temp_logger):
    """
    创建无 API 密钥的 Geocoder
    """
    return Geocoder(temp_cache, temp_logger)


# ============================================
# CLI Runner fixture
# ============================================

@pytest.fixture
def cli_runner():
    """
    Typer CLI 测试运行器
    """
    from typer.testing import CliRunner
    runner = CliRunner(mix_stderr=False)
    return runner


# ============================================
# 损坏数据库 fixture
# ============================================

@pytest.fixture
def corrupted_cache_file(tmp_path):
    """
    创建损坏的缓存数据库文件
    """
    cache_file = tmp_path / "corrupted.db"
    # 写入无效的二进制数据
    with open(cache_file, "wb") as f:
        f.write(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09")
    return cache_file


@pytest.fixture
def cache_with_data(temp_cache):
    """
    预填充数据的缓存
    """
    test_data = [
        ("北京市朝阳区", {"lat": 39.9289, "lng": 116.4853, "source": "amap"}),
        ("上海市浦东新区", {"lat": 31.2397, "lng": 121.4998, "source": "amap"}),
        ("广州市天河区", {"lat": 23.1291, "lng": 113.2644, "source": "tianditu"})
    ]
    for address, result in test_data:
        temp_cache.set(address, result)
    temp_cache.flush()
    return temp_cache


# ============================================
# 辅助函数 fixtures
# ============================================

@pytest.fixture
def assert_geocode_success():
    """
    断言地理编码成功的辅助函数
    """
    def _assert(result):
        assert result.get("success") is True
        assert result.get("latitude") is not None
        assert result.get("longitude") is not None
        assert isinstance(result.get("latitude"), (int, float))
        assert isinstance(result.get("longitude"), (int, float))
    return _assert


@pytest.fixture
def assert_geocode_failed():
    """
    断言地理编码失败的辅助函数
    """
    def _assert(result):
        assert result.get("success") is False
        assert result.get("error") is not None
    return _assert
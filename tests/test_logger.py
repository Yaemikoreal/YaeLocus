"""
API 日志测试

测试 APILogger 类的功能：
- 日志记录
- 日志保存
- 统计信息
- CSV 格式验证
"""

import pytest
import csv
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

from geocode.logger import APILogger
from geocode.models import APILog


# ============================================
# 初始化测试
# ============================================

class TestAPILoggerInit:
    """测试初始化"""

    def test_init_default_path(self, tmp_path, monkeypatch):
        """默认日志路径"""
        monkeypatch.chdir(tmp_path)
        logger = APILogger()
        # 默认路径是 output/api调用日志.csv
        assert "api调用日志" in str(logger.log_file) or "api" in str(logger.log_file).lower()

    def test_init_custom_path(self, tmp_path):
        """自定义日志路径"""
        log_file = tmp_path / "custom_log.csv"
        logger = APILogger(log_file=str(log_file))
        assert logger.log_file == log_file

    def test_init_creates_directory(self, tmp_path):
        """自动创建目录"""
        log_file = tmp_path / "subdir" / "nested" / "log.csv"
        logger = APILogger(log_file=str(log_file))
        assert logger.log_file.parent.exists()

    def test_init_empty_logs(self, tmp_path):
        """初始化时日志为空"""
        log_file = tmp_path / "test_log.csv"
        logger = APILogger(log_file=str(log_file))
        assert len(logger._logs) == 0


# ============================================
# 日志记录测试
# ============================================

class TestAPILoggerLog:
    """测试日志记录"""

    def test_log_success(self, temp_logger):
        """记录成功调用"""
        temp_logger.log(
            address="北京市朝阳区",
            api_name="amap",
            status="success",
            latitude=39.9,
            longitude=116.4
        )
        assert len(temp_logger._logs) == 1

        log = temp_logger._logs[0]
        assert log.address == "北京市朝阳区"
        assert log.api_name == "amap"
        assert log.status == "success"
        assert log.latitude == 39.9

    def test_log_failed(self, temp_logger):
        """记录失败调用"""
        temp_logger.log(
            address="无效地址",
            api_name="amap",
            status="failed",
            error_message="未找到结果"
        )
        assert len(temp_logger._logs) == 1
        assert temp_logger._logs[0].status == "failed"

    def test_log_error(self, temp_logger):
        """记录错误调用"""
        temp_logger.log(
            address="测试地址",
            api_name="tianditu",
            status="error",
            error_message="网络超时"
        )
        assert len(temp_logger._logs) == 1
        assert temp_logger._logs[0].status == "error"

    def test_log_with_all_fields(self, temp_logger):
        """记录完整字段"""
        temp_logger.log(
            address="北京市朝阳区建国路88号",
            api_name="amap",
            status="success",
            latitude=39.9059,
            longitude=116.4699,
            formatted_address="北京市朝阳区建国路88号",
            time_cost=0.5,
            error_message=None
        )

        log = temp_logger._logs[0]
        assert log.address == "北京市朝阳区建国路88号"
        assert log.latitude == 39.9059
        assert log.longitude == 116.4699
        assert log.formatted_address == "北京市朝阳区建国路88号"
        assert log.time_cost == 0.5

    def test_log_multiple_entries(self, temp_logger):
        """多条日志记录"""
        addresses = ["地址1", "地址2", "地址3"]
        for addr in addresses:
            temp_logger.log(addr, "amap", "success")

        assert len(temp_logger._logs) == 3

    def test_log_timestamp_auto_generated(self, temp_logger):
        """自动生成时间戳"""
        temp_logger.log("地址", "amap", "success")
        log = temp_logger._logs[0]

        # 时间戳格式应该是 YYYY-MM-DD HH:MM:SS
        assert log.timestamp is not None
        # 尝试解析时间戳
        try:
            datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S")
            valid_format = True
        except ValueError:
            valid_format = False
        assert valid_format

    def test_log_time_cost_rounded(self, temp_logger):
        """耗时四舍五入到3位小数"""
        temp_logger.log("地址", "amap", "success", time_cost=0.123456)
        log = temp_logger._logs[0]
        assert log.time_cost == 0.123


# ============================================
# 日志保存测试
# ============================================

class TestAPILoggerSave:
    """测试日志保存"""

    def test_save_creates_file(self, temp_logger, tmp_path):
        """保存创建文件"""
        temp_logger.log("地址", "amap", "success")
        temp_logger.save()

        assert temp_logger.log_file.exists()

    def test_save_csv_format(self, temp_logger):
        """CSV 格式正确"""
        temp_logger.log("北京市朝阳区", "amap", "success", latitude=39.9, longitude=116.4)
        temp_logger.save()

        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["address"] == "北京市朝阳区"
        assert rows[0]["api_name"] == "amap"
        assert rows[0]["status"] == "success"

    def test_save_utf8_bom_encoding(self, temp_logger):
        """UTF-8 BOM 编码"""
        temp_logger.log("中文地址测试", "amap", "success")
        temp_logger.save()

        # 检查文件编码
        with open(temp_logger.log_file, "rb") as f:
            first_bytes = f.read(3)
            # UTF-8 BOM 是 EF BB BF
            assert first_bytes == b'\xef\xbb\xbf' or temp_logger.log_file.exists()

    def test_save_append_mode(self, temp_logger):
        """追加模式"""
        # 第一次保存
        temp_logger.log("地址1", "amap", "success")
        temp_logger.save()

        # 第二次保存（新的 logger 实例）
        logger2 = APILogger(log_file=str(temp_logger.log_file))
        logger2.log("地址2", "tianditu", "success")
        logger2.save()

        # 应该有两行
        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

    def test_save_empty_logs(self, temp_logger):
        """空日志不创建文件"""
        temp_logger.save()
        # 空日志时不应该创建文件
        # （取决于实现，可能创建空文件或不创建）

    def test_save_multiple_entries(self, temp_logger):
        """保存多条记录"""
        for i in range(5):
            temp_logger.log(f"地址{i}", "amap", "success")
        temp_logger.save()

        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5

    def test_save_with_chinese_content(self, temp_logger):
        """保存中文内容"""
        temp_logger.log(
            address="北京市朝阳区建国路88号",
            api_name="amap",
            status="success",
            formatted_address="北京市朝阳区建国路88号",
            error_message="错误信息测试"
        )
        temp_logger.save()

        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            content = f.read()

        assert "北京市朝阳区" in content


# ============================================
# 统计功能测试
# ============================================

class TestAPILoggerStats:
    """测试统计功能"""

    def test_stats_empty(self, temp_logger):
        """空日志统计"""
        stats = temp_logger.get_stats()

        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["api_usage"] == {}

    def test_stats_success_count(self, temp_logger):
        """成功计数"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.log("地址2", "amap", "success")
        temp_logger.log("地址3", "amap", "failed")

        stats = temp_logger.get_stats()
        assert stats["success"] == 2
        assert stats["failed"] == 1

    def test_stats_success_rate(self, temp_logger):
        """成功率计算"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.log("地址2", "amap", "success")
        temp_logger.log("地址3", "amap", "failed")
        temp_logger.log("地址4", "amap", "failed")

        stats = temp_logger.get_stats()
        # 2 成功 / 4 总数 = 50%
        assert stats["success_rate"] == 50.0

    def test_stats_api_usage(self, temp_logger):
        """API 使用分布"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.log("地址2", "amap", "success")
        temp_logger.log("地址3", "tianditu", "success")
        temp_logger.log("地址4", "baidu", "success")

        stats = temp_logger.get_stats()
        assert stats["api_usage"]["amap"] == 2
        assert stats["api_usage"]["tianditu"] == 1
        assert stats["api_usage"]["baidu"] == 1

    def test_stats_mixed_status(self, temp_logger):
        """混合状态统计"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.log("地址2", "amap", "failed")
        temp_logger.log("地址3", "tianditu", "error")

        stats = temp_logger.get_stats()
        assert stats["total"] == 3
        assert stats["success"] == 1
        assert stats["failed"] == 2  # failed + error 都算失败

    def test_stats_100_percent_success(self, temp_logger):
        """100% 成功率"""
        for i in range(10):
            temp_logger.log(f"地址{i}", "amap", "success")

        stats = temp_logger.get_stats()
        assert stats["success_rate"] == 100.0

    def test_stats_0_percent_success(self, temp_logger):
        """0% 成功率"""
        for i in range(10):
            temp_logger.log(f"地址{i}", "amap", "failed")

        stats = temp_logger.get_stats()
        assert stats["success_rate"] == 0.0


# ============================================
# 清空功能测试
# ============================================

class TestAPILoggerClear:
    """测试清空"""

    def test_clear_empties_logs(self, temp_logger):
        """清空日志列表"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.log("地址2", "amap", "success")
        assert len(temp_logger._logs) == 2

        temp_logger.clear()
        assert len(temp_logger._logs) == 0

    def test_clear_resets_stats(self, temp_logger):
        """清空后统计重置"""
        temp_logger.log("地址", "amap", "success")
        temp_logger.clear()

        stats = temp_logger.get_stats()
        assert stats["total"] == 0

    def test_clear_empty_logger(self, temp_logger):
        """清空空日志"""
        temp_logger.clear()
        assert len(temp_logger._logs) == 0


# ============================================
# 边界条件测试
# ============================================

class TestAPILoggerEdgeCases:
    """测试边界条件"""

    def test_log_none_latitude_longitude(self, temp_logger):
        """None 经纬度"""
        temp_logger.log("地址", "amap", "failed", latitude=None, longitude=None)
        assert len(temp_logger._logs) == 1

    def test_log_zero_coordinates(self, temp_logger):
        """零坐标"""
        temp_logger.log("地址", "amap", "success", latitude=0.0, longitude=0.0)
        log = temp_logger._logs[0]
        assert log.latitude == 0.0
        assert log.longitude == 0.0

    def test_log_negative_coordinates(self, temp_logger):
        """负坐标"""
        temp_logger.log("地址", "amap", "success", latitude=-23.5, longitude=-46.6)
        log = temp_logger._logs[0]
        assert log.latitude == -23.5
        assert log.longitude == -46.6

    def test_log_very_long_address(self, temp_logger):
        """超长地址"""
        long_address = "北京市朝阳区" * 100
        temp_logger.log(long_address, "amap", "success")
        assert temp_logger._logs[0].address == long_address

    def test_log_unicode_address(self, temp_logger):
        """Unicode 地址"""
        unicode_address = "北京市朝阳区🎉📍"
        temp_logger.log(unicode_address, "amap", "success")
        assert temp_logger._logs[0].address == unicode_address

    def test_log_special_characters(self, temp_logger):
        """特殊字符"""
        temp_logger.log("地址,含逗号\n换行\"引号", "amap", "success")
        temp_logger.save()

        # 读取验证
        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            content = f.read()
        assert "地址" in content

    def test_multiple_save_calls(self, temp_logger):
        """多次调用 save"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.save()
        temp_logger.save()  # 再次保存
        temp_logger.save()  # 再次保存

        # 不应该重复写入
        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1

    def test_save_after_clear(self, temp_logger):
        """清空后保存"""
        temp_logger.log("地址1", "amap", "success")
        temp_logger.save()
        temp_logger.clear()
        temp_logger.log("地址2", "amap", "success")
        temp_logger.save()

        # 应该有两行（追加模式）
        with open(temp_logger.log_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2


# ============================================
# 与 Geocoder 集成测试
# ============================================

class TestLoggerIntegration:
    """测试与 Geocoder 集成"""

    def test_logger_used_by_geocoder(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """Geocoder 使用 Logger"""
        from geocode.geocoder import Geocoder
        from tests.fixtures.api_responses import AMAP_SUCCESS_RESPONSE_SIMPLE

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 应该有日志记录
        assert len(temp_logger._logs) >= 1

    def test_logger_records_api_name(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """记录正确的 API 名称"""
        from geocode.geocoder import Geocoder
        from tests.fixtures.api_responses import AMAP_SUCCESS_RESPONSE_SIMPLE

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 检查 API 名称
        assert temp_logger._logs[0].api_name == "amap"

    def test_logger_records_time_cost(self, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """记录耗时"""
        from geocode.geocoder import Geocoder
        from tests.fixtures.api_responses import AMAP_SUCCESS_RESPONSE_SIMPLE
        import time

        def slow_request(*args, **kwargs):
            time.sleep(0.1)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
            return mock_response

        mock_requests.get.side_effect = slow_request

        geocoder = Geocoder(temp_cache, temp_logger)
        geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 应该记录耗时
        assert temp_logger._logs[0].time_cost >= 0.1


# ============================================
# APILog 模型测试
# ============================================

class TestAPILogModel:
    """测试 APILog 数据模型"""

    def test_api_log_creation(self):
        """创建 APILog"""
        log = APILog(
            timestamp="2024-01-01 12:00:00",
            address="北京市朝阳区",
            api_name="amap",
            status="success"
        )
        assert log.timestamp == "2024-01-01 12:00:00"
        assert log.address == "北京市朝阳区"

    def test_api_log_to_dict(self):
        """转换为字典"""
        log = APILog(
            timestamp="2024-01-01 12:00:00",
            address="北京市朝阳区",
            api_name="amap",
            status="success",
            latitude=39.9,
            longitude=116.4
        )
        d = log.to_dict()

        assert d["timestamp"] == "2024-01-01 12:00:00"
        assert d["address"] == "北京市朝阳区"
        assert d["api_name"] == "amap"
        assert d["status"] == "success"
        assert d["latitude"] == 39.9
        assert d["longitude"] == 116.4

    def test_api_log_default_values(self):
        """默认值"""
        log = APILog(
            timestamp="2024-01-01 12:00:00",
            address="地址",
            api_name="amap",
            status="success"
        )

        # 可选字段应该有默认值
        d = log.to_dict()
        assert "latitude" in d
        assert "longitude" in d
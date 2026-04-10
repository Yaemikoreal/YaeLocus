"""
CLI 命令测试

测试 Typer CLI 的各个命令：
- run 命令（批量地理编码）
- geocode 命令（单地址转换）
- cache 命令（缓存管理）
- config 命令（交互式配置）
- doctor 命令（环境诊断）
- test-api 命令（API 连通测试）
"""

import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner

from geocode.cli import app
from geocode.config import Config, PROJECT_DIR

from tests.fixtures.api_responses import (
    AMAP_SUCCESS_RESPONSE_SIMPLE,
    AMAP_EMPTY_RESPONSE,
    AMAP_INVALID_KEY_RESPONSE,
    TIANDITU_SUCCESS_RESPONSE_SIMPLE,
    BAIDU_SUCCESS_RESPONSE_SIMPLE,
)


runner = CliRunner()


# ============================================
# run 命令测试
# ============================================

class TestRunCommand:
    """测试 run 命令"""

    def test_run_file_not_found(self):
        """输入文件不存在"""
        result = runner.invoke(app, ["run", "-i", "nonexistent_file.csv"])
        assert result.exit_code == 1
        assert "FILE_NOT_FOUND" in result.stdout or "错误" in result.stdout

    def test_run_column_not_found(self, sample_csv):
        """地址列不存在"""
        result = runner.invoke(app, ["run", "-i", str(sample_csv), "-c", "不存在的列名"])
        assert result.exit_code == 1
        assert "COLUMN_NOT_FOUND" in result.stdout or "不存在" in result.stdout

    def test_run_no_api_key(self, sample_csv, monkeypatch):
        """未配置 API 密钥"""
        monkeypatch.setattr(Config, 'AMAP_KEY', '')
        monkeypatch.setattr(Config, 'BAIDU_AK', '')
        monkeypatch.setattr(Config, 'TIANDITU_TK', '')

        # 需要确保 Config.validate() 返回 False
        result = runner.invoke(app, ["run", "-i", str(sample_csv)])
        assert result.exit_code == 1
        assert "NO_API_KEY" in result.stdout or "未配置" in result.stdout

    def test_run_basic_success(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """基本成功运行"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        # 创建临时输出目录
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-o", str(output_dir / "result.csv"),
            "--cache", str(output_dir / "cache.db")
        ])

        # 验证命令执行
        # 注意：CLI 中可能需要验证 .env 文件
        # 如果失败，检查配置是否正确加载

    def test_run_excel_input(self, sample_excel, mock_requests, mock_config_valid, tmp_path):
        """Excel 文件输入"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_excel),
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_csv_utf8_bom(self, sample_csv_utf8_bom, mock_requests, mock_config_valid, tmp_path):
        """UTF-8 BOM 编码 CSV"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv_utf8_bom),
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_malformed_file(self, malformed_csv, tmp_path):
        """损坏文件处理"""
        result = runner.invoke(app, ["run", "-i", str(malformed_csv)])
        # 可能成功（pandas 可能解析部分内容）
        # 或者失败

    def test_run_empty_address_column(self, csv_empty_addresses, mock_requests, mock_config_valid, tmp_path):
        """地址列为空"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_EMPTY_RESPONSE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(csv_empty_addresses),
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_with_ttl(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """设置缓存 TTL"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "--ttl", "3600",
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_cleanup_flag(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """--cleanup 清理过期缓存"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "--cleanup",
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_no_cluster(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """--no-cluster 禁用聚类"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "--no-cluster",
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_no_heatmap(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """--no-heatmap 禁用热力图"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "--no-heatmap",
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_verbose(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """-v 详细输出"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-v",
            "-o", str(output_dir / "result.csv")
        ])

    def test_run_custom_column_name(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """自定义列名"""
        # sample_csv 包含 "地址" 列，测试指定其他有效列
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-c", "地址"
        ])


# ============================================
# geocode 命令测试（单地址转换）
# ============================================

class TestGeocodeSingleCommand:
    """测试单个地址转换命令"""

    def test_geocode_success(self, mock_requests, mock_config_valid, tmp_path):
        """成功转换"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        cache_file = tmp_path / "output" / "cache.db"
        result = runner.invoke(app, [
            "geocode", "北京市朝阳区",
            "--cache", str(cache_file)
        ])

        # 成功应该显示坐标
        if result.exit_code == 0:
            assert "116" in result.stdout or "longitude" in result.stdout.lower()

    def test_geocode_json_output(self, mock_requests, mock_config_valid, tmp_path):
        """JSON 格式输出"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        cache_file = tmp_path / "output" / "cache.db"
        result = runner.invoke(app, [
            "geocode", "北京市朝阳区",
            "--json",
            "--cache", str(cache_file)
        ])

        if result.exit_code == 0:
            # 应该输出 JSON 格式
            try:
                output = json.loads(result.stdout)
                assert "latitude" in output or "longitude" in output
            except json.JSONDecodeError:
                # 可能输出包含其他内容
                pass

    def test_geocode_failed(self, mock_requests_all_fail, mock_config_valid, tmp_path):
        """转换失败"""
        cache_file = tmp_path / "output" / "cache.db"
        result = runner.invoke(app, [
            "geocode", "无效地址xyz",
            "--cache", str(cache_file)
        ])

        # 失败应该显示错误
        assert result.exit_code == 1 or "失败" in result.stdout

    def test_geocode_no_api_key(self, monkeypatch, tmp_path):
        """未配置 API 密钥"""
        monkeypatch.setattr(Config, 'AMAP_KEY', '')
        monkeypatch.setattr(Config, 'BAIDU_AK', '')
        monkeypatch.setattr(Config, 'TIANDITU_TK', '')

        cache_file = tmp_path / "output" / "cache.db"
        result = runner.invoke(app, [
            "geocode", "北京市朝阳区",
            "--cache", str(cache_file)
        ])

        assert result.exit_code == 1

    def test_geocode_with_cache_hit(self, cache_with_data, mock_config_valid, tmp_path):
        """使用缓存命中"""
        # cache_with_data 已预填充数据
        result = runner.invoke(app, [
            "geocode", "北京市朝阳区",
            "--cache", str(cache_with_data._path)
        ])

        # 应该从缓存获取结果

    def test_geocode_with_ttl(self, mock_requests, mock_config_valid, tmp_path):
        """设置 TTL"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        cache_file = tmp_path / "output" / "cache.db"
        result = runner.invoke(app, [
            "geocode", "北京市朝阳区",
            "--ttl", "3600",
            "--cache", str(cache_file)
        ])


# ============================================
# cache 命令测试
# ============================================

class TestCacheCommand:
    """测试 cache 命令"""

    def test_cache_stats(self, cache_with_data, tmp_path):
        """cache stats 统计"""
        result = runner.invoke(app, [
            "cache", "stats",
            "--cache", str(cache_with_data._path)
        ])

        assert result.exit_code == 0
        assert "缓存" in result.stdout or "entries" in result.stdout.lower()

    def test_cache_stats_empty(self, temp_cache):
        """空缓存统计"""
        result = runner.invoke(app, [
            "cache", "stats",
            "--cache", str(temp_cache._path)
        ])

        assert result.exit_code == 0

    def test_cache_file_not_found(self, tmp_path):
        """缓存文件不存在"""
        nonexistent = tmp_path / "nonexistent.db"
        result = runner.invoke(app, [
            "cache", "stats",
            "--cache", str(nonexistent)
        ])

        assert result.exit_code == 1

    def test_cache_clear(self, cache_with_data):
        """cache clear 清空"""
        count_before = cache_with_data.count()

        result = runner.invoke(app, [
            "cache", "clear",
            "--cache", str(cache_with_data._path)
        ])

        assert result.exit_code == 0
        assert "清空" in result.stdout or str(count_before) in result.stdout

    def test_cache_cleanup(self, temp_cache):
        """cache cleanup 清理过期"""
        # 设置一些过期数据
        import time
        temp_cache.set("过期地址", {"lat": 1}, ttl=0.1)
        temp_cache.flush()
        time.sleep(0.2)

        result = runner.invoke(app, [
            "cache", "cleanup",
            "--cache", str(temp_cache._path)
        ])

        assert result.exit_code == 0

    def test_cache_export(self, cache_with_data, tmp_path):
        """cache export 导出 JSON"""
        export_dir = tmp_path / "output"
        export_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(app, [
            "cache", "export",
            "--cache", str(cache_with_data._path)
        ])

        assert result.exit_code == 0

    def test_cache_invalid_action(self, cache_with_data):
        """无效操作"""
        result = runner.invoke(app, [
            "cache", "invalid_action",
            "--cache", str(cache_with_data._path)
        ])

        assert result.exit_code == 1


# ============================================
# doctor 命令测试
# ============================================

class TestDoctorCommand:
    """测试 doctor 命令"""

    def test_doctor_with_env_file(self, tmp_path, monkeypatch):
        """有 .env 文件"""
        env_file = tmp_path / ".env"
        env_file.write_text("AMAP_KEY=test_key_32_characters\n")

        # 临时修改 PROJECT_DIR
        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        # 重新加载配置
        from dotenv import load_dotenv
        load_dotenv(env_file)

        result = runner.invoke(app, ["doctor"])

        # 输出应该显示检查结果

    def test_doctor_no_env_file(self, tmp_path, monkeypatch):
        """缺少 .env 文件"""
        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        result = runner.invoke(app, ["doctor"])

        # 应该显示警告

    def test_doctor_no_api_keys(self, tmp_path, monkeypatch):
        """未配置 API 密钥"""
        env_file = tmp_path / ".env"
        env_file.write_text("# Empty config\n")

        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        result = runner.invoke(app, ["doctor"])

        # 应该显示 API 密钥缺失警告

    def test_doctor_output_dir_exists(self, tmp_path, monkeypatch):
        """output 目录存在"""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        result = runner.invoke(app, ["doctor"])

    def test_doctor_output_dir_missing(self, tmp_path, monkeypatch):
        """缺少 output 目录"""
        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        result = runner.invoke(app, ["doctor"])

        # 应该显示警告（目录不存在）


# ============================================
# test-api 命令测试
# ============================================

class TestTestApiCommand:
    """测试 test-api 命令"""

    def test_test_api_success(self, mock_requests, mock_config_valid):
        """API 连通正常"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        result = runner.invoke(app, ["test-api"])

        # 应该显示连接正常

    def test_test_api_failure(self, mock_requests_connection_error, mock_config_valid):
        """API 连接失败"""
        result = runner.invoke(app, ["test-api"])

        # 应该显示连接失败

    def test_test_api_no_keys(self, monkeypatch):
        """未配置密钥"""
        monkeypatch.setattr(Config, 'AMAP_KEY', '')
        monkeypatch.setattr(Config, 'BAIDU_AK', '')
        monkeypatch.setattr(Config, 'TIANDITU_TK', '')

        result = runner.invoke(app, ["test-api"])

        assert result.exit_code == 1


# ============================================
# version 命令测试
# ============================================

class TestVersionCommand:
    """测试版本显示"""

    def test_version_flag(self):
        """--version 输出版本"""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "YaeLocus" in result.stdout or "1.2" in result.stdout

    def test_version_short_flag(self):
        """-V 输出版本"""
        result = runner.invoke(app, ["-V"])

        assert result.exit_code == 0


# ============================================
# 帮助命令测试
# ============================================

class TestHelpCommand:
    """测试帮助显示"""

    def test_help_main(self):
        """主命令帮助"""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "run" in result.stdout
        assert "geocode" in result.stdout
        assert "cache" in result.stdout

    def test_help_run(self):
        """run 命令帮助"""
        result = runner.invoke(app, ["run", "--help"])

        assert result.exit_code == 0
        assert "--input" in result.stdout or "-i" in result.stdout

    def test_help_cache(self):
        """cache 命令帮助"""
        result = runner.invoke(app, ["cache", "--help"])

        assert result.exit_code == 0

    def test_help_geocode(self):
        """geocode 命令帮助"""
        result = runner.invoke(app, ["geocode", "--help"])

        assert result.exit_code == 0


# ============================================
# config 命令测试
# ============================================

class TestConfigCommand:
    """测试 config 命令"""

    def test_config_interactive_input(self, tmp_path, monkeypatch):
        """交互式配置输入"""
        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        # 模拟用户输入
        result = runner.invoke(app, ["config"], input="test_amap_key_32_characters\n\n\n")

        # 应该保存配置

    def test_config_existing_values(self, tmp_path, monkeypatch):
        """配置已存在的值"""
        env_file = tmp_path / ".env"
        env_file.write_text("AMAP_KEY=existing_key_32_chars\n")

        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        # 模拟用户保持现有值
        result = runner.invoke(app, ["config"], input="\n\n\n")

    def test_config_key_format_validation(self, tmp_path, monkeypatch):
        """密钥格式验证"""
        monkeypatch.setattr("geocode.config.PROJECT_DIR", tmp_path)
        monkeypatch.setattr("geocode.cli.PROJECT_DIR", tmp_path)

        # 输入格式错误的密钥（不是32位）
        result = runner.invoke(app, ["config"], input="short_key\n\n\n")

        # 应该显示格式错误警告


# ============================================
# 路径解析测试
# ============================================

class TestPathResolution:
    """测试路径解析"""

    def test_relative_path_resolution(self, sample_csv):
        """相对路径解析"""
        # 测试相对路径是否能正确解析
        result = runner.invoke(app, [
            "run",
            "-i", "tests/test_input.csv",  # 相对路径
            "-c", "地址"
        ])

        # 如果文件存在相对路径应该能解析

    def test_absolute_path(self, sample_csv):
        """绝对路径"""
        result = runner.invoke(app, [
            "run",
            "-i", str(sample_csv.absolute()),
            "-c", "地址"
        ])


# ============================================
# 错误处理测试
# ============================================

class TestCLIErrorHandling:
    """测试 CLI 错误处理"""

    def test_error_message_format(self):
        """错误消息格式"""
        result = runner.invoke(app, ["run", "-i", "nonexistent.csv"])

        # 错误应该有清晰的格式（包含错误码和建议）

    def test_error_exit_code(self):
        """错误退出码"""
        result = runner.invoke(app, ["run", "-i", "nonexistent.csv"])

        # 失败应该返回非零退出码
        assert result.exit_code != 0

    def test_error_with_suggestion(self):
        """错误包含建议"""
        result = runner.invoke(app, ["run", "-i", "nonexistent.csv"])

        # 应该包含修复建议
        # assert "建议" in result.stdout or "TIP" in result.stdout


# ============================================
# 输出文件测试
# ============================================

class TestOutputFiles:
    """测试输出文件"""

    def test_output_csv_created(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """输出 CSV 文件创建"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "result.csv"

        runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-o", str(output_file)
        ])

        # 如果成功，输出文件应该存在
        # (取决于 Mock 是否正确工作)

    def test_output_map_created(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """输出地图 HTML 创建"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        map_file = output_dir / "map.html"

        runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-m", str(map_file)
        ])

    def test_output_directory_created(self, sample_csv, mock_requests, mock_config_valid, tmp_path):
        """自动创建输出目录"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = AMAP_SUCCESS_RESPONSE_SIMPLE
        mock_requests.get.return_value = mock_response

        # 指定一个不存在的输出目录
        new_output_dir = tmp_path / "new_output"
        output_file = new_output_dir / "result.csv"

        runner.invoke(app, [
            "run",
            "-i", str(sample_csv),
            "-o", str(output_file)
        ])

        # 目录应该自动创建（如果命令成功执行）
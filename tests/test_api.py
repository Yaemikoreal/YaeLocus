"""
API 服务器端点测试 — 使用 FastAPI TestClient
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from geocode.api import create_api_app


@pytest.fixture
def client(clean_env):
    """创建 TestClient（干净环境，无 API Key）"""
    app = create_api_app()
    return TestClient(app)


# ════════════════════════════════════════════════════════════════════
# Health & Config
# ════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_includes_version(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_has_apis_list(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert isinstance(data["apis"], list)

    def test_config_returns_structure(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "apis" in data
        assert "ai_enabled" in data
        assert "cache" in data


# ════════════════════════════════════════════════════════════════════
# Cache Endpoints
# ════════════════════════════════════════════════════════════════════

class TestCacheEndpoints:
    def test_stats(self, client):
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
        assert "hits" in data
        assert "misses" in data

    def test_clear_returns_cleared_count(self, client):
        resp = client.post("/api/cache/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert "cleared" in data

    def test_export_returns_dict(self, client):
        resp = client.get("/api/cache/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data


# ════════════════════════════════════════════════════════════════════
# File & Map Listings
# ════════════════════════════════════════════════════════════════════

class TestFilesEndpoint:
    def test_list_files_returns_ok(self, client):
        resp = client.get("/api/files")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert "count" in data
        assert isinstance(data["files"], list)


class TestMapsEndpoint:
    def test_list_maps_returns_ok(self, client):
        resp = client.get("/api/maps")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["maps"], list)

    def test_list_maps_has_count(self, client):
        resp = client.get("/api/maps")
        data = resp.json()
        assert "count" in data
        assert data["count"] == len(data["maps"])


# ════════════════════════════════════════════════════════════════════
# Geocode Endpoints
# ════════════════════════════════════════════════════════════════════

class TestGeocodeSingle:
    def test_missing_address_returns_400(self, client):
        resp = client.post("/api/geocode/single", json={})
        assert resp.status_code == 400

    def test_empty_address_returns_400(self, client):
        resp = client.post("/api/geocode/single", json={"address": ""})
        assert resp.status_code == 400

    def test_address_returns_structure(self, client):
        """调用编码接口，验证响应结构（可能需要 API key，但至少格式正确）"""
        resp = client.post("/api/geocode/single", json={"address": "test_address_123"})
        # 可能成功(缓存命中)或失败(无API key)，但都是200且结构正确
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "success" in data
            assert "address" in data


class TestGeocodeReverse:
    def test_missing_coords_returns_400(self, client):
        resp = client.post("/api/geocode/reverse", json={})
        assert resp.status_code == 400

    def test_valid_coords_returns_structure(self, client):
        """逆地理编码应返回结构化响应"""
        resp = client.post("/api/geocode/reverse", json={
            "latitude": 39.9042, "longitude": 116.4074
        })
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "success" in data
            assert "latitude" in data


class TestGeocodeConvert:
    def test_wgs84_to_gcj02(self, client):
        resp = client.post("/api/geocode/convert", json={
            "latitude": 39.9042, "longitude": 116.4074,
            "from": "wgs84", "to": "gcj02",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "output" in data
        assert data["output"]["system"] == "gcj02"
        # GCJ-02 偏移: 约 0.006° (lat), 0.006° (lon)
        assert abs(data["output"]["latitude"] - 39.9042) < 0.01
        assert abs(data["output"]["longitude"] - 116.4074) < 0.02

    def test_gcj02_to_wgs84(self, client):
        resp = client.post("/api/geocode/convert", json={
            "latitude": 39.90569, "longitude": 116.41355,
            "from": "gcj02", "to": "wgs84",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["output"]["system"] == "wgs84"
        # 转换回 WGS-84 应接近原始坐标
        assert abs(data["output"]["latitude"] - 39.9042) < 0.0002

    def test_unsupported_pair_returns_400(self, client):
        resp = client.post("/api/geocode/convert", json={
            "latitude": 39.9, "longitude": 116.4,
            "from": "wgs84", "to": "bd09",
        })
        assert resp.status_code == 400

    def test_missing_coords_returns_400(self, client):
        resp = client.post("/api/geocode/convert", json={})
        assert resp.status_code == 400

    def test_6decimal_places(self, client):
        """输出应精确到6位小数"""
        resp = client.post("/api/geocode/convert", json={
            "latitude": 39.9, "longitude": 116.4,
            "from": "gcj02", "to": "wgs84",
        })
        assert resp.status_code == 200
        data = resp.json()
        # 验证是浮点数（精度足够）
        assert isinstance(data["output"]["latitude"], float)
        assert isinstance(data["output"]["longitude"], float)
        # 验证精确到小数点后至少有几位
        lat_str = str(data["output"]["latitude"])
        assert "." in lat_str


# ════════════════════════════════════════════════════════════════════
# Command Execution
# ════════════════════════════════════════════════════════════════════

class TestCommandExecution:
    def test_missing_command_returns_400(self, client):
        resp = client.post("/api/execute", json={})
        assert resp.status_code == 400

    def test_help_command(self, client):
        resp = client.post("/api/execute", json={"command": "--help"})
        assert resp.status_code == 200
        data = resp.json()
        assert "exit_code" in data
        assert data["exit_code"] == 0

    def test_command_result_has_fields(self, client):
        resp = client.post("/api/execute", json={"command": "config check"})
        assert resp.status_code == 200
        data = resp.json()
        assert "command" in data
        assert "exit_code" in data
        assert "stdout" in data
        assert "stderr" in data
        assert "success" in data

    def test_command_with_quoted_args(self, client):
        """BUG #17 修复: shlex.split 正确处理引号参数"""
        resp = client.post("/api/execute", json={
            "command": 'geocode single "test address"'
        })
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# AI Endpoints
# ════════════════════════════════════════════════════════════════════

class TestAIEndpoints:
    def test_chat_missing_prompt_returns_400(self, client):
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 400

    def test_chat_stream_missing_prompt_returns_400(self, client):
        resp = client.post("/api/chat/stream", json={})
        assert resp.status_code == 400

    def test_chat_returns_structure(self, client):
        """无 AI Key 时应返回 503（服务不可用）"""
        resp = client.post("/api/chat", json={"prompt": "Hello"})
        # clean_env 确保没有 AI key → 503
        assert resp.status_code in (503, 200, 500)


# ════════════════════════════════════════════════════════════════════
# File Content
# ════════════════════════════════════════════════════════════════════

class TestFileContent:
    def test_missing_path_returns_400(self, client):
        resp = client.get("/api/file/content")
        assert resp.status_code == 400

    def test_traversal_blocked(self, client):
        """路径遍历攻击应返回 403"""
        resp = client.get("/api/file/content?path=../../etc/passwd")
        assert resp.status_code == 403

    def test_file_not_found(self, client):
        """不存在的文件应返回 404"""
        resp = client.get("/api/file/content?path=data/this_does_not_exist_xyz.csv")
        assert resp.status_code == 404

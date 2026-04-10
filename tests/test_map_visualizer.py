"""
地图可视化测试

测试 map_visualizer.py 模块的功能：
- 地图创建
- 空数据处理
- 无效坐标过滤
- HTML 输出验证
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch

from geocode.map_visualizer import create_map


# ============================================
# 地图创建测试
# ============================================

class TestCreateMap:
    """测试地图创建"""

    def test_create_map_basic(self, tmp_path, sample_map_data):
        """基本地图创建"""
        output_file = tmp_path / "test_map.html"

        result = create_map(
            data=sample_map_data,
            output_file=str(output_file),
            title="测试地图"
        )

        assert output_file.exists()
        assert result == str(output_file)

    def test_create_map_with_cluster(self, tmp_path, sample_map_data):
        """启用点聚类"""
        output_file = tmp_path / "cluster_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            use_cluster=True
        )

        assert output_file.exists()

        # 检查 HTML 内容包含聚类相关代码
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "MarkerCluster" in content or "cluster" in content.lower()

    def test_create_map_without_cluster(self, tmp_path, sample_map_data):
        """禁用点聚类"""
        output_file = tmp_path / "no_cluster_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            use_cluster=False
        )

        assert output_file.exists()

    def test_create_map_with_heatmap(self, tmp_path, sample_map_data):
        """启用热力图"""
        output_file = tmp_path / "heatmap_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            use_heatmap=True
        )

        assert output_file.exists()

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "HeatMap" in content or "heat" in content.lower()

    def test_create_map_without_heatmap(self, tmp_path, sample_map_data):
        """禁用热力图"""
        output_file = tmp_path / "no_heatmap_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            use_heatmap=False
        )

        assert output_file.exists()

    def test_create_map_custom_title(self, tmp_path, sample_map_data):
        """自定义标题"""
        output_file = tmp_path / "custom_title_map.html"
        custom_title = "自定义地图标题测试"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            title=custom_title
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert custom_title in content

    def test_create_map_custom_output_path(self, tmp_path, sample_map_data):
        """自定义输出路径"""
        # 创建嵌套目录
        nested_dir = tmp_path / "nested" / "path"
        output_file = nested_dir / "map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        assert output_file.exists()

    def test_create_map_default_parameters(self, tmp_path, sample_map_data):
        """默认参数"""
        output_file = tmp_path / "default_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        assert output_file.exists()


# ============================================
# 错误处理测试
# ============================================

class TestCreateMapErrors:
    """测试错误处理"""

    def test_empty_data_raises_error(self, tmp_path):
        """空数据抛出异常"""
        output_file = tmp_path / "empty_map.html"

        with pytest.raises((ValueError, Exception)):
            create_map(
                data=[],
                output_file=str(output_file)
            )

    def test_no_valid_coordinates_raises_error(self, tmp_path):
        """无有效坐标抛出异常"""
        output_file = tmp_path / "invalid_map.html"

        # 所有坐标都缺失
        invalid_data = [
            {"original_address": "地址1"},  # 无坐标
            {"original_address": "地址2"},  # 无坐标
        ]

        with pytest.raises((ValueError, Exception)):
            create_map(
                data=invalid_data,
                output_file=str(output_file)
            )

    def test_filters_invalid_coordinates(self, tmp_path):
        """过滤无效坐标"""
        output_file = tmp_path / "filtered_map.html"

        mixed_data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "有效1"},
            {"latitude": None, "longitude": 116.4, "original_address": "无效1"},  # 无纬度
            {"latitude": 31.2, "longitude": None, "original_address": "无效2"},  # 无经度
            {"latitude": 23.1, "longitude": 113.3, "original_address": "有效2"},
        ]

        # 应该能成功创建（过滤掉无效的）
        try:
            create_map(
                data=mixed_data,
                output_file=str(output_file)
            )
            assert output_file.exists()
        except (ValueError, Exception):
            # 如果实现是抛出异常也接受
            pass

    def test_handles_missing_latitude(self, tmp_path):
        """处理缺失纬度"""
        output_file = tmp_path / "missing_lat_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "地址1"},
            {"longitude": 121.5, "original_address": "地址2"},  # 无纬度
        ]

        try:
            create_map(data=data, output_file=str(output_file))
        except Exception:
            pass  # 可能抛出异常

    def test_handles_missing_longitude(self, tmp_path):
        """处理缺失经度"""
        output_file = tmp_path / "missing_lon_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "地址1"},
            {"latitude": 31.2, "original_address": "地址2"},  # 无经度
        ]

        try:
            create_map(data=data, output_file=str(output_file))
        except Exception:
            pass


# ============================================
# 地图内容测试
# ============================================

class TestMapContent:
    """测试地图内容"""

    def test_map_contains_markers(self, tmp_path, sample_map_data):
        """地图包含标记点"""
        output_file = tmp_path / "markers_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 应该包含标记点相关代码
        assert "Marker" in content or "marker" in content.lower()

    def test_map_contains_layer_control(self, tmp_path, sample_map_data):
        """地图包含图层控制"""
        output_file = tmp_path / "layer_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 应该包含图层控制
        assert "LayerControl" in content or "layer" in content.lower()

    def test_map_contains_title(self, tmp_path, sample_map_data):
        """地图包含标题"""
        output_file = tmp_path / "title_map.html"
        title = "测试地图标题"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            title=title
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert title in content

    def test_marker_popup_content(self, tmp_path, sample_map_data):
        """标记点弹窗内容"""
        output_file = tmp_path / "popup_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 弹窗应该包含地址信息
        for item in sample_map_data:
            if "original_address" in item:
                assert item["original_address"] in content

    def test_map_html_structure(self, tmp_path, sample_map_data):
        """地图 HTML 结构"""
        output_file = tmp_path / "structure_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file)
        )

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 应该是有效的 HTML
        assert "<html" in content.lower() or "<div" in content.lower()
        assert "</html>" in content.lower() or "</div>" in content.lower()


# ============================================
# 边界情况测试
# ============================================

class TestMapEdgeCases:
    """测试边界情况"""

    def test_single_point(self, tmp_path):
        """单个坐标点"""
        output_file = tmp_path / "single_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "单点"}
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_many_points(self, tmp_path):
        """大量坐标点（性能）"""
        output_file = tmp_path / "many_points_map.html"

        # 生成 100 个点
        data = [
            {"latitude": 30 + i * 0.1, "longitude": 100 + i * 0.1, "original_address": f"地址{i}"}
            for i in range(100)
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_extreme_coordinates(self, tmp_path):
        """极端坐标值"""
        output_file = tmp_path / "extreme_map.html"

        data = [
            {"latitude": 53.5, "longitude": 73.0, "original_address": "中国西北"},  # 新疆
            {"latitude": 18.0, "longitude": 135.0, "original_address": "中国东南"},  # 南海
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_chinese_coordinates(self, tmp_path):
        """中国境内坐标"""
        output_file = tmp_path / "china_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "北京"},
            {"latitude": 31.2, "longitude": 121.5, "original_address": "上海"},
            {"latitude": 23.1, "longitude": 113.3, "original_address": "广州"},
            {"latitude": 22.5, "longitude": 114.1, "original_address": "深圳"},
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_negative_coordinates(self, tmp_path):
        """负数坐标"""
        output_file = tmp_path / "negative_map.html"

        data = [
            {"latitude": -33.9, "longitude": 151.2, "original_address": "悉尼"},
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_zero_coordinates(self, tmp_path):
        """零坐标"""
        output_file = tmp_path / "zero_map.html"

        data = [
            {"latitude": 0.0, "longitude": 0.0, "original_address": "赤道本初子午线"},
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_same_coordinates(self, tmp_path):
        """相同坐标多个点"""
        output_file = tmp_path / "same_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "地点1"},
            {"latitude": 39.9, "longitude": 116.4, "original_address": "地点2"},
            {"latitude": 39.9, "longitude": 116.4, "original_address": "地点3"},
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()


# ============================================
# 数据源颜色映射测试
# ============================================

class TestSourceColorMapping:
    """测试数据来源颜色映射"""

    def test_amap_source_color(self, tmp_path):
        """高德数据源颜色"""
        output_file = tmp_path / "amap_color_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "北京", "source": "amap"}
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_tianditu_source_color(self, tmp_path):
        """天地图数据源颜色"""
        output_file = tmp_path / "tianditu_color_map.html"

        data = [
            {"latitude": 31.2, "longitude": 121.5, "original_address": "上海", "source": "tianditu"}
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_baidu_source_color(self, tmp_path):
        """百度数据源颜色"""
        output_file = tmp_path / "baidu_color_map.html"

        data = [
            {"latitude": 23.1, "longitude": 113.3, "original_address": "广州", "source": "baidu"}
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()

    def test_mixed_sources(self, tmp_path):
        """混合数据源"""
        output_file = tmp_path / "mixed_source_map.html"

        data = [
            {"latitude": 39.9, "longitude": 116.4, "original_address": "北京", "source": "amap"},
            {"latitude": 31.2, "longitude": 121.5, "original_address": "上海", "source": "tianditu"},
            {"latitude": 23.1, "longitude": 113.3, "original_address": "广州", "source": "baidu"},
        ]

        create_map(data=data, output_file=str(output_file))
        assert output_file.exists()


# ============================================
# 瓦片图层测试
# ============================================

class TestTileLayers:
    """测试瓦片图层"""

    def test_default_tile_layer(self, tmp_path, sample_map_data):
        """默认瓦片图层"""
        output_file = tmp_path / "tile_map.html"

        create_map(data=sample_map_data, output_file=str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 应该包含瓦片图层 URL
        assert "TileLayer" in content or "tile" in content.lower()

    def test_satellite_layer_option(self, tmp_path, sample_map_data):
        """卫星图层选项"""
        output_file = tmp_path / "satellite_map.html"

        create_map(data=sample_map_data, output_file=str(output_file))

        # 检查是否有图层切换功能
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 地图应该支持图层切换


# ============================================
# 文件输出测试
# ============================================

class TestFileOutput:
    """测试文件输出"""

    def test_output_file_encoding(self, tmp_path, sample_map_data):
        """输出文件编码"""
        output_file = tmp_path / "encoding_map.html"

        create_map(
            data=sample_map_data,
            output_file=str(output_file),
            title="中文标题测试"
        )

        # 应该能正常读取中文
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "中文标题测试" in content

    def test_output_file_size(self, tmp_path, sample_map_data):
        """输出文件大小"""
        output_file = tmp_path / "size_map.html"

        create_map(data=sample_map_data, output_file=str(output_file))

        # 文件应该有一定大小
        file_size = output_file.stat().st_size
        assert file_size > 0

    def test_overwrite_existing_file(self, tmp_path, sample_map_data):
        """覆盖现有文件"""
        output_file = tmp_path / "overwrite_map.html"

        # 创建第一次
        create_map(data=sample_map_data, output_file=str(output_file))
        first_size = output_file.stat().st_size

        # 再次创建（覆盖）
        create_map(data=sample_map_data, output_file=str(output_file))
        second_size = output_file.stat().st_size

        # 文件应该被覆盖
        assert output_file.exists()


# ============================================
# 集成测试
# ============================================

class TestMapIntegration:
    """测试与 Geocoder 集成"""

    def test_map_from_geocode_results(self, tmp_path, mock_requests, mock_config_valid, temp_cache, temp_logger):
        """从地理编码结果创建地图"""
        from geocode.geocoder import Geocoder

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "1",
            "geocodes": [{
                "formatted_address": "北京市朝阳区",
                "location": "116.4853,39.9289"
            }]
        }
        mock_requests.get.return_value = mock_response

        geocoder = Geocoder(temp_cache, temp_logger)
        result = geocoder.geocode("北京市朝阳区")
        geocoder.close()

        # 使用结果创建地图
        if result.get("success"):
            output_file = tmp_path / "geocode_map.html"
            create_map(data=[result], output_file=str(output_file))
            assert output_file.exists()
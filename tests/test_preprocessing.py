"""
预处理模块测试

测试无效数据过滤和地址标准化
"""

import pytest
from geocode.preprocessing import InvalidAddressFilter, AddressNormalizer


class TestInvalidAddressFilter:
    """无效数据过滤测试"""

    def test_filter_zero(self):
        """过滤0值"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("0")
        assert is_valid is False
        # "0" 长度为1，会被 too_short 或 invalid_pattern 过滤
        assert reason in ["invalid_pattern", "too_short"]

    def test_filter_float_zero(self):
        """过滤0.0"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("0.0")
        assert is_valid is False
        assert reason == "invalid_pattern"

    def test_filter_pure_number(self):
        """过滤纯数字"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("12345")
        assert is_valid is False
        assert reason == "invalid_pattern"

    def test_filter_none_value(self):
        """过滤None"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid(None)
        assert is_valid is False
        assert reason == "null_value"

    def test_filter_empty_string(self):
        """过滤空字符串"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("")
        assert is_valid is False
        assert reason == "empty"

    def test_filter_whitespace(self):
        """过滤空白字符"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("   ")
        assert is_valid is False
        assert reason == "empty"

    def test_filter_short_address(self):
        """过滤过短地址"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("京")
        assert is_valid is False
        assert reason == "too_short"

    def test_accept_valid_address(self):
        """接受有效地址"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("北京市朝阳区")
        assert is_valid is True
        assert reason == "valid"

    def test_accept_complex_address(self):
        """接受复杂地址"""
        filter_obj = InvalidAddressFilter()
        is_valid, reason = filter_obj.is_valid("龙马潭区王氏商城C2区16号")
        assert is_valid is True
        assert reason == "valid"

    def test_batch_filter(self):
        """批量过滤测试"""
        filter_obj = InvalidAddressFilter()
        addresses = ["北京市朝阳区", "0", "龙马潭区", None, "123", "上海市浦东新区"]
        valid, stats = filter_obj.filter_addresses(addresses)
        assert len(valid) == 3
        assert stats["invalid"] == 3
        # "0" 和 "123" 都被 invalid_pattern 或 too_short 过滤
        invalid_total = stats["reasons"].get("invalid_pattern", 0) + stats["reasons"].get("too_short", 0)
        assert invalid_total >= 2


class TestAddressNormalizer:
    """地址标准化测试"""

    def test_province_completion_luzhou(self):
        """泸州区县省份补全"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("龙马潭区王氏商城C2区16号")
        # 应推断为四川省
        assert meta.get("province_hint") == "四川省"
        assert "四川省" in normalized

    def test_province_completion_jiangyang(self):
        """江阳区省份补全"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("江阳区龙透关路29号")
        assert meta.get("province_hint") == "四川省"
        assert "四川省" in normalized

    def test_no_province_if_already_present(self):
        """已有省份不重复补全"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("四川省龙马潭区王氏商城")
        # 已有省份，不重复添加
        assert normalized.count("四川省") <= 1

    def test_province_hint_for_beijing(self):
        """北京区县推断"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("朝阳区建国路88号")
        assert meta.get("province_hint") == "北京市"

    def test_province_hint_for_shanghai(self):
        """上海区县推断"""
        normalizer = AddressNormalizer()
        # 使用更具体的上海区县名称
        normalized, meta = normalizer.normalize("黄浦区南京路")
        assert meta.get("province_hint") == "上海市"

    def test_province_hint_for_shenzhen(self):
        """深圳区县推断"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("南山区科技园")
        assert meta.get("province_hint") == "广东省"

    def test_clean_basic_separators(self):
        """分隔符清洗"""
        normalizer = AddressNormalizer()
        normalized, _ = normalizer.normalize("北京市，朝阳区；建国路")
        # 分隔符统一为空格
        assert "，" not in normalized
        assert "；" not in normalized

    def test_empty_address(self):
        """空地址处理"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("")
        assert normalized == ""
        assert meta.get("valid") is False


class TestIntegration:
    """集成测试"""

    def test_filter_then_normalize(self):
        """先过滤再标准化"""
        filter_obj = InvalidAddressFilter()
        normalizer = AddressNormalizer()

        # 无效数据
        is_valid, _ = filter_obj.is_valid("0")
        assert is_valid is False

        # 有效数据标准化
        normalized, meta = normalizer.normalize("龙马潭区王氏商城")
        assert meta.get("province_hint") == "四川省"

    def test_cross_province_keyword_coverage(self):
        """跨省关键词覆盖测试"""
        normalizer = AddressNormalizer()

        # 测试泸州各区县
        luzhou_districts = ["龙马潭", "江阳", "纳溪", "泸县", "合江", "叙永", "古蔺"]
        for district in luzhou_districts:
            normalized, meta = normalizer.normalize(f"{district}区某街道")
            assert meta.get("province_hint") == "四川省"
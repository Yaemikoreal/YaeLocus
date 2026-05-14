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
    """地址标准化测试（简化版 - 只清洗符号）"""

    def test_clean_separators(self):
        """分隔符清洗"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("北京市，朝阳区；建国路")
        # 分隔符统一为空格
        assert "，" not in normalized
        assert "；" not in normalized
        assert meta.get("valid") is True

    def test_clean_code_marker(self):
        """编号标记清洗"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("东坡区xxx路(RS01656)")
        # 去除末尾编号标记
        assert "(RS01656)" not in normalized
        assert "RS01656" not in normalized
        assert normalized == "东坡区xxx路"
        assert meta.get("valid") is True

    def test_clean_brackets(self):
        """方括号编号清洗"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("龙马潭区王氏商城【编号123】")
        assert "【编号123】" not in normalized
        assert normalized == "龙马潭区王氏商城"
        assert meta.get("valid") is True

    def test_no_province_modification(self):
        """不修改地址内容（不添加省份）"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("龙马潭区王氏商城C2区16号")
        # 地址内容不应被修改
        assert normalized == "龙马潭区王氏商城C2区16号"
        # 不应添加省份前缀
        assert "四川省" not in normalized
        # 无 province_hint 字段
        assert meta.get("province_hint") is None

    def test_empty_address(self):
        """空地址处理"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("")
        assert normalized == ""
        assert meta.get("valid") is False

    def test_whitespace_address(self):
        """空白地址处理"""
        normalizer = AddressNormalizer()
        normalized, meta = normalizer.normalize("   ")
        assert normalized == ""
        assert meta.get("valid") is False

    def test_get_expected_province_deprecated(self):
        """get_expected_province 已弃用"""
        normalizer = AddressNormalizer()
        result = normalizer.get_expected_province("龙马潭区")
        assert result is None


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
        normalized, meta = normalizer.normalize("龙马潭区王氏商城(RS001)")
        assert normalized == "龙马潭区王氏商城"
        assert meta.get("province_hint") is None  # 不再推断省份

    def test_normalizer_preserves_address(self):
        """标准化器保留地址内容"""
        normalizer = AddressNormalizer()

        # 测试多个地址
        test_cases = [
            ("北京市朝阳区建国路88号", "北京市朝阳区建国路88号"),
            ("东坡区某街道(RS123)", "东坡区某街道"),
            ("龙马潭区,王氏商城", "龙马潭区 王氏商城"),
        ]

        for original, expected in test_cases:
            normalized, meta = normalizer.normalize(original)
            assert normalized == expected
            assert meta.get("province_hint") is None
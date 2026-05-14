"""地址拆分器测试"""

import pytest
from geocode.preprocessing import AddressSplitter


class TestAddressSplitter:
    """测试 AddressSplitter 类"""

    def setup_method(self):
        self.splitter = AddressSplitter()

    def test_split_with_pipe_separator(self):
        """测试管道符分隔格式"""
        # 眉山数据格式
        address = "某某分公司|眉山市仁寿县xxx小区xxx号"
        result = self.splitter.split(address)

        assert result["has_separator"] is True
        assert result["company"] == "某某分公司"
        assert result["address"] == "眉山市仁寿县xxx小区xxx号"

    def test_split_with_code_suffix(self):
        """测试末尾编号清理"""
        address = "某某分公司|眉山市仁寿县xxx小区xxx号(RS01656)"
        result = self.splitter.split(address)

        assert result["has_separator"] is True
        assert result["company"] == "某某分公司"
        assert result["address"] == "眉山市仁寿县xxx小区xxx号"
        assert "(RS01656)" not in result["address"]

    def test_split_with_chinese_pipe(self):
        """测试中文竖线分隔"""
        address = "公司名｜北京市朝阳区xxx路"
        result = self.splitter.split(address)

        assert result["has_separator"] is True
        assert result["company"] == "公司名"
        assert result["address"] == "北京市朝阳区xxx路"

    def test_split_without_separator(self):
        """测试无分隔符的普通地址"""
        address = "北京市朝阳区建国路88号"
        result = self.splitter.split(address)

        assert result["has_separator"] is False
        assert result["company"] == ""
        assert result["address"] == "北京市朝阳区建国路88号"

    def test_split_empty_address(self):
        """测试空地址"""
        result = self.splitter.split("")

        assert result["has_separator"] is False
        assert result["address"] == ""

    def test_split_none_address(self):
        """测试 None 地址"""
        result = self.splitter.split(None)

        assert result["has_separator"] is False
        assert result["address"] == ""

    def test_extract_address_simple(self):
        """测试简化接口 extract_address"""
        address = "公司|眉山市东坡区xxx路"
        extracted = self.splitter.extract_address(address)

        assert extracted == "眉山市东坡区xxx路"

    def test_has_special_format(self):
        """测试特殊格式检测"""
        assert self.splitter.has_special_format("公司|地址") is True
        assert self.splitter.has_special_format("公司｜地址") is True
        assert self.splitter.has_special_format("普通地址") is False

    def test_code_patterns(self):
        """测试各种编号格式清理"""
        test_cases = [
            ("地址(RS01656)", "地址"),
            ("地址【编号】", "地址"),
            ("地址[ABC123]", "地址"),
            ("地址（中文括号）", "地址"),
        ]

        for input_addr, expected in test_cases:
            result = self.splitter.split(input_addr)
            assert result["address"] == expected

    def test_whitespace_handling(self):
        """测试空白处理"""
        address = "  公司名  |  地址内容  "
        result = self.splitter.split(address)

        assert result["company"] == "公司名"
        assert result["address"] == "地址内容"

    def test_real_meishan_data_samples(self):
        """测试真实眉山数据样本"""
        # 基于真实数据格式的测试
        samples = [
            "某某分公司|眉山市仁寿县xxx小区xxx号(RS01656)",
            "某某分公司|眉山市彭山区xxx路xxx号(RS08950)",
            "某某分公司|眉山市东坡区xxx小区xxx号(RS53085)",
        ]

        for sample in samples:
            result = self.splitter.split(sample)
            assert result["has_separator"] is True
            assert "眉山市" in result["address"]
            # 编号应该被清理
            assert "(RS" not in result["address"]
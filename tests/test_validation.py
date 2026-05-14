"""
置信度校验测试

测试置信度评分和跨省错误检测
"""

import pytest
from geocode.validation import ConfidenceValidator, ConfidenceScore, CrossProvinceChecker


class TestConfidenceValidator:
    """置信度评分测试（简化版）"""

    def test_valid_result_high_confidence(self):
        """有效结果高置信度"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "泸州市",
            "district": "龙马潭区",
            "formatted_address": "四川省泸州市龙马潭区王氏商城...",
            "latitude": 28.9,
            "longitude": 105.4
        }

        score = validator.validate(
            "龙马潭区王氏商城C2区16号",
            result
        )

        assert score.total >= 60
        assert score.is_trustworthy is True
        # 区划完整：省+市+区 = 15+15+10 = 40
        assert score.completeness == 40

    def test_coord_out_of_china(self):
        """坐标超出中国境内"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "泸州市",
            "district": "龙马潭区",
            "formatted_address": "四川省泸州市龙马潭区...",
            "latitude": 10.0,  # 不在中国境内
            "longitude": 100.0
        }

        score = validator.validate(
            "龙马潭区王氏商城",
            result
        )

        assert any("超出中国境内" in issue for issue in score.issues)
        assert score.coord_valid < 20

    def test_completeness_missing_district(self):
        """区划完整性 - 缺少区"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "泸州市",
            "district": None,
            "formatted_address": "四川省泸州市...",
            "latitude": 28.9,
            "longitude": 105.4
        }

        score = validator.validate(
            "龙马潭区王氏商城",
            result
        )

        assert any("district缺失" in issue for issue in score.issues)
        # 省+市 = 15+15 = 30
        assert score.completeness == 30

    def test_completeness_missing_all(self):
        """区划完整性 - 全缺失"""
        validator = ConfidenceValidator()

        result = {
            "province": None,
            "city": None,
            "district": None,
            "formatted_address": "某地...",
            "latitude": 28.9,
            "longitude": 105.4
        }

        score = validator.validate("某地", result)

        assert score.completeness == 0
        assert "province缺失" in score.issues
        assert "city缺失" in score.issues
        assert "district缺失" in score.issues

    def test_address_keyword_match(self):
        """地址关键词匹配"""
        validator = ConfidenceValidator()

        result = {
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "formatted_address": "北京市朝阳区建国路88号",
            "latitude": 39.9,
            "longitude": 116.4
        }

        score = validator.validate(
            "北京市朝阳区建国路88号",
            result
        )

        # 关键词高度匹配（北京市、朝阳区、建国路）
        assert score.address_match >= 30

    def test_address_keyword_no_match(self):
        """地址关键词无匹配"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "成都市",
            "district": "高新区",
            "formatted_address": "四川省成都市高新区...",
            "latitude": 30.5,
            "longitude": 104.0
        }

        score = validator.validate("某路88号", result)

        # "某路" 关键词不在 formatted_address 中，重叠率为 0
        # 但区划完整和坐标合理，总分仍可达 60
        assert score.address_match == 0
        assert score.total >= 60  # completeness(40) + coord_valid(20)

    def test_no_formatted_address(self):
        """formatted_address缺失"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "成都市",
            "district": "高新区",
            "formatted_address": "",
            "latitude": 30.5,
            "longitude": 104.0
        }

        score = validator.validate("某路88号", result)

        assert score.address_match == 0
        assert "formatted_address缺失" in score.issues

    def test_province_hint_deprecated(self):
        """province_hint 参数已弃用"""
        validator = ConfidenceValidator()

        result = {
            "province": "四川省",
            "city": "泸州市",
            "district": "龙马潭区",
            "formatted_address": "四川省泸州市龙马潭区...",
            "latitude": 28.9,
            "longitude": 105.4
        }

        # province_hint 传入但不再影响评分
        score_with_hint = validator.validate("龙马潭区", result, province_hint="四川省")
        score_no_hint = validator.validate("龙马潭区", result, province_hint=None)

        # 两者评分应相同
        assert score_with_hint.total == score_no_hint.total


class TestCrossProvinceChecker:
    """跨省检测器测试"""

    def test_sichuan_district_detection(self):
        """四川省区县检测"""
        checker = CrossProvinceChecker()

        # 龙马潭区应属四川，被解析到浙江
        has_error, desc = checker.check(
            "龙马潭区王氏商城",
            "浙江省",  # 错误省份
            "金华市",
            "婺城区"
        )

        assert has_error is True
        assert "跨省错误" in desc

    def test_correct_province_no_error(self):
        """正确省份无错误"""
        checker = CrossProvinceChecker()

        # 使用不含任何已映射区县关键词的地址
        has_error, desc = checker.check(
            "某省某市某街道",
            "四川省",  # 正确省份
            "成都市",
            "高新区"
        )

        assert has_error is False

    def test_city_mismatch_error(self):
        """市归属错误检测"""
        checker = CrossProvinceChecker()

        # 龙马潭区应属泸州市，但被解析到成都市
        has_error, desc = checker.check(
            "龙马潭区王氏商城",
            "四川省",  # 省份正确
            "成都市",  # 市错误
            "武侯区"
        )

        assert has_error is True
        assert "市归属错误" in desc

    def test_get_expected_province(self):
        """获取预期省份"""
        checker = CrossProvinceChecker()

        province = checker.get_expected_province("龙马潭区王氏商城")
        assert province == "四川省"

        province = checker.get_expected_province("朝阳区建国路")
        assert province == "北京市"

    def test_batch_check(self):
        """批量检查"""
        checker = CrossProvinceChecker()

        results = [
            # 使用不含已映射区县关键词的地址（不会触发检测）
            {"success": True, "original_address": "某省某市某街道", "province": "四川省", "city": "成都市", "district": "高新区"},
            {"success": True, "original_address": "龙马潭区", "province": "浙江省", "city": "金华市", "district": "婺城区"},
            {"success": False, "original_address": "无效地址", "error": "API failed"},
        ]

        valid, errors, stats = checker.check_batch(results)

        # 第一个结果不含已映射区县关键词，不会被检测为跨省错误
        # 第二个结果是跨省错误（龙马潭应属四川）
        # 第三个是失败结果
        assert len(valid) == 1
        assert len(errors) == 2  # 跨省错误 + 失败结果
        assert stats["cross_province_errors"] == 1


class TestConfidenceThreshold:
    """置信度阈值测试"""

    def test_threshold_60(self):
        """验证60分阈值"""
        validator = ConfidenceValidator()

        # 低置信度结果（缺少区划信息）
        low_result = {
            "province": None,
            "city": None,
            "district": None,
            "formatted_address": "某地...",
            "latitude": 10.0,  # 不在中国境内
            "longitude": 119.6
        }
        low_score = validator.validate("龙马潭区王氏商城", low_result)
        assert low_score.is_trustworthy is False  # < 60

        # 高置信度结果
        high_result = {
            "province": "四川省",
            "city": "泸州市",
            "district": "龙马潭区",
            "formatted_address": "四川省泸州市龙马潭区王氏商城...",
            "latitude": 28.9,
            "longitude": 105.4
        }
        high_score = validator.validate("龙马潭区王氏商城", high_result)
        assert high_score.is_trustworthy is True  # >= 60


class TestIntegration:
    """集成测试"""

    def test_normalizer_validator_flow(self):
        """预处理 -> 验证流程"""
        from geocode.preprocessing import AddressNormalizer
        validator = ConfidenceValidator()
        normalizer = AddressNormalizer()

        # 1. 预处理 - 只清洗符号
        address = "龙马潭区王氏商城(RS001)"
        normalized, meta = normalizer.normalize(address)

        # 清洗后的地址
        assert normalized == "龙马潭区王氏商城"
        # 无省份推断
        assert meta.get("province_hint") is None

        # 2. 模拟API返回结果（正确）
        correct_result = {
            "province": "四川省",
            "city": "泸州市",
            "district": "龙马潭区",
            "formatted_address": "四川省泸州市龙马潭区王氏商城",
            "latitude": 28.9137,
            "longitude": 105.4376
        }

        # 3. 置信度验证（不使用 province_hint）
        score = validator.validate(normalized, correct_result)

        assert score.is_trustworthy is True
        assert score.total >= 60
"""
跨省错误检测器

核心逻辑：
1. 维护省市区关系表
2. 检测返回省份与推断省份是否匹配
3. 检测市-区归属是否正确
"""

from typing import Dict, Optional, Tuple, List

# 四川省区县关键词映射（核心解决泸州问题）
SICHUAN_DISTRICTS = {
    "龙马潭": "泸州市",
    "江阳": "泸州市",
    "纳溪": "泸州市",
    "泸县": "泸州市",
    "合江": "泸州市",
    "叙永": "泸州市",
    "古蔺": "泸州市",
    # 成都市区县
    "锦江": "成都市",
    "青羊": "成都市",
    "金牛": "成都市",
    "武侯": "成都市",
    "成华": "成都市",
    "龙泉驿": "成都市",
    "新都": "成都市",
    "温江": "成都市",
    "双流": "成都市",
    "郫都": "成都市",
}

# 其他省份区县映射（扩展覆盖）
DISTRICT_PROVINCE_MAP = {
    # 北京
    "朝阳": "北京市", "海淀": "北京市", "东城": "北京市", "西城": "北京市",
    "丰台": "北京市", "石景山": "北京市", "通州": "北京市", "顺义": "北京市",
    # 上海
    "浦东": "上海市", "黄浦": "上海市", "徐汇": "上海市", "长宁": "上海市",
    "静安": "上海市", "普陀": "上海市", "虹口": "上海市", "杨浦": "上海市",
    # 广东
    "南山": "广东省", "福田": "广东省", "罗湖": "广东省", "宝安": "广东省",
    "龙岗": "广东省", "天河": "广东省", "越秀": "广东省", "海珠": "广东省",
    # 江苏
    "玄武": "江苏省", "秦淮": "江苏省", "建邺": "江苏省", "鼓楼": "江苏省",
}


class CrossProvinceChecker:
    """跨省错误检测器"""

    def __init__(self, admin_data: Dict = None):
        """
        初始化检测器

        Args:
            admin_data: 行政区划数据（可选）
        """
        self.admin_data = admin_data or {}
        # 合并内置区县映射
        self.district_province_map = {**DISTRICT_PROVINCE_MAP, **SICHUAN_DISTRICTS}

    def check(
        self,
        original_address: str,
        result_province: str,
        result_city: str,
        result_district: str
    ) -> Tuple[bool, str]:
        """
        检测跨省错误

        Args:
            original_address: 原始输入地址
            result_province: API返回的省份
            result_city: API返回的城市
            result_district: API返回的区县

        Returns:
            (has_error, error_description)
        """
        # 检查四川省区县（核心解决泸州问题）
        for district_keyword, expected_city in SICHUAN_DISTRICTS.items():
            if district_keyword in original_address:
                # 地址含四川区县关键词
                if result_province and "四川" not in result_province:
                    return True, f"跨省错误: {district_keyword}应属四川省，返回{result_province}"

                if result_city and expected_city.replace("市", "") not in result_city.replace("市", ""):
                    return True, f"市归属错误: {district_keyword}应属{expected_city}，返回{result_city}"

        # 检查其他省份区县
        for district_keyword, expected_province in self.district_province_map.items():
            if district_keyword in original_address:
                if result_province and expected_province.replace("省", "").replace("市", "") not in result_province.replace("省", "").replace("市", ""):
                    return True, f"跨省错误: {district_keyword}应属{expected_province}，返回{result_province}"

        return False, ""

    def get_expected_province(self, address: str) -> Optional[str]:
        """
        获取地址预期的省份

        Args:
            address: 地址字符串

        Returns:
            预期省份名称
        """
        for district_keyword, expected_city in SICHUAN_DISTRICTS.items():
            if district_keyword in address:
                return "四川省"

        for district_keyword, expected_province in self.district_province_map.items():
            if district_keyword in address:
                return expected_province

        return None

    def get_expected_city(self, address: str) -> Optional[str]:
        """
        获取地址预期的城市

        Args:
            address: 地址字符串

        Returns:
            预期城市名称
        """
        for district_keyword, expected_city in SICHUAN_DISTRICTS.items():
            if district_keyword in address:
                return expected_city

        return None

    def check_batch(self, results: List[Dict]) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        批量检查结果

        Args:
            results: 地理编码结果列表

        Returns:
            (valid_results, error_results, stats)
        """
        valid = []
        errors = []
        cross_province_count = 0
        city_error_count = 0

        for result in results:
            if not result.get("success"):
                errors.append(result)
                continue

            original = result.get("original_address", "")
            province = result.get("province", "")
            city = result.get("city", "")
            district = result.get("district", "")

            has_error, desc = self.check(original, province, city, district)

            if has_error:
                # 不修改原始 dict，创建带错误标记的浅拷贝
                flagged = dict(result)
                flagged["cross_check_error"] = desc
                flagged["success"] = False
                errors.append(flagged)

                if "跨省错误" in desc:
                    cross_province_count += 1
                elif "市归属错误" in desc:
                    city_error_count += 1
            else:
                valid.append(result)

        return valid, errors, {
            "total": len(results),
            "valid": len(valid),
            "errors": len(errors),
            "cross_province_errors": cross_province_count,
            "city_errors": city_error_count,
        }
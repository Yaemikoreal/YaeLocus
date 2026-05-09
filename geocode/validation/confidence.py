"""
置信度评分器

为地理编码结果评分，识别可疑结果

评分维度（总分100）：
1. 地址匹配度（0-30）：原始地址与formatted_address关键词重叠
2. 省份一致性（0-30）：推断省份与返回省份是否匹配
3. 区划完整性（0-20）：是否有省/市/区
4. 坐标合理性（0-20）：是否在中国境内

阈值：>=60分为可信结果
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 中国境内大致范围
CHINA_LAT_MIN = 18.0
CHINA_LAT_MAX = 54.0
CHINA_LON_MIN = 73.0
CHINA_LON_MAX = 135.0


@dataclass
class ConfidenceScore:
    """置信度评分结果"""
    total: float          # 总分 0-100
    address_match: float  # 地址匹配度 0-30
    province_match: float # 省份一致性 0-30
    completeness: float   # 区划完整性 0-20
    coord_valid: float    # 坐标合理性 0-20
    issues: List[str] = field(default_factory=list)
    is_trustworthy: bool = False  # total >= TRUST_THRESHOLD


class ConfidenceValidator:
    """置信度校验器"""

    TRUST_THRESHOLD = 60.0  # 信任阈值

    def validate(
        self,
        original_address: str,
        result: Dict,
        province_hint: Optional[str] = None
    ) -> ConfidenceScore:
        """
        校验地理编码结果置信度

        Args:
            original_address: 原始输入地址
            result: API 返回结果
            province_hint: 推断的省份（预处理阶段）

        Returns:
            ConfidenceScore 置信度评分
        """
        issues = []

        # 1. 地址匹配度（0-30分）
        address_match = self._score_address_match(
            original_address,
            result.get("formatted_address", ""),
            issues
        )

        # 2. 省份一致性（0-30分）- 核心检测跨省错误
        province_match = self._score_province_match(
            province_hint,
            result.get("province", ""),
            original_address,
            issues
        )

        # 3. 区划完整性（0-20分）
        completeness = self._score_completeness(result, issues)

        # 4. 坐标合理性（0-20分）
        coord_valid = self._score_coord_validity(result, issues)

        total = address_match + province_match + completeness + coord_valid
        is_trustworthy = total >= self.TRUST_THRESHOLD

        return ConfidenceScore(
            total=round(total, 1),
            address_match=round(address_match, 1),
            province_match=round(province_match, 1),
            completeness=round(completeness, 1),
            coord_valid=round(coord_valid, 1),
            issues=issues,
            is_trustworthy=is_trustworthy
        )

    def _score_address_match(
        self,
        original: str,
        formatted: str,
        issues: List[str]
    ) -> float:
        """地址匹配度评分"""
        if not formatted:
            issues.append("formatted_address缺失")
            return 0

        # 提取关键词（2个及以上连续中文字符）
        original_keywords = set(re.findall(r'[一-龥]{2,}', original))
        formatted_keywords = set(re.findall(r'[一-龥]{2,}', formatted))

        if not original_keywords:
            return 15  # 无法评估，给中等分

        # 关键词重叠率
        overlap = len(original_keywords & formatted_keywords)
        total = len(original_keywords)
        ratio = overlap / total if total > 0 else 0

        return ratio * 30

    def _score_province_match(
        self,
        hint: Optional[str],
        result_province: str,
        original: str,
        issues: List[str]
    ) -> float:
        """省份一致性评分 - 核心检测跨省错误"""
        if hint and result_province:
            # 检查推断省份与返回省份是否匹配
            if hint.replace("省", "") not in result_province.replace("省", "").replace("市", ""):
                # 跨省错误！严重问题
                issues.append(f"跨省错误: 推断{hint}, 返回{result_province}")
                return 0
            return 30

        # 无推断省份时，检查地址中的省份关键词
        province_in_address = self._extract_province_from_address(original)
        if province_in_address and result_province:
            if province_in_address.replace("省", "") not in result_province.replace("省", "").replace("市", ""):
                issues.append(f"省份不一致: 地址含{province_in_address}, 返回{result_province}")
                return 5
            return 25

        return 15  # 无法评估

    def _extract_province_from_address(self, address: str) -> Optional[str]:
        """从地址中提取省份关键词"""
        province_keywords = [
            "北京市", "上海市", "天津市", "重庆市",
            "广东省", "浙江省", "江苏省", "山东省", "河南省", "四川省",
            "湖北省", "湖南省", "安徽省", "福建省", "江西省", "河北省",
            "山西省", "辽宁省", "吉林省", "黑龙江省", "陕西省", "甘肃省",
            "青海省", "宁夏", "新疆", "内蒙古", "广西", "西藏", "云南", "贵州省", "海南省",
        ]
        # 简化匹配（去掉省/市后缀）
        for province in province_keywords:
            key = province.replace("省", "").replace("市", "")
            if key in address:
                return province

        return None

    def _score_completeness(self, result: Dict, issues: List[str]) -> float:
        """区划完整性评分"""
        score = 0

        if result.get("province"):
            score += 7
        else:
            issues.append("province缺失")

        if result.get("city"):
            score += 7
        else:
            issues.append("city缺失")

        if result.get("district"):
            score += 6
        else:
            issues.append("district缺失")

        return score

    def _score_coord_validity(self, result: Dict, issues: List[str]) -> float:
        """坐标合理性评分"""
        lat = result.get("latitude")
        lon = result.get("longitude")

        if lat is None or lon is None:
            issues.append("坐标缺失")
            return 0

        try:
            lat_f = float(lat)
            lon_f = float(lon)

            # 中国境内范围检查
            if not (CHINA_LAT_MIN <= lat_f <= CHINA_LAT_MAX and
                    CHINA_LON_MIN <= lon_f <= CHINA_LON_MAX):
                issues.append(f"坐标超出中国境内: ({lat_f}, {lon_f})")
                return 5

            return 20
        except (TypeError, ValueError):
            issues.append("坐标格式错误")
            return 0


def is_in_china(lat: float, lon: float) -> bool:
    """检查坐标是否在中国境内"""
    return (CHINA_LAT_MIN <= lat <= CHINA_LAT_MAX and
            CHINA_LON_MIN <= lon <= CHINA_LON_MAX)
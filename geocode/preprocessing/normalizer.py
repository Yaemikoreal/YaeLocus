"""
地址标准化器

功能：
1. 自动补全缺失省份
2. 去除冗余词和统一分隔符
3. 基于行政区划数据推断省份

核心解决跨省错误问题：
- 龙马潭区 → 四川省
- 江阳区 → 四川省
"""

import json
import re
from pathlib import Path
from typing import Tuple, Dict, Optional


class AddressNormalizer:
    """地址标准化处理器"""

    # 冗余词模式
    REDUNDANT_PATTERN = re.compile(r'(省|市|区|县|镇|街道){2,}')

    # 地址分隔符标准化
    SEPARATOR_PATTERN = re.compile(r'[,\s;；，]+')

    def __init__(self, admin_data_path: Optional[str] = None):
        """
        初始化地址标准化器

        Args:
            admin_data_path: 行政区划数据文件路径，None 使用默认路径
        """
        self.admin_data = self._load_admin_divisions(admin_data_path)
        self.district_map = self._build_district_map()

    def _load_admin_divisions(self, path: Optional[str] = None) -> Dict:
        """加载行政区划数据"""
        if path is None:
            data_file = Path(__file__).parent.parent / "data" / "admin_divisions.json"
        else:
            data_file = Path(path)

        if not data_file.exists():
            # 数据文件不存在，返回空字典（使用内置关键词）
            return {}

        try:
            return json.loads(data_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _build_district_map(self) -> Dict[str, str]:
        """
        构建区县关键词到省份的映射

        Returns:
            {区县关键词: 省份名称}
        """
        district_map = {}

        # 从行政区划数据构建
        if self.admin_data:
            for province_name, province_data in self.admin_data.items():
                if isinstance(province_data, dict) and "cities" in province_data:
                    for city_name, city_data in province_data["cities"].items():
                        if isinstance(city_data, dict) and "districts" in city_data:
                            for district_name in city_data["districts"]:
                                # 提取区县关键词（去掉"区"、"县"后缀）
                                key = district_name.replace("区", "").replace("县", "")
                                district_map[key] = province_name

        # 内置关键词（确保核心区县覆盖）
        builtin_map = {
            # 四川省泸州市
            "龙马潭": "四川省",
            "江阳": "四川省",
            "纳溪": "四川省",
            "泸县": "四川省",
            "合江": "四川省",
            "叙永": "四川省",
            "古蔺": "四川省",
            # 四川省成都市
            "锦江": "四川省",
            "青羊": "四川省",
            "金牛": "四川省",
            "武侯": "四川省",
            "成华": "四川省",
            "龙泉驿": "四川省",
            "新都": "四川省",
            "温江": "四川省",
            "双流": "四川省",
            "郫都": "四川省",
            # 其他常见区县（覆盖主要城市）
            "朝阳": "北京市",
            "海淀": "北京市",
            "东城": "北京市",
            "西城": "北京市",
            "丰台": "北京市",
            "浦东": "上海市",
            "黄浦": "上海市",
            "徐汇": "上海市",
            "长宁": "上海市",
            "静安": "上海市",
            "南山": "广东省",
            "福田": "广东省",
            "罗湖": "广东省",
            "宝安": "广东省",
            "龙岗": "广东省",
            "天河": "广东省",
            "越秀": "广东省",
            "海珠": "广东省",
            "荔湾": "广东省",
            "玄武": "江苏省",
            "秦淮": "江苏省",
            "建邺": "江苏省",
            "鼓楼": "江苏省",
        }

        # 合并内置和加载的映射
        for key, province in builtin_map.items():
            if key not in district_map:
                district_map[key] = province

        return district_map

    def normalize(self, address: str) -> Tuple[str, Dict]:
        """
        标准化地址

        Args:
            address: 原始地址

        Returns:
            (normalized_address, metadata)
            metadata 包含：原始地址、推断省份、置信度
        """
        if not address or not address.strip():
            return "", {"valid": False, "reason": "empty"}

        original = address.strip()

        # 1. 基础清洗
        cleaned = self._clean_basic(original)

        # 2. 去除冗余词
        cleaned = self.REDUNDANT_PATTERN.sub(lambda m: m.group(1), cleaned)

        # 3. 省份推断（关键：解决跨省错误）
        province_hint = self._guess_province(cleaned)

        # 4. 构建标准化地址
        normalized = self._build_normalized(cleaned, province_hint)

        return normalized, {
            "original": original,
            "province_hint": province_hint,
            "valid": True
        }

    def _clean_basic(self, address: str) -> str:
        """基础清洗：去除特殊字符"""
        # 统一分隔符为空格
        address = self.SEPARATOR_PATTERN.sub(' ', address)
        # 去除前后空格
        return address.strip()

    def _guess_province(self, address: str) -> Optional[str]:
        """
        推断省份（基于关键词匹配）

        Args:
            address: 地址字符串

        Returns:
            推断的省份名称，无法推断返回 None
        """
        # 检查地址中是否已有省份关键词
        province_keywords = [
            "北京", "上海", "天津", "重庆",
            "广东", "浙江", "江苏", "山东", "河南", "四川", "湖北", "湖南",
            "安徽", "福建", "江西", "河北", "山西", "辽宁", "吉林", "黑龙江",
            "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "广西", "西藏",
            "云南", "贵州", "海南", "香港", "澳门",
        ]
        for kw in province_keywords:
            if kw in address:
                return None  # 已有省份，无需推断

        # 检查区县关键词
        for district_keyword, province in self.district_map.items():
            if district_keyword in address:
                return province

        return None

    def _build_normalized(self, address: str, province: Optional[str]) -> str:
        """
        构建标准化地址

        Args:
            address: 清洗后的地址
            province: 推断的省份

        Returns:
            标准化地址
        """
        if province and province not in address:
            # 补全省份
            return f"{province}{address}"
        return address

    def get_expected_province(self, address: str) -> Optional[str]:
        """
        获取地址预期的省份

        Args:
            address: 地址字符串

        Returns:
            预期省份名称
        """
        _, meta = self.normalize(address)
        return meta.get("province_hint")
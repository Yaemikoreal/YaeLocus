"""
地址拆分器 - 处理特殊格式的地址数据

支持以下格式：
- "公司名|地址" 格式（管道符分隔）
- "公司名｜地址" 格式（中文竖线分隔）
- 地址末尾编号清理：(RSxxxx)、【xxx】等

核心解决眉山数据格式问题：
- 某某分公司|眉山市仁寿县xxx小区xxx号(RS01656)
"""

import re
from typing import Dict


class AddressSplitter:
    """处理 '公司名|地址' 格式的地址拆分"""

    # 分隔符模式：管道符、中文竖线等
    SEPARATOR_PATTERN = re.compile(r'[|｜]')

    # 编号清理模式：(xxx) 或 【xxx】 或 [xxx]
    # 匹配末尾的编号标记，如 (RS01656)、【编号】等
    CODE_PATTERN = re.compile(r'\s*[（\(【\[][^）\)】\]]*[）\)】\]]\s*$')

    def split(self, address: str) -> Dict:
        """
        拆分地址，提取实际地址部分

        Args:
            address: 原始地址（可能包含公司名前缀和末尾编号）

        Returns:
            {
                "original": 原始地址,
                "company": 公司名（如有）,
                "address": 实际地址（用于地理编码）,
                "has_separator": 是否包含分隔符
            }
        """
        if not address or not address.strip():
            return {
                "original": address,
                "company": "",
                "address": "",
                "has_separator": False
            }

        original = address.strip()

        # 1. 检查分隔符，提取地址部分
        match = self.SEPARATOR_PATTERN.search(original)

        if match:
            # 有分隔符：提取后半部分作为地址
            parts = self.SEPARATOR_PATTERN.split(original, maxsplit=1)
            company = parts[0].strip() if len(parts) > 1 else ""
            address_part = parts[1].strip() if len(parts) > 1 else original
        else:
            # 无分隔符：整个字符串作为地址
            company = ""
            address_part = original

        # 2. 清理末尾编号标记
        cleaned_address = self.CODE_PATTERN.sub('', address_part).strip()

        return {
            "original": original,
            "company": company,
            "address": cleaned_address,
            "has_separator": bool(match)
        }

    def extract_address(self, address: str) -> str:
        """
        提取实际地址部分（简化接口）

        Args:
            address: 原始地址

        Returns:
            清理后的实际地址，可直接用于地理编码
        """
        result = self.split(address)
        return result["address"]

    def has_special_format(self, address: str) -> bool:
        """
        检查地址是否包含特殊格式（分隔符）

        Args:
            address: 地址字符串

        Returns:
            是否包含分隔符
        """
        if not address:
            return False
        return bool(self.SEPARATOR_PATTERN.search(address.strip()))
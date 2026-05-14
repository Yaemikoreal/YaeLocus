"""
地址清洗器

功能：
1. 清洗非地址符号（分隔符统一、编号清理）
2. 不修改地址内容（不添加省份、不推断）
"""

import re
from typing import Tuple, Dict, Optional


class AddressNormalizer:
    """地址清洗处理器"""

    # 地址分隔符标准化
    SEPARATOR_PATTERN = re.compile(r'[,\s;；，]+')

    # 编号清理模式：(xxx) 或 【xxx】
    CODE_PATTERN = re.compile(r'\s*[（\(【\[][^）\)】\]]*[）\)】\]]\s*$')

    def normalize(self, address: str) -> Tuple[str, Dict]:
        """
        地址清洗（只清洗，不修改地址内容）

        Args:
            address: 原始地址

        Returns:
            (cleaned_address, metadata)
            metadata 仅包含：原始地址、是否有效
        """
        if not address or not address.strip():
            return "", {"valid": False, "reason": "empty"}

        original = address.strip()

        # 清洗非地址符号
        cleaned = self._clean_basic(original)

        return cleaned, {
            "original": original,
            "valid": True
        }

    def _clean_basic(self, address: str) -> str:
        """清洗非地址符号"""
        # 1. 统一分隔符为空格
        address = self.SEPARATOR_PATTERN.sub(' ', address)

        # 2. 去除末尾编号标记 (RSxxx)、【编号】等
        address = self.CODE_PATTERN.sub('', address)

        # 3. 去除前后空格
        return address.strip()

    def get_expected_province(self, address: str) -> Optional[str]:
        """
        已弃用：不再推断省份

        Returns:
            None
        """
        return None
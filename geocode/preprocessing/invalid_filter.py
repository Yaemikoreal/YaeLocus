"""
无效地址过滤器

识别并过滤以下无效数据：
- 数值型数据（0, 0.0, 123）
- 空值和空白
- 过短地址（< 2字符）
- 纯数字地址
"""

import re
from typing import Tuple, List, Dict

# 无效地址模式
INVALID_PATTERNS = [
    re.compile(r'^0+$'),           # 纯0
    re.compile(r'^\d+$'),          # 纯数字
    re.compile(r'^\d+\.\d+$'),     # 浮点数
    re.compile(r'^[\-]+$'),        # 纯分隔符
]


class InvalidAddressFilter:
    """无效地址过滤器"""

    MIN_ADDRESS_LENGTH = 2  # 最小有效长度

    def is_valid(self, address) -> Tuple[bool, str]:
        """
        检查地址有效性

        Args:
            address: 地址（可以是字符串或其他类型）

        Returns:
            (is_valid, reason) - 是否有效及原因
        """
        if address is None:
            return False, "null_value"

        # 转换为字符串
        address_str = str(address).strip()

        # 空值检查
        if not address_str:
            return False, "empty"

        # 长度检查
        if len(address_str) < self.MIN_ADDRESS_LENGTH:
            return False, "too_short"

        # 无效模式检查
        for pattern in INVALID_PATTERNS:
            if pattern.match(address_str):
                return False, "invalid_pattern"

        # 必须包含至少一个中文字符或有效字符
        if not re.search(r'[一-龥a-zA-Z]', address_str):
            return False, "no_valid_chars"

        return True, "valid"

    def filter_addresses(self, addresses: List) -> Tuple[List[str], Dict]:
        """
        批量过滤无效地址

        Args:
            addresses: 地址列表

        Returns:
            (valid_addresses, stats) - 有效地址列表和统计信息
        """
        valid = []
        invalid_count = 0
        invalid_reasons = {}
        invalid_samples = []  # 保存无效样本供输出

        for addr in addresses:
            is_valid, reason = self.is_valid(addr)
            if is_valid:
                valid.append(str(addr).strip())
            else:
                invalid_count += 1
                invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1
                invalid_samples.append((addr, reason))

        return valid, {
            "total": len(addresses),
            "valid": len(valid),
            "invalid": invalid_count,
            "reasons": invalid_reasons,
            "samples": invalid_samples[:10]  # 只保留前10个样本
        }
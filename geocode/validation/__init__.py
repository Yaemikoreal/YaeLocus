"""
结果验证模块

提供置信度评分和跨省错误检测功能
"""

from .confidence import ConfidenceValidator, ConfidenceScore
from .cross_check import CrossProvinceChecker

__all__ = ["ConfidenceValidator", "ConfidenceScore", "CrossProvinceChecker"]
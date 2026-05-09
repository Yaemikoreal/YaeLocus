"""
行政区划数据模块

包含全国省市区数据（国家统计局）
"""

import json
from pathlib import Path

# 数据文件路径
DATA_FILE = Path(__file__).parent / "admin_divisions.json"


def load_admin_divisions() -> dict:
    """加载行政区划数据"""
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


__all__ = ["load_admin_divisions", "DATA_FILE"]
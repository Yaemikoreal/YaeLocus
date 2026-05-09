"""
CLI 共享工具函数和常量

从 cli.py 提取，供各命令模块复用
"""

import json
import time
import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..config import PROJECT_DIR

# Windows 兼容: ASCII 符号替代 Unicode
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

# Rich Console 实例（全局共享）
console = Console(force_terminal=True)

# 中国主要城市坐标表（AI 模式后备，无需 API 密钥）
CITY_COORDS = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "天津": (39.3434, 117.3616), "重庆": (29.4316, 106.9123),
    "杭州": (30.2741, 120.1551), "南京": (32.0603, 118.7969),
    "武汉": (30.5928, 114.3055), "成都": (30.5728, 104.0668),
    "西安": (34.3416, 108.9398), "郑州": (34.7466, 113.6253),
    "沈阳": (41.8057, 123.4315), "青岛": (36.0671, 120.3826),
    "宁波": (29.8683, 121.5440), "东莞": (23.0208, 113.7518),
    "佛山": (23.0219, 113.1214), "苏州": (31.2990, 120.5853),
    "长沙": (28.2282, 112.9388), "合肥": (31.8206, 117.2272),
    "大连": (38.9140, 121.6147), "福州": (26.0745, 119.2965),
    "厦门": (24.4798, 118.0894), "哈尔滨": (45.8038, 126.5350),
    "昆明": (25.0389, 102.7183), "贵阳": (26.6470, 106.6302),
    "南宁": (22.8170, 108.3665), "兰州": (36.0611, 103.8343),
    "拉萨": (29.6499, 91.1722), "乌鲁木齐": (43.8256, 87.6168),
    "海口": (20.0440, 110.3692), "三亚": (18.2528, 109.5120),
    "呼和浩特": (40.8422, 111.7499), "银川": (38.4863, 106.2325),
    "西宁": (36.6173, 101.7782), "香港": (22.3193, 114.1694),
    "澳门": (22.1987, 113.5439), "台北": (25.0330, 121.5654),
    "雄安": (38.9107, 115.9693),
}


def resolve_path(file_path: str) -> Path:
    """解析路径，相对路径基于项目根目录"""
    path = Path(file_path)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def _write_progress(progress_file: Path, data: dict) -> None:
    """原子写入进度文件"""
    try:
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = progress_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(progress_file)
    except Exception:
        pass  # 进度文件写入失败不应中断主流程


def _print_error_json(error, command: str = "unknown") -> None:
    """输出 JSON 格式的错误信息"""
    output = {
        "error": {
            "code": error.code,
            "message": error.message,
            "suggestion": error.suggestion
        },
        "command": command,
        "status": "error"
    }
    print(json.dumps(output, ensure_ascii=False))


def _resolve_address_coords(address: str) -> Optional[dict]:
    """解析地址为坐标，优先使用内置城市表（零成本），失败则回退到地图 API"""
    for city_name, (lat, lon) in CITY_COORDS.items():
        if city_name in address:
            return {"lat": lat, "lon": lon, "address": address}
    try:
        from ..geocoder import Geocoder
        from ..cache import CacheManager as CacheMgr
        mgr = CacheMgr()
        geo = Geocoder(mgr)
        result = geo.geocode(address)
        geo.close()
        if result.get("success"):
            return {"lat": result["latitude"], "lon": result["longitude"], "address": address}
    except Exception:
        pass
    return None


def print_version(version_str: str):
    """返回 Rich Panel 展示版本信息"""
    from rich.panel import Panel
    console.print(Panel.fit(
        f"[bold blue]YaeLocus[/bold blue] [dim]v{version_str}[/dim]\n"
        f"[dim]地址转经纬度 + 路线规划 + AI 分析[/dim]",
        border_style="blue"
    ))


def setup_windows_encoding():
    """Windows 兼容: 设置 UTF-8 环境"""
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

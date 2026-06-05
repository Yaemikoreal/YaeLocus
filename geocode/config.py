"""
配置管理模块

从 .env 文件加载配置，支持环境变量覆盖
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv

# 获取项目根目录
PROJECT_DIR = Path(__file__).parent.parent.resolve()

# 加载 .env 文件
ENV_FILE = PROJECT_DIR / ".env"
load_dotenv(ENV_FILE)


# ── 输出目录结构 ─────────────────────────────────────────────────

class OutputPaths:
    """集中化输出路径管理

    所有模块通过此类引用输出路径，便于统一重构。

    结构:
        output/
          csv/        — 结果 CSV/XLSX/JSON (geocode batch, ai analyze)
          map/        — 地图 HTML (geocode batch, map create, ai route)
          database/   — SQLite 缓存 DB (geocache.db)
          log/        — API 调用日志 (api调用日志.csv)
          export/     — 导出文件 (cache_export.json, session_history.txt)
          progress/   — 临时进度 (.geocode_progress.json)
    """
    ROOT      = PROJECT_DIR / "output"
    CSV       = ROOT / "csv"
    MAP       = ROOT / "map"
    DATABASE  = ROOT / "database"
    LOG       = ROOT / "log"
    EXPORT    = ROOT / "export"
    PROGRESS  = ROOT / "progress"

    _DIRS = (CSV, MAP, DATABASE, LOG, EXPORT, PROGRESS)

    @classmethod
    def ensure_dirs(cls) -> None:
        """确保所有输出子目录存在"""
        for d in cls._DIRS:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def migrate_legacy(cls, max_retries: int = 3) -> None:
        """一次性迁移: 将 output/ 根目录下的旧文件移动到对应子目录

        幂等操作 — 目标已存在则跳过并删除源文件。
        数据库 WAL/SHM 伴随文件自动清理。
        """
        MIGRATIONS = [
            ("geocache.db",          cls.DATABASE),
            ("frontend_cache.db",    cls.DATABASE),
            ("perf_cache.db",        cls.DATABASE),
            ("test_cache.db",        cls.DATABASE),
            ("api调用日志.csv",      cls.LOG),
            ("cache_export.json",    cls.EXPORT),
            ("session_history.txt",  cls.EXPORT),
            (".geocode_progress.json", cls.PROGRESS),
        ]
        for old_rel, target_dir in MIGRATIONS:
            old = cls.ROOT / old_rel
            if not old.exists():
                continue
            new = target_dir / old.name
            if not new.exists():
                for attempt in range(max_retries):
                    try:
                        old.replace(new)
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(0.1)
            else:
                old.unlink(missing_ok=True)

        # 数据库 WAL/SHM 伴随文件 — 仅当主 DB 不存在于根目录时才清理
        for suffix in ("-wal", "-shm"):
            for db_name in ("geocache", "frontend_cache", "perf_cache", "test_cache"):
                f = cls.ROOT / f"{db_name}.db{suffix}"
                f.unlink(missing_ok=True)

        # CSV 结果文件 (排除已迁移的 api调用日志)
        for f in cls.ROOT.glob("*.csv"):
            if f.name != "api调用日志.csv":
                dst = cls.CSV / f.name
                if not dst.exists():
                    try:
                        f.replace(dst)
                    except PermissionError:
                        pass

        # XLSX 结果文件
        for ext in ("*.xlsx", "*.xls", "*.json", "*.geojson"):
            for f in cls.ROOT.glob(ext):
                dst = cls.CSV / f.name
                if not dst.exists():
                    try:
                        f.replace(dst)
                    except PermissionError:
                        pass

        # HTML 地图文件
        for f in cls.ROOT.glob("*.html"):
            dst = cls.MAP / f.name
            if not dst.exists():
                try:
                    f.replace(dst)
                except PermissionError:
                    pass

    @classmethod
    def for_flag(cls, flag: str) -> "Path":
        """根据命令行标志返回合适的搜索目录"""
        if flag in ("-i", "--input"):
            return PROJECT_DIR / "data"
        if flag in ("-o", "--output"):
            return cls.CSV
        if flag in ("-m", "--map"):
            return cls.MAP
        if flag in ("--cache",):
            return cls.DATABASE
        return cls.CSV


# 模块加载时初始化目录并迁移旧文件
_initialized = False
def _init_output_paths():
    global _initialized
    if not _initialized:
        OutputPaths.ensure_dirs()
        OutputPaths.migrate_legacy()
        _initialized = True
_init_output_paths()


@dataclass
class APIConfigItem:
    """单个API配置"""
    name: str
    key: str
    url: str
    daily_limit: int
    coordinate_system: str

    @property
    def is_available(self) -> bool:
        return bool(self.key)


class Config:
    """全局配置类"""

    # API密钥
    AMAP_KEY: str = os.getenv("AMAP_KEY", "")
    BAIDU_AK: str = os.getenv("BAIDU_AK", "")
    TIANDITU_TK: str = os.getenv("TIANDITU_TK", "")

    # API端点
    AMAP_URL: str = "https://restapi.amap.com/v3/geocode/geo"
    AMAP_REGEO_URL: str = "https://restapi.amap.com/v3/geocode/regeo"  # 逆地理编码
    BAIDU_URL: str = "https://api.map.baidu.com/geocoding/v3/"
    BAIDU_REGEO_URL: str = "https://api.map.baidu.com/reverse_geocoding/v3/"  # 逆地理编码
    TIANDITU_URL: str = "http://api.tianditu.gov.cn/geocoder"
    TIANDITU_REGEO_URL: str = "http://api.tianditu.gov.cn/geodecoder"  # 逆地理编码

    # 请求配置
    REQUEST_DELAY: float = 0.1  # 请求间隔(秒)
    REQUEST_TIMEOUT: int = 10  # 超时时间(秒)
    MAX_RETRIES: int = 3  # 最大重试次数（网络错误时）

    # API优先级顺序
    API_PRIORITY: List[str] = ["amap", "tianditu", "baidu"]

    # API配额(次/日)
    API_DAILY_LIMITS = {
        "amap": 5000,
        "tianditu": 10000,
        "baidu": 6000
    }

    # AI 配额(次/日) — 无硬性限制，仅用于 UI 展示
    AI_DAILY_LIMITS = {
        "deepseek": 1000,
        "qwen": 1000,
        "glm": 1000,
        "moonshot": 1000,
    }

    # 坐标系
    COORDINATE_SYSTEMS = {
        "amap": "GCJ-02",
        "tianditu": "CGCS2000",
        "baidu": "BD-09"
    }

    @classmethod
    def get_api_config(cls, api_name: str) -> Optional[APIConfigItem]:
        """获取指定API的配置"""
        configs = {
            "amap": APIConfigItem(
                name="amap",
                key=cls.AMAP_KEY,
                url=cls.AMAP_URL,
                daily_limit=cls.API_DAILY_LIMITS["amap"],
                coordinate_system=cls.COORDINATE_SYSTEMS["amap"]
            ),
            "tianditu": APIConfigItem(
                name="tianditu",
                key=cls.TIANDITU_TK,
                url=cls.TIANDITU_URL,
                daily_limit=cls.API_DAILY_LIMITS["tianditu"],
                coordinate_system=cls.COORDINATE_SYSTEMS["tianditu"]
            ),
            "baidu": APIConfigItem(
                name="baidu",
                key=cls.BAIDU_AK,
                url=cls.BAIDU_URL,
                daily_limit=cls.API_DAILY_LIMITS["baidu"],
                coordinate_system=cls.COORDINATE_SYSTEMS["baidu"]
            )
        }
        return configs.get(api_name)

    @classmethod
    def get_available_apis(cls) -> List[str]:
        """获取可用的API列表"""
        available = []
        for api_name in cls.API_PRIORITY:
            config = cls.get_api_config(api_name)
            if config and config.is_available:
                available.append(api_name)
        return available

    # AI 集成配置
    AI_ENABLED: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "deepseek")
    AI_MODEL: str = os.getenv("AI_MODEL", "")

    # AI 供应商 API Keys
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    MOONSHOT_API_KEY: str = os.getenv("MOONSHOT_API_KEY", "")

    @classmethod
    def get_ai_client(cls) -> Optional[Any]:
        """获取 AI 客户端（如果 AI 已启用且配置有效）"""
        if not cls.AI_ENABLED:
            return None
        try:
            from geocode.ai import AIClient
            from geocode.ai.providers import get_provider

            provider = get_provider(cls.AI_PROVIDER)
            if not provider:
                import logging
                logging.getLogger(__name__).warning("AI 供应商 '%s' 未找到配置", cls.AI_PROVIDER)
                return None
            api_key = os.getenv(provider.api_key_env, "")
            if not api_key:
                import logging
                logging.getLogger(__name__).warning("AI 供应商 '%s' 的 API Key 未配置 (%s)", provider.display_name, provider.api_key_env)
                return None

            model = cls.AI_MODEL or None
            if model and provider.available_models:
                if model not in provider.available_models:
                    import logging
                    logging.getLogger(__name__).warning("模型 '%s' 不在 %s 的已知列表中，回退到默认 '%s'", model, provider.display_name, provider.default_model)
                    model = None

            return AIClient(
                provider=cls.AI_PROVIDER,
                api_key=api_key,
                model=model,
            )
        except ValueError as e:
            import logging
            logging.getLogger(__name__).warning("AI 客户端配置错误: %s", e)
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("AI 客户端创建失败: %s", e)
            return None

    @classmethod
    def get_available_ai_providers(cls) -> List[str]:
        """获取已配置 API Key 的 AI 供应商列表"""
        from geocode.ai.providers import get_available_providers
        return [p.name for p in get_available_providers()]

    # 路线规划模式
    ROUTING_MODE: str = os.getenv("ROUTING_MODE", "ai")
    ROUTING_AUTO_FALLBACK: bool = os.getenv("ROUTING_AUTO_FALLBACK", "false").lower() == "true"

    # API 最大并发连接数（0 = 不限制）
    API_MAX_CONCURRENT = {
        "amap": 0,
        "tianditu": 0,
        "baidu": 2,
    }

    # 并发地理编码配置
    PARALLEL_APIS: bool = os.getenv("PARALLEL_APIS", "true").lower() == "true"
    CROSS_VALIDATE_THRESHOLD: float = float(os.getenv("CROSS_VALIDATE_THRESHOLD", "70.0"))
    CROSS_VALIDATE_MAX_COORD_DELTA: float = float(os.getenv("CROSS_VALIDATE_MAX_COORD_DELTA", "1.0"))  # km
    GEOCODE_PARALLEL_TIMEOUT: int = int(os.getenv("GEOCODE_PARALLEL_TIMEOUT", "8"))

    @classmethod
    def get_routing_default_mode(cls) -> str:
        """获取路线规划默认模式: ai（零外部成本）| api（付费）"""
        mode = cls.ROUTING_MODE.lower()
        return mode if mode in ("ai", "api") else "ai"

    @classmethod
    def get_routing_provider(cls) -> str:
        """获取路线规划默认供应商"""
        if cls.AMAP_KEY:
            return "amap"
        if cls.BAIDU_AK:
            return "baidu"
        return "amap"

    @classmethod
    def reload(cls) -> None:
        """重新加载 .env 配置到类属性"""
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)
        cls.AMAP_KEY = os.getenv("AMAP_KEY", "")
        cls.BAIDU_AK = os.getenv("BAIDU_AK", "")
        cls.TIANDITU_TK = os.getenv("TIANDITU_TK", "")
        cls.AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
        cls.AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")
        cls.AI_MODEL = os.getenv("AI_MODEL", "")
        cls.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
        cls.QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
        cls.GLM_API_KEY = os.getenv("GLM_API_KEY", "")
        cls.MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
        cls.ROUTING_MODE = os.getenv("ROUTING_MODE", "ai")
        cls.ROUTING_AUTO_FALLBACK = os.getenv("ROUTING_AUTO_FALLBACK", "false").lower() == "true"

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否有效"""
        return bool(cls.AMAP_KEY or cls.BAIDU_AK or cls.TIANDITU_TK)

    @classmethod
    def get_project_dir(cls) -> Path:
        """获取项目根目录"""
        return PROJECT_DIR


# 导出常用配置
__all__ = [
    "Config",
    "OutputPaths",
    "PROJECT_DIR",
]

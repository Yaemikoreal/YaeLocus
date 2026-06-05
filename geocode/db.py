"""
统一数据库管理器

特性:
- 单例模式，全局唯一实例
- 统一 PRAGMA 配置（WAL / NORMAL / busy_timeout）
- Schema 版本管理与自动迁移
- 上下文管理器连接（自动 commit/rollback/close）
- Settings CRUD（含掩码读取）
- API Usage 配额追踪
- Config History 配置变更审计
- Cache Stats Daily 统计持久化
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config, OutputPaths

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 2

PRAGMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=30000;
PRAGMA foreign_keys=ON;
"""

CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL,
    description TEXT
);
"""

CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

CREATE_API_USAGE = """
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL,
    call_date TEXT NOT NULL,
    call_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_called REAL,
    UNIQUE(api_name, call_date)
);
CREATE INDEX IF NOT EXISTS idx_api_date ON api_usage(api_name, call_date);
"""

CREATE_CONFIG_HISTORY = """
CREATE TABLE IF NOT EXISTS config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at REAL NOT NULL,
    changed_via TEXT DEFAULT 'web_gui'
);
CREATE INDEX IF NOT EXISTS idx_config_key ON config_history(key);
CREATE INDEX IF NOT EXISTS idx_config_time ON config_history(changed_at);
"""

CREATE_CACHE_STATS_DAILY = """
CREATE TABLE IF NOT EXISTS cache_stats_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,
    hits INTEGER DEFAULT 0,
    misses INTEGER DEFAULT 0,
    hit_rate REAL DEFAULT 0,
    total_entries INTEGER DEFAULT 0,
    evictions INTEGER DEFAULT 0,
    UNIQUE(stat_date)
);
CREATE INDEX IF NOT EXISTS idx_stats_date ON cache_stats_daily(stat_date);
"""

CACHE_NEW_COLUMNS = [
    ("formatted_address", "TEXT"),
    ("province", "TEXT"),
    ("city", "TEXT"),
    ("district", "TEXT"),
    ("latitude", "REAL"),
    ("longitude", "REAL"),
    ("confidence", "REAL"),
    ("access_count", "INTEGER DEFAULT 1"),
    ("last_accessed", "REAL"),
]

CACHE_NEW_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cache_source ON cache(source)",
    "CREATE INDEX IF NOT EXISTS idx_cache_province_city ON cache(province, city)",
    "CREATE INDEX IF NOT EXISTS idx_cache_last_accessed ON cache(last_accessed)",
]

TASK_NEW_COLUMNS = [
    ("workers", "INTEGER DEFAULT 1"),
    ("duration_sec", "REAL"),
]

TASK_NEW_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_task_status ON task_history(status)",
    "CREATE INDEX IF NOT EXISTS idx_task_started ON task_history(started_at)",
]


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _instances_by_path: Dict[str, "DatabaseManager"] = {}
    _lock = threading.Lock()

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(OutputPaths.DATABASE / "geocache.db")
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @classmethod
    def get_instance(cls, db_path: str = None) -> "DatabaseManager":
        if db_path is None:
            if cls._instance is None:
                with cls._lock:
                    if cls._instance is None:
                        cls._instance = cls()
            return cls._instance
        resolved = str(Path(db_path).resolve())
        if resolved not in cls._instances_by_path:
            with cls._lock:
                if resolved not in cls._instances_by_path:
                    inst = cls(db_path)
                    cls._instances_by_path[resolved] = inst
                    if cls._instance is None:
                        cls._instance = inst
        return cls._instances_by_path[resolved]

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
        cls._instances_by_path = {}

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self):
        conn = self._new_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── Schema 迁移 ──────────────────────────────────────────────

    def _get_current_version(self, conn: sqlite3.Connection) -> int:
        try:
            row = conn.execute(
                "SELECT MAX(version) FROM _schema_version"
            ).fetchone()
            return row[0] if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def _ensure_schema(self) -> None:
        try:
            with self.connection() as conn:
                version = self._get_current_version(conn)
                if version < CURRENT_SCHEMA_VERSION:
                    self._migrate(conn, version)
        except sqlite3.DatabaseError:
            logger.warning("数据库损坏，尝试恢复: %s", self._path, exc_info=True)
            self._recover_database()

    def _recover_database(self) -> None:
        import shutil
        backup_path = Path(str(self._path) + ".corrupted." + str(int(time.time())))
        for suffix in ['', '-wal', '-shm']:
            src = Path(str(self._path) + suffix)
            if src.exists():
                try:
                    dst = Path(str(backup_path) + suffix)
                    shutil.copy2(str(src), str(dst))
                except Exception:
                    pass
        for suffix in ['', '-wal', '-shm']:
            p = Path(str(self._path) + suffix)
            if p.exists():
                for _ in range(3):
                    try:
                        p.unlink()
                        break
                    except PermissionError:
                        time.sleep(0.1)
        try:
            with self.connection() as conn:
                self._migrate(conn, 0)
        except Exception:
            logger.error("数据库恢复后重建schema失败", exc_info=True)

    def _migrate(self, conn: sqlite3.Connection, from_version: int) -> None:
        if from_version < 1:
            self._migrate_v0_to_v1(conn)
        if from_version < 2:
            self._migrate_v1_to_v2(conn)
        conn.execute(
            "INSERT OR REPLACE INTO _schema_version (version, applied_at, description) VALUES (?,?,?)",
            (CURRENT_SCHEMA_VERSION, time.time(), f"schema v{CURRENT_SCHEMA_VERSION}"),
        )

    def _migrate_v0_to_v1(self, conn: sqlite3.Connection) -> None:
        conn.execute(CREATE_SCHEMA_VERSION)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                address TEXT,
                data TEXT NOT NULL,
                created_at REAL,
                expires_at REAL,
                source TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
        conn.execute(CREATE_SETTINGS)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                input_file TEXT NOT NULL,
                column TEXT NOT NULL,
                city TEXT,
                total INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                csv_output TEXT,
                map_output TEXT,
                started_at REAL NOT NULL,
                completed_at REAL,
                error TEXT
            );
        """)

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        conn.execute(CREATE_SCHEMA_VERSION)

        existing_cache_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(cache)").fetchall()
        }
        for col_name, col_type in CACHE_NEW_COLUMNS:
            if col_name not in existing_cache_cols:
                conn.execute(f"ALTER TABLE cache ADD COLUMN {col_name} {col_type}")

        for idx_sql in CACHE_NEW_INDEXES:
            try:
                conn.execute(idx_sql)
            except sqlite3.OperationalError:
                pass

        existing_task_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(task_history)").fetchall()
        }
        for col_name, col_type in TASK_NEW_COLUMNS:
            if col_name not in existing_task_cols:
                conn.execute(f"ALTER TABLE task_history ADD COLUMN {col_name} {col_type}")

        for idx_sql in TASK_NEW_INDEXES:
            try:
                conn.execute(idx_sql)
            except sqlite3.OperationalError:
                pass

        conn.executescript(CREATE_SETTINGS)
        conn.executescript(CREATE_API_USAGE)
        conn.executescript(CREATE_CONFIG_HISTORY)
        conn.executescript(CREATE_CACHE_STATS_DAILY)

        if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            env_keys = [
                ("AMAP_KEY", Config.AMAP_KEY),
                ("BAIDU_AK", Config.BAIDU_AK),
                ("TIANDITU_TK", Config.TIANDITU_TK),
                ("AI_ENABLED", str(Config.AI_ENABLED).lower()),
                ("AI_PROVIDER", Config.AI_PROVIDER),
                ("AI_MODEL", Config.AI_MODEL),
                ("DEEPSEEK_API_KEY", Config.DEEPSEEK_API_KEY),
                ("QWEN_API_KEY", Config.QWEN_API_KEY),
                ("GLM_API_KEY", Config.GLM_API_KEY),
                ("MOONSHOT_API_KEY", Config.MOONSHOT_API_KEY),
                ("ROUTING_MODE", Config.ROUTING_MODE),
            ]
            now = time.time()
            for key, value in env_keys:
                if value:
                    conn.execute(
                        "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?,?,?)",
                        (key, value, now),
                    )

    # ── Settings CRUD ────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str, source: str = "api") -> None:
        old_value = self.get_setting(key)
        with self.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,?)",
                (key, value, time.time()),
            )
            masked_old = self._mask_value(old_value) if old_value else ""
            masked_new = self._mask_value(value)
            conn.execute(
                "INSERT INTO config_history (key, old_value, new_value, changed_at, changed_via) VALUES (?,?,?,?,?)",
                (key, masked_old, masked_new, time.time(), source),
            )

    def get_masked_setting(self, key: str) -> str:
        value = self.get_setting(key)
        if not value:
            return ""
        return self._mask_value(value)

    def get_all_settings(self) -> Dict[str, str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: row["value"] for row in rows}

    def get_all_masked_settings(self) -> Dict[str, str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: self._mask_value(row["value"]) for row in rows}

    @staticmethod
    def _mask_value(value: str) -> str:
        if not value:
            return ""
        n = len(value)
        if n <= 4:
            return "****"
        if n <= 8:
            return value[:2] + "****" + value[-2:]
        return value[:4] + "****" + value[-4:]

    # ── API Usage ────────────────────────────────────────────────

    def record_api_call(self, api_name: str, success: bool) -> None:
        today = time.strftime("%Y-%m-%d")
        now = time.time()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT call_count, success_count, fail_count FROM api_usage WHERE api_name = ? AND call_date = ?",
                (api_name, today),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE api_usage SET call_count = call_count + 1, "
                    "success_count = success_count + ?, fail_count = fail_count + ?, "
                    "last_called = ? WHERE api_name = ? AND call_date = ?",
                    (1 if success else 0, 0 if success else 1, now, api_name, today),
                )
            else:
                conn.execute(
                    "INSERT INTO api_usage (api_name, call_date, call_count, success_count, fail_count, last_called) "
                    "VALUES (?,?,?,?,?,?)",
                    (api_name, today, 1, 1 if success else 0, 0 if success else 1, now),
                )

    def get_api_usage(self, api_name: str = None, days: int = 30) -> List[Dict]:
        with self.connection() as conn:
            if api_name:
                rows = conn.execute(
                    "SELECT * FROM api_usage WHERE api_name = ? AND call_date >= date('now', ?||' days') ORDER BY call_date DESC",
                    (api_name, f"-{days}"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM api_usage WHERE call_date >= date('now', ?||' days') ORDER BY call_date DESC",
                    (f"-{days}",),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_today_usage(self, api_name: str) -> Dict:
        today = time.strftime("%Y-%m-%d")
        limit = Config.API_DAILY_LIMITS.get(api_name, Config.AI_DAILY_LIMITS.get(api_name, 0))
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM api_usage WHERE api_name = ? AND call_date = ?",
                (api_name, today),
            ).fetchone()
            if row:
                d = dict(row)
                d["daily_limit"] = limit
                d["remaining"] = max(0, limit - d["call_count"]) if limit else None
                return d
            return {
                "api_name": api_name,
                "call_date": today,
                "call_count": 0,
                "success_count": 0,
                "fail_count": 0,
                "daily_limit": limit,
                "remaining": limit if limit else None,
                "last_called": None,
            }

    def get_today_usage_all(self) -> Dict[str, Dict]:
        result = {}
        for api_name in Config.API_PRIORITY:
            result[api_name] = self.get_today_usage(api_name)
        for ai_name in Config.AI_DAILY_LIMITS:
            result[ai_name] = self.get_today_usage(ai_name)
        return result

    # ── Config History ────────────────────────────────────────────

    def get_config_history(self, key: str = None, limit: int = 50) -> List[Dict]:
        with self.connection() as conn:
            if key:
                rows = conn.execute(
                    "SELECT * FROM config_history WHERE key = ? ORDER BY changed_at DESC LIMIT ?",
                    (key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM config_history ORDER BY changed_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

    # ── Cache Stats Daily ─────────────────────────────────────────

    def record_daily_stats(
        self, hits: int, misses: int, total: int, evictions: int = 0
    ) -> None:
        today = time.strftime("%Y-%m-%d")
        total_req = hits + misses
        hit_rate = round(hits / total_req * 100, 2) if total_req > 0 else 0.0
        with self.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_stats_daily (stat_date, hits, misses, hit_rate, total_entries, evictions) "
                "VALUES (?,?,?,?,?,?)",
                (today, hits, misses, hit_rate, total, evictions),
            )

    def get_stats_history(self, days: int = 30) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM cache_stats_daily WHERE stat_date >= date('now', ?||' days') ORDER BY stat_date DESC",
                (f"-{days}",),
            ).fetchall()
            return [dict(row) for row in rows]

    # ── Task History (代理方法) ───────────────────────────────────

    def save_task(self, task_data: dict) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO task_history "
                "(task_id, status, input_file, column, city, workers, total, success, failed, "
                "csv_output, map_output, started_at, completed_at, duration_sec, error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    task_data.get("task_id"),
                    task_data.get("status"),
                    task_data.get("input_file", ""),
                    task_data.get("column", "地址"),
                    task_data.get("city"),
                    task_data.get("workers", 1),
                    task_data.get("total", 0),
                    task_data.get("success", 0),
                    task_data.get("failed", 0),
                    task_data.get("csv_output"),
                    task_data.get("map_output"),
                    task_data.get("started_at", time.time()),
                    task_data.get("completed_at"),
                    task_data.get("duration_sec"),
                    task_data.get("error"),
                ),
            )

    def get_all_tasks(self) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT task_id, status, input_file, column, city, workers, "
                "total, success, failed, csv_output, map_output, "
                "started_at, completed_at, duration_sec, error "
                "FROM task_history ORDER BY started_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT task_id, status, input_file, column, city, workers, "
                "total, success, failed, csv_output, map_output, "
                "started_at, completed_at, duration_sec, error "
                "FROM task_history WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

    def delete_task(self, task_id: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM task_history WHERE task_id = ?", (task_id,)
            )
            return cursor.rowcount > 0

    def cleanup_old_tasks(self, days: int = 30) -> int:
        cutoff = time.time() - days * 24 * 3600
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM task_history WHERE completed_at < ? AND status IN ('done', 'error')",
                (cutoff,),
            )
            return cursor.rowcount

    # ── Cache Export ──────────────────────────────────────────────

    def export_cache_entries(self) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT key, address, source, formatted_address, province, city, district, "
                "latitude, longitude, confidence, created_at, expires_at, access_count, last_accessed "
                "FROM cache ORDER BY last_accessed DESC NULLS LAST"
            ).fetchall()
            return [dict(row) for row in rows]

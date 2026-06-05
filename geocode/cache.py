"""
混合架构地理编码缓存

特性:
- 内存优先缓存（无锁读写）
- 异步持久化队列（后台单线程写入 SQLite）
- 启动时加载历史缓存（断点续传）
- 程序退出时确保数据落盘
- 优雅关闭 + atexit 保护
- 通过 DatabaseManager 统一连接管理，消除裸连接
- 扩展持久化字段（formatted_address, province, city, district, lat/lon, confidence, access_count）
"""

import atexit
import json
import logging
import queue
import shutil
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import OutputPaths

logger = logging.getLogger(__name__)


class CacheManager:
    """
    混合架构缓存管理器：内存优先 + 异步持久化

    架构设计：
    - 内存 LRU 缓存（主缓存，RLock 保护线程安全）
    - 持久化队列（线程安全 Queue）
    - 持久化线程（独占 SQLite 连接，无竞争）
    - 临时连接通过 DatabaseManager 获取（统一 PRAGMA）
    - 批量预热查询（get_batch_prefetch）减少逐条查询开销
    """

    INIT_SQL = """
    CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        address TEXT,
        data TEXT NOT NULL,
        created_at REAL,
        expires_at REAL,
        source TEXT,
        formatted_address TEXT,
        province TEXT,
        city TEXT,
        district TEXT,
        latitude REAL,
        longitude REAL,
        confidence REAL,
        access_count INTEGER DEFAULT 1,
        last_accessed REAL
    );
    CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at);
    CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache(last_accessed);
    """

    DEFAULT_MEM_SIZE = 5000
    DEFAULT_PERSIST_BATCH = 100
    DEFAULT_BATCH_THRESHOLD = 50  # 默认批量写入阈值

    def __init__(
        self,
        cache_file: str = str(OutputPaths.DATABASE / "geocache.db"),
        default_ttl: float = None,
        batch_size: int = None,
        mem_cache_size: int = DEFAULT_MEM_SIZE,
        persist_batch_size: int = DEFAULT_PERSIST_BATCH,
        load_on_start: bool = True,
        batch_threshold: int = None,  # 批量写入阈值，默认50
    ):
        self._path = Path(cache_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = default_ttl
        self._persist_batch_size = persist_batch_size if batch_size is None else batch_size
        self._batch_threshold = batch_threshold if batch_threshold is not None else self.DEFAULT_BATCH_THRESHOLD

        self._hits = 0
        self._misses = 0
        self._evictions = 0

        self._mem_cache: OrderedDict = OrderedDict()
        self._mem_maxsize = max(1, mem_cache_size)
        self._cache_lock = threading.RLock()

        self._write_queue: queue.Queue = queue.Queue()

        self._persist_conn = None
        self._persist_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._flush_done_event = threading.Event()

        self._watchdog_thread = None
        self._watchdog_stop = None
        self._conn = None

        self._recovery_callback: Optional[Callable[[Any], None]] = None

        self._init_db()
        if load_on_start:
            self._load_from_db()
        self._start_persist_thread()

        atexit.register(self._emergency_flush)

    def set_recovery_callback(self, callback: Callable[[Any], None]) -> None:
        self._recovery_callback = callback

    def _get_db(self):
        from .db import DatabaseManager
        return DatabaseManager.get_instance(str(self._path))

    def _init_db(self) -> None:
        try:
            db = self._get_db()
        except Exception:
            db = None

        if db:
            db._ensure_schema()
            return

        import sqlite3
        conn = sqlite3.connect(str(self._path), timeout=30)
        try:
            conn.executescript(self.INIT_SQL)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.commit()
        except sqlite3.DatabaseError:
            self._rebuild_db_with_conn(conn)
        finally:
            conn.close()

    def _rebuild_db_with_conn(self, conn) -> None:
        if self._recovery_callback:
            try:
                self._recovery_callback({
                    'type': 'cache_recovery',
                    'message': '数据库损坏，正在重建...',
                    'timestamp': time.time()
                })
            except Exception:
                pass

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

        conn.executescript(self.INIT_SQL)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        if self._recovery_callback:
            try:
                self._recovery_callback({
                    'type': 'cache_recovery_done',
                    'message': '数据库已恢复',
                    'timestamp': time.time()
                })
            except Exception:
                pass

    def _load_from_db(self) -> None:
        loaded = []
        try:
            db = self._get_db()
            with db.connection() as conn:
                now = time.time()
                cursor = conn.execute(
                    "SELECT key, data, expires_at FROM cache WHERE expires_at IS NULL OR expires_at > ?",
                    (now,)
                )
                for key, data_json, expires_at in cursor:
                    try:
                        data = json.loads(data_json)
                        loaded.append((key, data, expires_at))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                now = time.time()
                cursor = conn.execute(
                    "SELECT key, data, expires_at FROM cache WHERE expires_at IS NULL OR expires_at > ?",
                    (now,)
                )
                for key, data_json, expires_at in cursor:
                    try:
                        data = json.loads(data_json)
                        loaded.append((key, data, expires_at))
                    except json.JSONDecodeError:
                        continue
            except (sqlite3.DatabaseError, sqlite3.OperationalError):
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        with self._cache_lock:
            for key, data, expires_at in loaded:
                if len(self._mem_cache) >= self._mem_maxsize:
                    try:
                        self._mem_cache.popitem(last=False)
                    except KeyError:
                        pass
                self._mem_cache[key] = {"data": data, "expires_at": expires_at}

    def _start_persist_thread(self) -> None:
        self._persist_thread = threading.Thread(
            target=self._persist_thread_main,
            daemon=True,
            name="CachePersistence"
        )
        self._persist_thread.start()

    def _persist_thread_main(self) -> None:
        import sqlite3
        try:
            self._persist_conn = sqlite3.connect(str(self._path), timeout=30)
            self._persist_conn.execute("PRAGMA journal_mode=WAL")
            self._persist_conn.execute("PRAGMA synchronous=NORMAL")
            self._persist_conn.execute("PRAGMA busy_timeout=30000")
            self._persist_conn.row_factory = sqlite3.Row
            self._conn = self._persist_conn

            try:
                self._persist_conn.execute(
                    "CREATE TABLE IF NOT EXISTS cache ("
                    "key TEXT PRIMARY KEY, address TEXT, data TEXT NOT NULL, "
                    "created_at REAL, expires_at REAL, source TEXT)"
                )
            except Exception:
                pass

            self._migrate_table_schema()

            try:
                self._persist_conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)"
                )
            except sqlite3.OperationalError:
                pass
            try:
                self._persist_conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache(last_accessed)"
                )
            except sqlite3.OperationalError:
                pass

            self._persist_loop()
        except Exception:
            logger.error("缓存持久化线程异常退出，数据可能丢失", exc_info=True)
            try:
                remaining = []
                while True:
                    try:
                        item = self._write_queue.get_nowait()
                        remaining.append(item)
                    except queue.Empty:
                        break
                if remaining:
                    logger.warning("持久化线程退出时队列中仍有 %d 条未写入数据", len(remaining))
            except Exception:
                pass
        finally:
            if self._persist_conn:
                try:
                    self._persist_conn.close()
                except Exception:
                    pass
            self._persist_conn = None
            self._conn = None

    def _migrate_table_schema(self) -> None:
        """自动添加缺失的扩展字段（兼容旧数据库）"""
        required_columns = {
            'formatted_address': 'TEXT',
            'province': 'TEXT',
            'city': 'TEXT',
            'district': 'TEXT',
            'latitude': 'REAL',
            'longitude': 'REAL',
            'confidence': 'REAL',
            'access_count': 'INTEGER DEFAULT 1',
            'last_accessed': 'REAL',
        }

        try:
            # 获取现有列
            existing = self._persist_conn.execute(
                "SELECT name FROM pragma_table_info('cache')"
            ).fetchall()
            existing_columns = {row[0] for row in existing}

            # 添加缺失列
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    try:
                        self._persist_conn.execute(
                            f"ALTER TABLE cache ADD COLUMN {col_name} {col_type}"
                        )
                    except Exception:
                        pass  # 列已存在或添加失败

            self._persist_conn.commit()
        except Exception:
            logger.warning("缓存表结构迁移失败，扩展字段可能不可用", exc_info=True)

    def _persist_loop(self) -> None:
        while not self._shutdown_event.is_set():
            batch = []
            flush_requested = False

            try:
                first = self._write_queue.get(timeout=0.5)
                if first is None:
                    flush_requested = True
                else:
                    batch.append(first)
            except queue.Empty:
                continue

            # 收集更多消息，最多到阈值
            while len(batch) < self._batch_threshold:
                try:
                    item = self._write_queue.get_nowait()
                    if item is None:
                        flush_requested = True
                        break
                    batch.append(item)
                except queue.Empty:
                    break

            # 处理批次（无论是否达到阈值）
            if batch:
                self._process_batch(batch)

            if flush_requested:
                self._flush_done_event.set()

        self._flush_remaining()

    def _convert_legacy_message(self, item) -> tuple:
        """转换旧格式消息到新格式

        旧格式：(key, address, data, ttl)
        新格式：('write', key, address, data, ttl) 或 ('access', key)
        """
        if isinstance(item, tuple):
            if len(item) == 5 and item[0] in ('write', 'access'):
                # 新格式，直接返回
                return item
            elif len(item) == 4:
                key, address, data, ttl = item
                if data is None and address is None and ttl is None:
                    # 旧格式的访问消息 (key, None, None, None)
                    return ('access', key)
                else:
                    # 旧格式的写入消息
                    return ('write', key, address, data, ttl)
        return item

    def _process_batch(self, batch: List[tuple]) -> None:
        """处理批量消息，拆分写入和访问操作"""
        write_batch = []  # (key, address, data, ttl)
        access_batch = []  # (key)

        for item in batch:
            item = self._convert_legacy_message(item)
            if item[0] == 'write':
                write_batch.append(item[1:])
            elif item[0] == 'access':
                access_batch.append(item[1])

        # 先处理写入（确保数据存在）
        if write_batch:
            self._persist_write_batch(write_batch)

        # 再处理访问更新
        if access_batch:
            self._persist_access_batch(access_batch)

    def _persist_write_batch(self, batch: List[tuple]) -> None:
        """写入新数据，基于置信度决定是否替换"""
        try:
            self._persist_conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            for key, address, data, ttl in batch:
                expires = now + ttl if ttl else None
                new_confidence = data.get('confidence', {}).get('total', 0) if data else 0

                # 检查是否已存在
                row = self._persist_conn.execute(
                    "SELECT confidence FROM cache WHERE key = ?", (key,)
                ).fetchone()

                if row is None:
                    # 新记录，直接 INSERT
                    self._persist_conn.execute(
                        "INSERT INTO cache (key, address, data, created_at, expires_at, source, "
                        "formatted_address, province, city, district, latitude, longitude, confidence, "
                        "access_count, last_accessed) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                        (
                            key, address, json.dumps(data, ensure_ascii=False), now, expires,
                            data.get('source') if data else None,
                            data.get('formatted_address') if data else None,
                            data.get('province') if data else None,
                            data.get('city') if data else None,
                            data.get('district') if data else None,
                            data.get('latitude') if data else None,
                            data.get('longitude') if data else None,
                            new_confidence,
                            now,
                        )
                    )
                else:
                    # 已存在，比较置信度
                    old_confidence = row[0] if row else 0  # row[0] 是 confidence 列

                    new_has_formatted = bool(data.get('formatted_address')) if data else False
                    should_replace = new_confidence >= old_confidence

                    if not should_replace and new_has_formatted:
                        try:
                            old_row = self._persist_conn.execute(
                                "SELECT data FROM cache WHERE key = ?", (key,)
                            ).fetchone()
                            if old_row:
                                old_data = json.loads(old_row[0])
                                if not old_data.get('formatted_address'):
                                    should_replace = True
                        except Exception:
                            pass

                    if should_replace:
                        # 新数据置信度 >= 旧数据，全字段替换
                        self._persist_conn.execute(
                            "UPDATE cache SET address=?, data=?, source=?, formatted_address=?, "
                            "province=?, city=?, district=?, latitude=?, longitude=?, confidence=?, "
                            "expires_at=?, created_at=?, last_accessed=? WHERE key=?",
                            (
                                address, json.dumps(data, ensure_ascii=False),
                                data.get('source') if data else None,
                                data.get('formatted_address') if data else None,
                                data.get('province') if data else None,
                                data.get('city') if data else None,
                                data.get('district') if data else None,
                                data.get('latitude') if data else None,
                                data.get('longitude') if data else None,
                                new_confidence,
                                expires,
                                now,
                                now,
                                key,
                            )
                        )
                    # 置信度更低则保留旧数据，不更新
            self._persist_conn.commit()
            try:
                self._persist_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
        except Exception:
            # 转换为新格式后调用原有失败处理
            self._handle_persist_failure([('write', *item) for item in batch])

    def _persist_access_batch(self, keys: List[str]) -> None:
        """仅累加访问计数"""
        try:
            self._persist_conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            for key in keys:
                # 如果 key 不存在，忽略（数据应该已通过 write 写入）
                self._persist_conn.execute(
                    "UPDATE cache SET access_count = access_count + 1, last_accessed = ? WHERE key = ?",
                    (now, key)
                )
            self._persist_conn.commit()
        except Exception:
            # 失败不影响主流程，仅记录日志
            pass

    def _handle_persist_failure(self, batch: List[tuple]) -> None:
        """处理写入失败的批量数据"""
        import sqlite3
        import sys as _sys

        # 提取 write 操作的数据（忽略 access 操作）
        write_items = []
        for item in batch:
            if isinstance(item, tuple) and len(item) >= 1:
                if item[0] == 'write':
                    write_items.append(item[1:])  # (key, address, data, ttl)

        for attempt in range(3):
            try:
                self._persist_conn.execute("BEGIN IMMEDIATE")
                now = time.time()
                for key, address, data, ttl in write_items:
                    expires = now + ttl if ttl else None
                    new_confidence = data.get('confidence', {}).get('total', 0) if data else 0

                    row = self._persist_conn.execute(
                        "SELECT confidence FROM cache WHERE key = ?", (key,)
                    ).fetchone()

                    if row is None:
                        self._persist_conn.execute(
                            "INSERT INTO cache (key, address, data, created_at, expires_at, source, "
                            "formatted_address, province, city, district, latitude, longitude, confidence, "
                            "access_count, last_accessed) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                            (key, address, json.dumps(data, ensure_ascii=False), now, expires,
                             data.get('source') if data else None,
                             data.get('formatted_address') if data else None,
                             data.get('province') if data else None,
                             data.get('city') if data else None,
                             data.get('district') if data else None,
                             data.get('latitude') if data else None,
                             data.get('longitude') if data else None,
                             new_confidence, now)
                        )
                    else:
                        old_confidence = row[0] if row else 0  # row[0] 是 confidence 列
                        if new_confidence >= old_confidence:
                            self._persist_conn.execute(
                                "UPDATE cache SET address=?, data=?, source=?, formatted_address=?, "
                                "province=?, city=?, district=?, latitude=?, longitude=?, confidence=?, "
                                "expires_at=?, created_at=?, last_accessed=? WHERE key=?",
                                (address, json.dumps(data, ensure_ascii=False),
                                 data.get('source') if data else None,
                                 data.get('formatted_address') if data else None,
                                 data.get('province') if data else None,
                                 data.get('city') if data else None,
                                 data.get('district') if data else None,
                                 data.get('latitude') if data else None,
                                 data.get('longitude') if data else None,
                                 new_confidence, expires, now, now, key)
                            )
                self._persist_conn.commit()
                return
            except Exception:
                try:
                    self._persist_conn.rollback()
                except Exception:
                    pass
                time.sleep(0.3 * (attempt + 1))

        print(f"[cache] WARNING: 持久化失败(重试3次) — {len(write_items)} 条数据放回队列",
              file=_sys.stderr, flush=True)
        for item in write_items:
            self._write_queue.put(('write', *item))
        try:
            self._persist_conn.close()
        except Exception:
            pass
        try:
            self._persist_conn = sqlite3.connect(str(self._path), timeout=30)
            self._persist_conn.execute("PRAGMA journal_mode=WAL")
            self._persist_conn.execute("PRAGMA synchronous=NORMAL")
            self._persist_conn.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass

    def _flush_remaining(self) -> None:
        remaining = []
        while True:
            try:
                item = self._write_queue.get_nowait()
                remaining.append(item)
            except queue.Empty:
                break
        if remaining:
            self._process_batch(remaining)

    def _emergency_flush(self) -> None:
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()
            if self._persist_thread:
                self._persist_thread.join(timeout=5)
        if self._persist_conn is not None:
            try:
                self._flush_remaining()
            except Exception:
                logger.warning("紧急刷新时写入失败", exc_info=True)
            try:
                self._persist_conn.close()
            except Exception:
                pass
            self._persist_conn = None

    @staticmethod
    def _normalize_key(address: str) -> str:
        if not address:
            return ""

        import re

        key = address.strip().lower()

        province_prefixes = [
            "广西壮族自治区", "新疆维吾尔自治区", "宁夏回族自治区",
            "内蒙古自治区", "西藏自治区",
            "香港特别行政区", "澳门特别行政区",
            "广东省", "四川省", "浙江省", "江苏省",
            "山东省", "河南省", "湖北省", "湖南省",
            "安徽省", "福建省", "江西省", "河北省",
            "山西省", "辽宁省", "吉林省", "黑龙江省",
            "陕西省", "甘肃省", "青海省",
            "云南", "贵州省", "海南省",
            "北京市", "上海市", "天津市", "重庆市",
        ]
        for prefix in province_prefixes:
            if key.startswith(prefix.lower()):
                key = key[len(prefix):]

        key = re.sub(r'(市){2,}', '市', key)
        key = re.sub(r'(区){2,}', '区', key)
        key = re.sub(r'\s+', '', key)

        return key

    # === 公开 API ===

    def get(self, address: str) -> Optional[Dict]:
        key = self._normalize_key(address)

        with self._cache_lock:
            if key in self._mem_cache:
                entry = self._mem_cache[key]
                if entry["expires_at"] and entry["expires_at"] < time.time():
                    try:
                        self._mem_cache.pop(key, None)
                        self._evictions += 1
                    except KeyError:
                        pass
                    self._misses += 1
                    return None
                try:
                    self._mem_cache.move_to_end(key)
                except KeyError:
                    pass
                self._hits += 1
                data = entry["data"]
                self._write_queue.put(('access', key))
                return data

        self._misses += 1
        return None

    _BATCH_CHUNK_SIZE = 500

    def get_batch(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        if not addresses:
            return {}
        results: Dict[str, Optional[Dict]] = {}
        for addr in addresses:
            results[addr] = self.get(addr)
        return results

    def get_batch_prefetch(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """批量缓存预热：一次获取所有缓存命中，减少逐条查缓存开销。

        Args:
            addresses: 原始地址列表

        Returns:
            字典：{原始地址: 缓存结果或None}
        """
        if not addresses:
            return {}
        results: Dict[str, Optional[Dict]] = {}
        with self._cache_lock:
            now = time.time()
            for addr in addresses:
                key = self._normalize_key(addr)
                if key in self._mem_cache:
                    entry = self._mem_cache[key]
                    if entry["expires_at"] and entry["expires_at"] < now:
                        try:
                            self._mem_cache.pop(key, None)
                            self._evictions += 1
                        except KeyError:
                            pass
                        self._misses += 1
                        results[addr] = None
                    else:
                        try:
                            self._mem_cache.move_to_end(key)
                        except KeyError:
                            pass
                        self._hits += 1
                        results[addr] = entry["data"]
                else:
                    self._misses += 1
                    results[addr] = None
        for addr, data in results.items():
            if data is not None:
                key = self._normalize_key(addr)
                self._write_queue.put(('access', key))
        return results

    def set(self, address: str, result: Dict, ttl: float = None) -> None:
        key = self._normalize_key(address)
        effective_ttl = ttl if ttl is not None else self._ttl
        expires = time.time() + effective_ttl if effective_ttl else None

        if result is not None:
            with self._cache_lock:
                if len(self._mem_cache) >= self._mem_maxsize:
                    try:
                        self._mem_cache.popitem(last=False)
                        self._evictions += 1
                    except KeyError:
                        pass
                self._mem_cache[key] = {"data": dict(result), "expires_at": expires}
                try:
                    self._mem_cache.move_to_end(key)
                except KeyError:
                    pass

        self._write_queue.put(('write', key, address, result, effective_ttl))

    def flush(self) -> None:
        self._flush_done_event.clear()
        self._write_queue.put(None)
        self._flush_done_event.wait(timeout=5)
        while not self._write_queue.empty():
            time.sleep(0.1)

    def delete(self, address: str) -> bool:
        key = self._normalize_key(address)
        with self._cache_lock:
            existed = key in self._mem_cache
            try:
                self._mem_cache.pop(key, None)
            except KeyError:
                pass

        try:
            db = self._get_db()
            with db.connection() as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                conn.close()
            except sqlite3.Error:
                pass

        return existed

    def clear(self) -> int:
        with self._cache_lock:
            count = len(self._mem_cache)
            self._mem_cache.clear()

        try:
            db = self._get_db()
            with db.connection() as conn:
                conn.execute("DELETE FROM cache")
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                conn.execute("DELETE FROM cache")
                conn.commit()
                conn.close()
            except sqlite3.Error:
                pass

        self._hits = 0
        self._misses = 0
        self._evictions = 0
        return count

    def cleanup(self) -> int:
        now = time.time()
        cleaned = 0
        with self._cache_lock:
            expired_keys = []
            for key, entry in self._mem_cache.items():
                if entry["expires_at"] and entry["expires_at"] < now:
                    expired_keys.append(key)
            for key in expired_keys:
                try:
                    self._mem_cache.pop(key, None)
                    cleaned += 1
                except KeyError:
                    pass

        try:
            db = self._get_db()
            with db.connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now,)
                )
                cleaned += cursor.rowcount
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                cursor = conn.execute(
                    "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now,)
                )
                conn.commit()
                cleaned += cursor.rowcount
                conn.close()
            except sqlite3.Error:
                pass

        return cleaned

    def get_stats(self) -> Dict:
        mem_entries = len(self._mem_cache)

        try:
            db = self._get_db()
            with db.connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                expired = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),)
                ).fetchone()[0]
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                expired = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),)
                ).fetchone()[0]
                conn.close()
            except sqlite3.Error:
                total = 0
                expired = 0

        total_requests = self._hits + self._misses
        hit_rate = round(self._hits / total_requests * 100, 2) if total_requests > 0 else 0.0

        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate,
            'total_entries': total,
            'mem_entries': mem_entries,
            'mem_max': self._mem_maxsize,
            'expired_entries': expired,
            'queue_size': self._write_queue.qsize(),
            'pending_writes': self._write_queue.qsize(),
            'evictions': self._evictions,
        }

    def count(self) -> int:
        try:
            db = self._get_db()
            with db.connection() as conn:
                return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                conn.close()
                return total
            except sqlite3.Error:
                return len(self._mem_cache)

    def export_entries(self) -> List[Dict]:
        try:
            db = self._get_db()
            return db.export_cache_entries()
        except Exception:
            import sqlite3
            try:
                conn = sqlite3.connect(str(self._path), timeout=30)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT key, address, source, formatted_address, province, city, district, "
                    "latitude, longitude, confidence, created_at, expires_at, access_count, last_accessed "
                    "FROM cache ORDER BY last_accessed DESC"
                ).fetchall()
                result = [dict(row) for row in rows]
                conn.close()
                return result
            except sqlite3.Error:
                return []

    def start_watchdog(self, interval: float = 30.0) -> None:
        self._watchdog_stop = threading.Event()
        self._watchdog_thread = self._persist_thread

    def stop_watchdog(self) -> None:
        self._watchdog_thread = None
        self._watchdog_stop = None

    def close(self) -> None:
        try:
            atexit.unregister(self._emergency_flush)
        except Exception:
            pass

        try:
            db = self._get_db()
            db.record_daily_stats(
                hits=self._hits, misses=self._misses,
                total=self.count(), evictions=self._evictions,
            )
        except Exception:
            pass

        self._shutdown_event.set()
        if self._persist_thread:
            self._persist_thread.join(timeout=10)
        if self._persist_conn:
            try:
                self._persist_conn.close()
            except Exception:
                pass
            self._persist_conn = None

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, address: str) -> bool:
        return self.get(address) is not None

    def __enter__(self) -> 'CacheManager':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

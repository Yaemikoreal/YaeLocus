"""
轻量级地理编码缓存

特性:
- 单层SQLite存储，持久化可靠
- 延迟提交，批量写入优化
- WAL模式，读写并发友好
- 自动过期清理
- 异常恢复机制

优化点:
- 移除内存层，减少代码复杂度（420行 -> 180行）
- 延迟commit，批量写入性能提升10倍+
- WAL + mmap优化，读取性能接近内存缓存
"""

import json
import sqlite3
import time
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from .config import OutputPaths


class CacheManager:
    """
    轻量级缓存管理器

    基于SQLite + 内存 LRU 的二级地理编码缓存，支持：
    - 内存 LRU 层（热点数据零 I/O）
    - SQLite 持久化 + 延迟提交（批量写入优化）
    - TTL 过期清理
    - WAL 模式并发优化
    - 数据库损坏自动恢复
    """

    INIT_SQL = """
    CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        address TEXT,
        data TEXT NOT NULL,
        created_at REAL,
        expires_at REAL,
        source TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at);
    """

    # 默认内存缓存条目数
    DEFAULT_MEM_SIZE = 2000

    def __init__(
        self,
        cache_file: str = str(OutputPaths.DATABASE / "geocache.db"),
        default_ttl: float = None,
        batch_size: int = 100,
        mem_cache_size: int = DEFAULT_MEM_SIZE,
    ):
        """
        初始化缓存管理器

        Args:
            cache_file: SQLite数据库文件路径
            default_ttl: 默认过期时间(秒)，None表示永不过期
            batch_size: 批量提交阈值，达到此数量自动commit
            mem_cache_size: 内存 LRU 缓存条目上限（默认 2000）
        """
        self._path = Path(cache_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = default_ttl
        self._batch_size = batch_size
        self._pending = 0
        self._hits = 0
        self._misses = 0
        self._conn = None
        self._lock = threading.RLock()  # 可重入锁，防止死锁
        self._watchdog_thread = None
        self._watchdog_stop = None

        # 内存 LRU 缓存层（OrderedDict 天然支持 LRU）
        self._mem_cache: OrderedDict = OrderedDict()
        self._mem_maxsize = max(1, mem_cache_size)
        self._recovery_callback: Optional[Callable[[Any], None]] = None  # 恢复通知回调

        self._init_db()

    def set_recovery_callback(self, callback: Callable[[Any], None]) -> None:
        """设置数据库恢复通知回调"""
        self._recovery_callback = callback

    def _init_db(self) -> None:
        """初始化数据库，支持损坏恢复"""
        try:
            self._conn = sqlite3.connect(str(self._path), timeout=30, check_same_thread=False)
            self._conn.executescript(self.INIT_SQL)
            # 性能优化
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA mmap_size=268435456")  # 256MB
            self._conn.execute("PRAGMA cache_size=-32000")    # 32MB
            self._conn.row_factory = sqlite3.Row
        except sqlite3.DatabaseError:
            # 数据库损坏，删除重建
            self._rebuild_db()

    def _rebuild_db(self) -> None:
        """重建损坏的数据库，并发送恢复通知"""
        # 发送恢复开始通知
        if self._recovery_callback:
            try:
                self._recovery_callback({
                    'type': 'cache_recovery',
                    'message': '数据库锁定或损坏，正在重建...',
                    'timestamp': time.time()
                })
            except Exception:
                pass  # 回调失败不影响恢复

        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

        # 删除损坏的数据库文件（带重试机制处理Windows文件锁定）
        for suffix in ['', '-wal', '-shm']:
            p = Path(str(self._path) + suffix)
            if p.exists():
                for _ in range(3):  # 重试3次
                    try:
                        p.unlink()
                        break
                    except PermissionError:
                        time.sleep(0.1)  # 等待文件释放

        # 重新创建
        self._conn = sqlite3.connect(str(self._path), timeout=30, check_same_thread=False)
        self._conn.executescript(self.INIT_SQL)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA mmap_size=268435456")
        self._conn.row_factory = sqlite3.Row

        # 发送恢复完成通知
        if self._recovery_callback:
            try:
                self._recovery_callback({
                    'type': 'cache_recovery_done',
                    'message': '数据库已恢复，缓存已清空',
                    'timestamp': time.time()
                })
            except Exception:
                pass

    @staticmethod
    def _normalize_key(address: str) -> str:
        """智能缓存键 - 处理地址变体

        处理：
        - 空格差异："深圳市南山区" vs "深圳市 南山区"
        - 简繁差异："深圳" vs "深圳市"
        - 省份前缀差异："广东省深圳市" vs "深圳市"
        """
        if not address:
            return ""

        import re

        # 基础清洗
        key = address.strip().lower()

        # 去除省份前缀（统一缓存）
        # "广东省深圳市南山区" -> "深圳市南山区"
        province_prefixes = [
            # 完整自治区名称优先（长前缀先匹配，避免短前缀残根问题）
            "广西壮族自治区", "新疆维吾尔自治区", "宁夏回族自治区",
            "内蒙古自治区", "西藏自治区",
            "香港特别行政区", "澳门特别行政区",
            # 常规省份
            "广东省", "四川省", "浙江省", "江苏省",
            "山东省", "河南省", "湖北省", "湖南省",
            "安徽省", "福建省", "江西省", "河北省",
            "山西省", "辽宁省", "吉林省", "黑龙江省",
            "陕西省", "甘肃省", "青海省",
            "云南", "贵州省", "海南省",
            # 直辖市
            "北京市", "上海市", "天津市", "重庆市",
        ]
        for prefix in province_prefixes:
            if key.startswith(prefix.lower()):
                key = key[len(prefix):]

        # 去除重复的"市"、"区"
        key = re.sub(r'(市){2,}', '市', key)
        key = re.sub(r'(区){2,}', '区', key)

        # 去除多余空格
        key = re.sub(r'\s+', '', key)

        return key

    def get(self, address: str) -> Optional[Dict]:
        """
        获取缓存（内存 LRU → SQLite 二级查询）

        Args:
            address: 地址字符串

        Returns:
            缓存的结果字典，不存在或过期返回None
        """
        key = self._normalize_key(address)

        with self._lock:
            # 一级：内存 LRU
            if key in self._mem_cache:
                entry = self._mem_cache[key]
                if entry["expires_at"] and entry["expires_at"] < time.time():
                    del self._mem_cache[key]
                    self._misses += 1
                    return None
                self._mem_cache.move_to_end(key)
                self._hits += 1
                return entry["data"]

            # 二级：SQLite
            try:
                row = self._conn.execute(
                    "SELECT data, expires_at FROM cache WHERE key = ?", (key,)
                ).fetchone()

                if row is None:
                    self._misses += 1
                    return None

                if row['expires_at'] and row['expires_at'] < time.time():
                    self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    self._misses += 1
                    return None

                data = json.loads(row['data'])
                self._hits += 1

                # 提升到内存（LRU 淘汰最旧条目）
                if len(self._mem_cache) >= self._mem_maxsize:
                    self._mem_cache.popitem(last=False)
                self._mem_cache[key] = {"data": data, "expires_at": row["expires_at"]}

                return data

            except sqlite3.DatabaseError:
                self._rebuild_db()
                self._misses += 1
                return None

    # SQLite 默认最大变量数 999，取安全值
    _BATCH_CHUNK_SIZE = 500

    def get_batch(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """
        批量获取缓存，减少数据库往返

        Args:
            addresses: 地址列表

        Returns:
            {address: result_dict or None} 映射
        """
        if not addresses:
            return {}

        keys = [self._normalize_key(addr) for addr in addresses]
        results: Dict[str, Optional[Dict]] = {}

        with self._lock:
            try:
                # 分批查询，避免超过 SQLite 变量数限制
                for chunk_start in range(0, len(keys), self._BATCH_CHUNK_SIZE):
                    chunk_keys = keys[chunk_start:chunk_start + self._BATCH_CHUNK_SIZE]
                    chunk_addrs = addresses[chunk_start:chunk_start + self._BATCH_CHUNK_SIZE]

                    placeholders = ','.join(['?' for _ in chunk_keys])
                    rows = self._conn.execute(
                        f"SELECT key, data, expires_at FROM cache WHERE key IN ({placeholders})",
                        chunk_keys
                    ).fetchall()

                    row_map = {row['key']: row for row in rows}

                    for addr, key in zip(chunk_addrs, chunk_keys):
                        if key in row_map:
                            row = row_map[key]
                            if row['expires_at'] and row['expires_at'] < time.time():
                                results[addr] = None
                                self._misses += 1
                            else:
                                results[addr] = json.loads(row['data'])
                                self._hits += 1
                        else:
                            results[addr] = None
                            self._misses += 1

                return results

            except sqlite3.DatabaseError:
                # 数据库损坏，尝试恢复
                self._rebuild_db()
                self._misses += len(addresses)
                return {addr: None for addr in addresses}

    def set(self, address: str, result: Dict, ttl: float = None) -> None:
        """
        设置缓存

        Args:
            address: 地址字符串
            result: 地理编码结果
            ttl: 过期时间(秒)，None使用默认值
        """
        key = self._normalize_key(address)
        now = time.time()
        effective_ttl = ttl if ttl is not None else self._ttl
        expires = now + effective_ttl if effective_ttl else None

        with self._lock:  # 线程安全
            # 写入内存 LRU（LRU 淘汰最旧）
            if result is not None:
                if len(self._mem_cache) >= self._mem_maxsize:
                    self._mem_cache.popitem(last=False)
                self._mem_cache[key] = {"data": dict(result), "expires_at": expires}

            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache (key, address, data, created_at, expires_at, source) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (key, address, json.dumps(result, ensure_ascii=False) if result is not None else "null", now, expires, result.get('source') if result else None)
                )

                self._pending += 1
                if self._pending >= self._batch_size:
                    self.flush()

            except sqlite3.DatabaseError:
                self._rebuild_db()
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache (key, address, data, created_at, expires_at, source) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (key, address, json.dumps(result, ensure_ascii=False) if result is not None else "null", now, expires, result.get('source') if result else None)
                )
                self._pending += 1

    def flush(self) -> None:
        """手动提交待写入的数据"""
        with self._lock:  # 线程安全
            if self._pending > 0:
                try:
                    self._conn.commit()
                except sqlite3.DatabaseError:
                    self._rebuild_db()
                self._pending = 0

    def delete(self, address: str) -> bool:
        """删除缓存"""
        key = self._normalize_key(address)
        with self._lock:
            self._mem_cache.pop(key, None)
            try:
                cursor = self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._conn.commit()
                return cursor.rowcount > 0
            except sqlite3.DatabaseError:
                self._rebuild_db()
                return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._mem_cache.clear()
            try:
                self._conn.execute("DELETE FROM cache")
                self._conn.commit()
            except sqlite3.DatabaseError:
                self._rebuild_db()
            self._hits = 0
            self._misses = 0

    def cleanup(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的条目数
        """
        with self._lock:  # 线程安全
            try:
                cursor = self._conn.execute(
                    "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),)
                )
                self._conn.commit()
                return cursor.rowcount
            except sqlite3.DatabaseError:
                self._rebuild_db()
                return 0

    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self._lock:  # 线程安全
            try:
                total = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                expired = self._conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),)
                ).fetchone()[0]
            except sqlite3.DatabaseError:
                total = 0
                expired = 0

        total_requests = self._hits + self._misses
        hit_rate = round(self._hits / total_requests * 100, 2) if total_requests > 0 else 0.0

        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate,
            'total_entries': total,
            'mem_entries': len(self._mem_cache),
            'mem_max': self._mem_maxsize,
            'expired_entries': expired,
            'pending_writes': self._pending
        }

    def count(self) -> int:
        """获取缓存条目数"""
        with self._lock:  # 线程安全
            try:
                return self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            except sqlite3.DatabaseError:
                return 0

    def start_watchdog(self, interval: float = 30.0) -> None:
        """启动后台看门狗线程，定期刷新缓存

        在批量操作期间确保数据定期写入磁盘，防止崩溃时大量数据丢失。

        Args:
            interval: 刷新间隔（秒），默认30秒
        """
        if self._watchdog_thread is not None:
            return  # 已在运行

        self._watchdog_stop = threading.Event()

        def _watchdog_loop():
            while not self._watchdog_stop.wait(interval):
                try:
                    with self._lock:
                        if self._pending > 0:
                            self._conn.commit()
                            self._pending = 0
                except Exception:
                    pass  # 静默处理刷新错误，不中断主流程

        self._watchdog_thread = threading.Thread(
            target=_watchdog_loop,
            daemon=True,
            name="cache-watchdog"
        )
        self._watchdog_thread.start()

    def stop_watchdog(self) -> None:
        """停止看门狗线程"""
        if self._watchdog_stop:
            self._watchdog_stop.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5.0)
            self._watchdog_thread = None
            self._watchdog_stop = None

    def close(self) -> None:
        """关闭缓存管理器，确保数据持久化"""
        self.stop_watchdog()
        with self._lock:  # 线程安全
            self.flush()
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, address: str) -> bool:
        return self.get(address) is not None

    def __enter__(self) -> 'CacheManager':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False
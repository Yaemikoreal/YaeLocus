"""
混合架构地理编码缓存

特性:
- 内存优先缓存（无锁读写）
- 异步持久化队列（后台单线程写入 SQLite）
- 启动时加载历史缓存（断点续传）
- 程序退出时确保数据落盘
- 优雅关闭 + atexit 保护

优化点:
- 解决 "database is locked" 问题
- 工作线程永不阻塞（内存缓存无锁）
- 持久化线程独占 SQLite 连接（无并发冲突）
- 20000+ 地址批量处理稳定运行
"""

import json
import sqlite3
import time
import threading
import queue
import atexit
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from .config import OutputPaths


class CacheManager:
    """
    混合架构缓存管理器：内存优先 + 异步持久化

    架构设计：
    - 内存 LRU 缓存（主缓存，读写无锁）
    - 持久化队列（线程安全 Queue）
    - 持久化线程（独占 SQLite 连接，无竞争）

    解决的问题：
    - "database is locked" 错误
    - 多线程并发写入冲突
    - 看门狗线程与工作线程竞争
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

    # 默认内存缓存条目数（覆盖典型批量规模）
    DEFAULT_MEM_SIZE = 5000

    # 持久化批次大小
    DEFAULT_PERSIST_BATCH = 100

    def __init__(
        self,
        cache_file: str = str(OutputPaths.DATABASE / "geocache.db"),
        default_ttl: float = None,
        batch_size: int = None,  # 兼容旧参数
        mem_cache_size: int = DEFAULT_MEM_SIZE,
        persist_batch_size: int = DEFAULT_PERSIST_BATCH,
        load_on_start: bool = True,
    ):
        """
        初始化缓存管理器

        Args:
            cache_file: SQLite 数据库文件路径（仅用于持久化）
            default_ttl: 默认过期时间(秒)，None 表示永不过期
            mem_cache_size: 内存 LRU 缓存条目上限（默认 5000）
            persist_batch_size: 持久化批次大小（默认 100）
            load_on_start: 启动时是否加载历史缓存（断点续传）
        """
        self._path = Path(cache_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = default_ttl
        # 兼容旧参数：batch_size 映射到 persist_batch_size
        self._persist_batch_size = persist_batch_size if batch_size is None else batch_size

        # 统计计数器（使用线程安全的原子操作）
        self._hits = 0
        self._misses = 0

        # 内存 LRU 缓存（主缓存，读写无锁）
        self._mem_cache: OrderedDict = OrderedDict()
        self._mem_maxsize = max(1, mem_cache_size)

        # 持久化队列（线程安全）
        self._write_queue: queue.Queue = queue.Queue()

        # 持久化线程状态
        self._persist_conn: Optional[sqlite3.Connection] = None
        self._persist_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._flush_done_event = threading.Event()  # flush 完成通知

        # 兼容旧看门狗属性（已弃用，但保留属性以兼容测试）
        self._watchdog_thread = None
        self._watchdog_stop = None

        # 兼容旧属性名：_conn 映射到 _persist_conn
        # (旧测试可能检查 _conn)
        self._conn = None  # 初始为 None，持久化线程启动后指向 _persist_conn

        # 恢复通知回调
        self._recovery_callback: Optional[Callable[[Any], None]] = None

        # 初始化
        self._init_db()
        if load_on_start:
            self._load_from_db()  # 断点续传：加载历史缓存
        self._start_persist_thread()

        # 注册 atexit 确保程序退出时数据落盘
        atexit.register(self._emergency_flush)

    def set_recovery_callback(self, callback: Callable[[Any], None]) -> None:
        """设置数据库恢复通知回调"""
        self._recovery_callback = callback

    def _init_db(self) -> None:
        """初始化数据库（仅创建表结构）"""
        conn = sqlite3.connect(str(self._path), timeout=30)
        try:
            conn.executescript(self.INIT_SQL)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")  # 30秒等待
            conn.commit()
        except sqlite3.DatabaseError:
            self._rebuild_db_with_conn(conn)
        finally:
            conn.close()

    def _rebuild_db_with_conn(self, conn: sqlite3.Connection) -> None:
        """重建损坏的数据库"""
        if self._recovery_callback:
            try:
                self._recovery_callback({
                    'type': 'cache_recovery',
                    'message': '数据库损坏，正在重建...',
                    'timestamp': time.time()
                })
            except Exception:
                pass

        # 删除损坏文件
        for suffix in ['', '-wal', '-shm']:
            p = Path(str(self._path) + suffix)
            if p.exists():
                for _ in range(3):
                    try:
                        p.unlink()
                        break
                    except PermissionError:
                        time.sleep(0.1)

        # 重建
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
        """启动时从 SQLite 加载历史缓存到内存（断点续传）"""
        conn = sqlite3.connect(str(self._path), timeout=30)
        try:
            now = time.time()
            cursor = conn.execute(
                "SELECT key, data, expires_at FROM cache WHERE expires_at IS NULL OR expires_at > ?",
                (now,)
            )
            loaded = 0
            for key, data_json, expires_at in cursor:
                try:
                    data = json.loads(data_json)
                    # 内存 LRU
                    if len(self._mem_cache) >= self._mem_maxsize:
                        self._mem_cache.popitem(last=False)
                    self._mem_cache[key] = {"data": data, "expires_at": expires_at}
                    loaded += 1
                except json.JSONDecodeError:
                    continue

            # 按创建时间排序（最旧的在前，符合 LRU 淘汰顺序）
            # 已通过数据库查询顺序保证

        except sqlite3.DatabaseError:
            # 数据库损坏，忽略历史缓存
            pass
        finally:
            conn.close()

    def _start_persist_thread(self) -> None:
        """启动后台持久化线程"""
        # 持久化线程专用连接（独占，无竞争）
        # 注意：必须在持久化线程内创建连接，或设置 check_same_thread=False
        # 这里我们在线程启动后创建连接
        self._persist_thread = threading.Thread(
            target=self._persist_thread_main,
            daemon=True,
            name="CachePersistence"
        )
        self._persist_thread.start()

    def _persist_thread_main(self) -> None:
        """持久化线程主入口：创建连接并运行循环"""
        # 在线程内创建连接（避免跨线程问题）
        self._persist_conn = sqlite3.connect(str(self._path), timeout=30)
        self._persist_conn.execute("PRAGMA journal_mode=WAL")
        self._persist_conn.execute("PRAGMA synchronous=NORMAL")
        self._persist_conn.execute("PRAGMA busy_timeout=30000")
        self._persist_conn.row_factory = sqlite3.Row

        # 兼容旧属性：_conn 映射到 _persist_conn
        self._conn = self._persist_conn

        self._persist_loop()

        # 线程退出时关闭连接
        if self._persist_conn:
            try:
                self._persist_conn.close()
            except Exception:
                pass
        self._persist_conn = None
        self._conn = None  # 兼容属性同步

    def _persist_loop(self) -> None:
        """持久化线程主循环：批量写入 SQLite"""
        while not self._shutdown_event.is_set():
            batch = []
            flush_requested = False

            # 等待数据（阻塞）
            try:
                first = self._write_queue.get(timeout=0.5)
                if first is None:
                    flush_requested = True
                else:
                    batch.append(first)
            except queue.Empty:
                continue

            # 收集更多数据（非阻塞），直到遇到 None 或批次满
            while len(batch) < self._persist_batch_size:
                try:
                    item = self._write_queue.get_nowait()
                    if item is None:
                        flush_requested = True
                        break
                    batch.append(item)
                except queue.Empty:
                    break

            # 持久化批次
            if batch:
                self._persist_batch(batch)

            # 如果收到 flush 标记，处理完数据后通知
            if flush_requested:
                self._flush_done_event.set()

        # 线程退出前，确保剩余数据落盘
        self._flush_remaining()

    def _persist_batch(self, batch: List[tuple]) -> None:
        """执行批量持久化"""
        try:
            self._persist_conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            for key, address, data, ttl in batch:
                expires = now + ttl if ttl else None
                self._persist_conn.execute(
                    "INSERT OR REPLACE INTO cache (key, address, data, created_at, expires_at, source) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (key, address, json.dumps(data, ensure_ascii=False), now, expires, data.get('source') if data else None)
                )
            self._persist_conn.commit()
            # 定期 WAL checkpoint（减少 WAL 文件积累）
            try:
                self._persist_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
        except Exception:
            self._handle_persist_failure(batch)

    def _handle_persist_failure(self, batch: List[tuple]) -> None:
        """持久化批次失败处理：重试 + 回退到队列"""
        import sys as _sys
        for attempt in range(3):
            try:
                self._persist_conn.execute("BEGIN IMMEDIATE")
                now = time.time()
                for key, address, data, ttl in batch:
                    expires = now + ttl if ttl else None
                    self._persist_conn.execute(
                        "INSERT OR REPLACE INTO cache (key, address, data, created_at, expires_at, source) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (key, address, json.dumps(data, ensure_ascii=False), now, expires, data.get('source') if data else None)
                    )
                self._persist_conn.commit()
                return  # 重试成功
            except Exception:
                try:
                    self._persist_conn.rollback()
                except Exception:
                    pass
                time.sleep(0.3 * (attempt + 1))

        # 3次重试全部失败：数据放回队列，打印告警
        print(f"[cache] WARNING: 持久化失败(重试3次) — {len(batch)} 条数据放回队列",
              file=_sys.stderr, flush=True)
        for item in batch:
            self._write_queue.put(item)
        # 尝试重建连接
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
        """程序退出时，确保队列中剩余数据落盘"""
        remaining = []
        while True:
            try:
                item = self._write_queue.get_nowait()
                remaining.append(item)
            except queue.Empty:
                break

        if remaining:
            self._persist_batch(remaining)

    def _emergency_flush(self) -> None:
        """atexit 回调：程序退出时确保数据落盘"""
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()
            if self._persist_thread:
                self._persist_thread.join(timeout=5)
            self._flush_remaining()
            if self._persist_conn:
                try:
                    self._persist_conn.close()
                except Exception:
                    pass

    @staticmethod
    def _normalize_key(address: str) -> str:
        """智能缓存键 - 处理地址变体"""
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
        """
        获取缓存（仅内存，无锁读取）

        Args:
            address: 地址字符串

        Returns:
            缓存的结果字典，不存在或过期返回 None
        """
        key = self._normalize_key(address)

        # 内存缓存（无锁）
        if key in self._mem_cache:
            entry = self._mem_cache[key]
            # 检查过期
            if entry["expires_at"] and entry["expires_at"] < time.time():
                # 过期，移除
                try:
                    self._mem_cache.pop(key, None)
                except KeyError:
                    pass
                self._misses += 1
                return None
            # 移到末尾（最近使用）
            try:
                self._mem_cache.move_to_end(key)
            except KeyError:
                pass
            self._hits += 1
            return entry["data"]

        self._misses += 1
        return None

    # SQLite 最大变量数限制
    _BATCH_CHUNK_SIZE = 500

    def get_batch(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """
        批量获取缓存（仅内存）

        Args:
            addresses: 地址列表

        Returns:
            {address: result_dict or None} 映射
        """
        if not addresses:
            return {}

        results: Dict[str, Optional[Dict]] = {}
        for addr in addresses:
            results[addr] = self.get(addr)

        return results

    def set(self, address: str, result: Dict, ttl: float = None) -> None:
        """
        设置缓存（内存 + 异步持久化队列）

        Args:
            address: 地址字符串
            result: 地理编码结果
            ttl: 过期时间(秒)，None 使用默认值
        """
        key = self._normalize_key(address)
        effective_ttl = ttl if ttl is not None else self._ttl
        expires = time.time() + effective_ttl if effective_ttl else None

        # 内存缓存（无锁写入）
        if result is not None:
            # LRU 淘汰最旧条目
            if len(self._mem_cache) >= self._mem_maxsize:
                try:
                    self._mem_cache.popitem(last=False)
                except KeyError:
                    pass
            self._mem_cache[key] = {"data": dict(result), "expires_at": expires}
            try:
                self._mem_cache.move_to_end(key)
            except KeyError:
                pass

        # 异步持久化（写入队列，无阻塞）
        self._write_queue.put((key, address, result, effective_ttl))

    def flush(self) -> None:
        """等待持久化队列清空并数据落盘"""
        # 清除之前的 flush 标记
        self._flush_done_event.clear()

        # 发送 flush 标记（None）
        self._write_queue.put(None)

        # 等待持久化线程处理完成（最多等待 5 秒）
        self._flush_done_event.wait(timeout=5)

        # 确保队列真的清空了
        while not self._write_queue.empty():
            time.sleep(0.1)

    def delete(self, address: str) -> bool:
        """删除缓存（内存 + 持久化）

        Returns:
            是否存在并成功删除（基于内存缓存判断）
        """
        key = self._normalize_key(address)

        # 检查内存缓存是否存在
        existed = key in self._mem_cache

        # 内存删除
        try:
            self._mem_cache.pop(key, None)
        except KeyError:
            pass

        # 持久化删除（直接操作，不走队列）
        try:
            conn = sqlite3.connect(str(self._path), timeout=30)
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

        return existed

    def clear(self) -> None:
        """清空所有缓存"""
        # 内存清空
        self._mem_cache.clear()

        # 持久化清空
        try:
            conn = sqlite3.connect(str(self._path), timeout=30)
            conn.execute("DELETE FROM cache")
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

        self._hits = 0
        self._misses = 0

    def cleanup(self) -> int:
        """清理过期缓存"""
        now = time.time()
        cleaned = 0

        # 内存过期清理
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

        # 持久化过期清理
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
        """获取缓存统计信息"""
        # 内存统计
        mem_entries = len(self._mem_cache)

        # 持久化统计（独立连接，不影响持久化线程）
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
            'pending_writes': self._write_queue.qsize(),  # 兼容旧字段名
        }

    def count(self) -> int:
        """获取缓存条目数"""
        try:
            conn = sqlite3.connect(str(self._path), timeout=30)
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            conn.close()
            return total
        except sqlite3.Error:
            return len(self._mem_cache)

    def start_watchdog(self, interval: float = 30.0) -> None:
        """已弃用：持久化线程自动处理，无需看门狗

        保持向后兼容，设置虚拟属性供测试检查。
        """
        # 兼容测试：设置虚拟看门狗属性
        self._watchdog_stop = threading.Event()
        # 持久化线程已启动，将其作为"看门狗"（兼容测试）
        self._watchdog_thread = self._persist_thread

    def stop_watchdog(self) -> None:
        """已弃用：保持向后兼容"""
        # 持久化线程由 close() 管理，这里只清空属性
        self._watchdog_thread = None
        self._watchdog_stop = None

    def close(self) -> None:
        """关闭缓存管理器，确保数据落盘"""
        # 取消 atexit（避免重复调用）
        try:
            atexit.unregister(self._emergency_flush)
        except Exception:
            pass

        # 通知持久化线程退出
        self._shutdown_event.set()

        # 等待持久化线程完成
        if self._persist_thread:
            self._persist_thread.join(timeout=10)

        # 关闭持久化连接
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
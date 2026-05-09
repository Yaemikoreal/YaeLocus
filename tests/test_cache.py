"""缓存模块测试"""
import json
import time
import threading

import pytest

from geocode.cache import CacheManager


class TestCacheBasic:
    """基本 CRUD 操作"""

    def test_set_and_get(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            result = {"success": True, "latitude": 39.9, "longitude": 116.4}
            cache.set("北京市朝阳区", result)
            cached = cache.get("北京市朝阳区")
            assert cached is not None
            assert cached["latitude"] == 39.9
            assert cached["longitude"] == 116.4
        finally:
            cache.close()

    def test_get_missing(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            assert cache.get("不存在的地址") is None
        finally:
            cache.close()

    def test_update_existing(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            cache.set("上海市浦东新区", {"success": True, "latitude": 31.23})
            cache.set("上海市浦东新区", {"success": True, "latitude": 31.24})
            cached = cache.get("上海市浦东新区")
            assert cached["latitude"] == 31.24
        finally:
            cache.close()

    def test_delete(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            cache.set("广州市天河区", {"success": True})
            assert cache.delete("广州市天河区") is True
            assert cache.get("广州市天河区") is None
            assert cache.delete("不存在的") is False
        finally:
            cache.close()


class TestCacheKeyNormalization:
    """键规范化测试"""

    def test_case_insensitive(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            cache.set("北京市朝阳区", {"val": 1})
            assert cache.get("北京市朝阳区") is not None
            assert cache.get("  北京市朝阳区  ") is not None
        finally:
            cache.close()

    def test_case_insensitive_english(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            cache.set("Beijing Chaoyang", {"val": 1})
            assert cache.get("beijing chaoyang") is not None
            assert cache.get("  Beijing Chaoyang  ") is not None
        finally:
            cache.close()


class TestCacheBatch:
    """批量操作测试"""

    def test_get_batch(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=10)
        try:
            cache.set("地址A", {"val": 1})
            cache.set("地址B", {"val": 2})
            cache.set("地址C", {"val": 3})
            cache.flush()
            results = cache.get_batch(["地址A", "地址B", "地址D"])
            assert results["地址A"]["val"] == 1
            assert results["地址B"]["val"] == 2
            assert results["地址D"] is None
        finally:
            cache.close()

    def test_get_batch_empty(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            results = cache.get_batch([])
            assert results == {}
        finally:
            cache.close()


class TestCacheTTL:
    """TTL 过期测试"""

    def test_expired_entry(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=1)
        try:
            cache.set("过期地址", {"val": 1}, ttl=0.001)  # 1ms TTL
            cache.flush()
            time.sleep(0.05)
            assert cache.get("过期地址") is None
        finally:
            cache.close()

    def test_cleanup_expired(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=1)
        try:
            cache.set("过期1", {"val": 1}, ttl=0.001)
            cache.set("过期2", {"val": 2}, ttl=0.001)
            cache.set("永久", {"val": 3})  # 永不过期
            cache.flush()
            time.sleep(0.05)
            cleaned = cache.cleanup()
            assert cleaned >= 2
            assert cache.get("永久") is not None
        finally:
            cache.close()


class TestCacheThreadSafety:
    """线程安全测试"""

    def test_concurrent_writes(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=10)
        errors = []

        def writer(start_id, count):
            for i in range(count):
                try:
                    cache.set(f"thread_addr_{start_id}_{i}", {"id": start_id, "idx": i})
                except Exception as e:
                    errors.append(e)

        threads = []
        for t_id in range(4):
            t = threading.Thread(target=writer, args=(t_id, 25))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        cache.flush()
        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        assert cache.count() == 100
        cache.close()

    def test_concurrent_read_write(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=5)
        try:
            cache.set("shared_addr", {"val": 0})
            cache.flush()
            errors = []

            def worker():
                for i in range(20):
                    try:
                        val = cache.get("shared_addr")
                        if val:
                            val["val"] = val.get("val", 0) + 1
                            cache.set("shared_addr", val)
                    except Exception as e:
                        errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            cache.flush()

            assert len(errors) == 0
            cached = cache.get("shared_addr")
            assert cached is not None
        finally:
            cache.close()


class TestCacheStats:
    """统计信息测试"""

    def test_stats(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=1)
        try:
            cache.set("地址1", {"val": 1})
            cache.set("地址2", {"val": 2})
            cache.flush()
            stats = cache.get_stats()
            assert stats["total_entries"] == 2
            assert stats["pending_writes"] == 0
        finally:
            cache.close()


class TestCacheClear:
    """清空测试"""

    def test_clear(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=1)
        try:
            cache.set("A", {"val": 1})
            cache.set("B", {"val": 2})
            cache.flush()
            assert cache.count() == 2
            cache.clear()
            assert cache.count() == 0
        finally:
            cache.close()


class TestCacheWatchdog:
    """看门狗定时刷新测试"""

    def test_watchdog_flushes(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file), batch_size=100)
        try:
            cache.start_watchdog(interval=0.5)
            cache.set("看门狗测试", {"val": 1})
            # 应被看门狗自动刷新
            time.sleep(1.0)
            # 创建一个新连接读取（验证数据已持久化）
            from geocode.cache import CacheManager as CM
            cache2 = CM(str(temp_cache_file))
            try:
                cached = cache2.get("看门狗测试")
                assert cached is not None
                assert cached["val"] == 1
            finally:
                cache2.close()
        finally:
            cache.close()

    def test_watchdog_stop(self, temp_cache_file):
        cache = CacheManager(str(temp_cache_file))
        try:
            cache.start_watchdog(interval=0.5)
            assert cache._watchdog_thread is not None
            assert cache._watchdog_thread.is_alive()
            cache.stop_watchdog()
            # 停止后线程对象被置为 None
            assert cache._watchdog_thread is None
            assert cache._watchdog_stop is None
        finally:
            cache.close()
            # Windows: 手动清理数据库文件以释放临时目录
            import time as _time
            _time.sleep(0.1)
            for suffix in ["", "-wal", "-shm"]:
                p = str(temp_cache_file) + suffix
                from pathlib import Path as _Path
                _Path(p).unlink(missing_ok=True)


class TestCachePersistence:
    """持久化测试"""

    def test_data_survives_reopen(self, temp_cache_file):
        cache1 = CacheManager(str(temp_cache_file))
        cache1.set("持久化测试", {"val": 42})
        cache1.close()

        cache2 = CacheManager(str(temp_cache_file))
        try:
            result = cache2.get("持久化测试")
            assert result is not None
            assert result["val"] == 42
        finally:
            cache2.close()

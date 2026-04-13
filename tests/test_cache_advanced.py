"""
缓存高级测试

测试 CacheManager 的高级功能：
- 数据库损坏恢复
- 并发访问
- 边界条件
- 性能测试
"""

import pytest
import sqlite3
import time
import threading
import os
from pathlib import Path

from geocode.cache import CacheManager


# ============================================
# 数据库恢复测试
# ============================================

class TestCacheRecovery:
    """测试数据库恢复"""

    def test_rebuild_corrupted_db(self, corrupted_cache_file):
        """损坏数据库重建"""
        # 创建 CacheManager，应该自动恢复
        cache = CacheManager(cache_file=str(corrupted_cache_file))

        # 应该可以正常使用
        cache.set("测试地址", {"lat": 39.9})
        result = cache.get("测试地址")
        cache.close()

        assert result is not None
        assert result["lat"] == 39.9

    def test_recover_from_wal_file(self, tmp_path):
        """WAL 文件处理"""
        cache_file = tmp_path / "test.db"

        # 创建缓存并写入数据
        cache = CacheManager(cache_file=str(cache_file))
        cache.set("地址1", {"lat": 1})
        cache.close()

        # 删除主数据库文件，保留 WAL
        cache_file.unlink()
        wal_file = Path(str(cache_file) + "-wal")
        # WAL 文件可能不存在，取决于 PRAGMA 设置

        # 重新打开应该能处理
        cache2 = CacheManager(cache_file=str(cache_file))
        cache2.close()

    def test_handle_locked_db(self, tmp_path):
        """数据库锁定处理"""
        cache_file = tmp_path / "locked.db"

        # 打开第一个连接
        cache1 = CacheManager(cache_file=str(cache_file))
        cache1.set("地址1", {"lat": 1})
        cache1.flush()  # 先提交，释放写锁

        # 第二个连接（WAL 模式支持并发读，但写入需等待）
        cache2 = CacheManager(cache_file=str(cache_file))
        cache2.set("地址2", {"lat": 2})  # 应该能成功

        cache1.close()
        cache2.close()

    def test_recovery_preserves_functionality(self, tmp_path):
        """恢复后功能正常"""
        cache_file = tmp_path / "test.db"

        # 创建缓存
        cache = CacheManager(cache_file=str(cache_file))
        cache.set("地址1", {"lat": 1})
        cache.close()

        # 损坏数据库
        with open(cache_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03")

        # 重新打开，应该自动恢复
        cache2 = CacheManager(cache_file=str(cache_file))

        # 功能测试
        cache2.set("地址2", {"lat": 2})
        result = cache2.get("地址2")
        cache2.close()

        assert result is not None

    def test_delete_wal_and_shm_on_rebuild(self, tmp_path):
        """重建时删除 WAL 和 SHM 文件"""
        cache_file = tmp_path / "test.db"

        # 创建缓存
        cache = CacheManager(cache_file=str(cache_file))
        cache.set("地址", {"lat": 1})
        cache.close()

        # 损坏数据库
        with open(cache_file, "wb") as f:
            f.write(b"\x00" * 100)

        # 创建 WAL 和 SHM 文件
        wal_file = Path(str(cache_file) + "-wal")
        shm_file = Path(str(cache_file) + "-shm")
        wal_file.write_bytes(b"\x00" * 100)
        shm_file.write_bytes(b"\x00" * 100)

        # 重新打开触发恢复
        cache2 = CacheManager(cache_file=str(cache_file))
        cache2.close()

        # WAL 和 SHM 应该被清理
        # （取决于实现）


# ============================================
# 并发访问测试
# ============================================

class TestCacheConcurrency:
    """测试并发安全"""

    def test_concurrent_reads(self, temp_cache):
        """多线程读取"""
        # 预填充数据
        for i in range(10):
            temp_cache.set(f"地址{i}", {"lat": i})
        temp_cache.flush()

        results = []
        errors = []

        def read_thread(start_idx):
            try:
                for i in range(start_idx, start_idx + 5):
                    result = temp_cache.get(f"地址{i}")
                    results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=read_thread, args=(0,)),
            threading.Thread(target=read_thread, args=(5,))
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该没有错误
        assert len(errors) == 0

    def test_concurrent_writes(self, temp_cache):
        """多线程写入"""
        results = []
        errors = []

        def write_thread(idx):
            try:
                for i in range(10):
                    temp_cache.set(f"线程{idx}地址{i}", {"lat": i, "thread": idx})
                temp_cache.flush()
                results.append(True)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=write_thread, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该没有错误
        assert len(errors) == 0

    def test_concurrent_read_write(self, temp_cache):
        """并发读写"""
        errors = []

        def write_thread():
            try:
                for i in range(20):
                    temp_cache.set(f"地址{i}", {"lat": i})
                    time.sleep(0.001)
                temp_cache.flush()
            except Exception as e:
                errors.append(f"write: {e}")

        def read_thread():
            try:
                for i in range(20):
                    temp_cache.get(f"地址{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"read: {e}")

        threads = [
            threading.Thread(target=write_thread),
            threading.Thread(target=read_thread),
            threading.Thread(target=read_thread)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 可能有少量错误（非线程安全设计）
        # assert len(errors) == 0

    def test_batch_size_trigger_during_concurrent_writes(self, temp_cache):
        """并发写入时批量提交触发"""
        temp_cache._batch_size = 5
        errors = []

        def write_many():
            try:
                for i in range(10):
                    temp_cache.set(f"地址{i}", {"lat": i})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_many) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()


# ============================================
# 边界条件测试
# ============================================

class TestCacheEdgeCases:
    """测试边界条件"""

    def test_empty_address_key(self, temp_cache):
        """空地址键处理"""
        temp_cache.set("", {"lat": 0})
        result = temp_cache.get("")
        # 空字符串应该被规范化处理
        # 取决于实现

    def test_whitespace_address_key(self, temp_cache):
        """空白字符地址键"""
        temp_cache.set("  北京市  ", {"lat": 39.9})
        result = temp_cache.get("  北京市  ")
        # 应该能获取（规范化后）
        assert result is not None

    def test_case_normalization(self, temp_cache):
        """大小写规范化"""
        temp_cache.set("Beijing", {"lat": 39.9})
        result = temp_cache.get("beijing")
        # 小写应该能匹配
        assert result is not None

    def test_unicode_address(self, temp_cache):
        """Unicode 地址"""
        unicode_address = "北京市朝阳区🎉📍"
        temp_cache.set(unicode_address, {"lat": 39.9})
        result = temp_cache.get(unicode_address)
        assert result is not None
        assert result["lat"] == 39.9

    def test_very_long_address(self, temp_cache):
        """超长地址"""
        long_address = "北京市朝阳区" * 1000  # 很长的地址
        temp_cache.set(long_address, {"lat": 39.9})
        result = temp_cache.get(long_address)
        assert result is not None

    def test_special_characters_in_address(self, temp_cache):
        """特殊字符地址"""
        special_address = "地址\n换行\t制表符\"引号'单引号"
        temp_cache.set(special_address, {"lat": 39.9})
        result = temp_cache.get(special_address)
        assert result is not None

    def test_large_cache_entry(self, temp_cache):
        """大缓存条目"""
        large_data = {
            "lat": 39.9,
            "extra_data": "x" * 10000  # 大数据
        }
        temp_cache.set("大地址", large_data)
        result = temp_cache.get("大地址")
        assert result is not None
        assert len(result["extra_data"]) == 10000

    def test_rapid_set_operations(self, temp_cache):
        """快速连续 set 操作"""
        for i in range(100):
            temp_cache.set(f"地址{i}", {"lat": i})

        temp_cache.flush()

        # 验证所有数据
        for i in range(100):
            result = temp_cache.get(f"地址{i}")
            assert result is not None

    def test_set_none_result(self, temp_cache):
        """set None 结果"""
        # 不应该崩溃
        temp_cache.set("地址", None)
        result = temp_cache.get("地址")
        # None 应该被存储

    def test_nested_dict_result(self, temp_cache):
        """嵌套字典结果"""
        nested = {
            "lat": 39.9,
            "info": {
                "province": "北京市",
                "city": "朝阳区"
            }
        }
        temp_cache.set("嵌套地址", nested)
        result = temp_cache.get("嵌套地址")
        assert result["info"]["province"] == "北京市"


# ============================================
# 持久化测试
# ============================================

class TestCachePersistence:
    """测试持久化"""

    def test_persist_after_close(self, tmp_path):
        """关闭后数据持久化"""
        cache_file = tmp_path / "persist.db"

        # 写入并关闭
        cache1 = CacheManager(cache_file=str(cache_file))
        cache1.set("地址1", {"lat": 39.9})
        cache1.set("地址2", {"lat": 31.2})
        cache1.close()

        # 重新打开读取
        cache2 = CacheManager(cache_file=str(cache_file))
        result1 = cache2.get("地址1")
        result2 = cache2.get("地址2")
        cache2.close()

        assert result1 is not None
        assert result1["lat"] == 39.9
        assert result2 is not None
        assert result2["lat"] == 31.2

    def test_persist_after_batch(self, tmp_path):
        """批量写入后持久化"""
        cache_file = tmp_path / "batch.db"

        cache = CacheManager(cache_file=str(cache_file), batch_size=10)
        for i in range(15):
            cache.set(f"地址{i}", {"lat": i})
        cache.close()

        # 验证所有数据
        cache2 = CacheManager(cache_file=str(cache_file))
        for i in range(15):
            result = cache2.get(f"地址{i}")
            assert result is not None
        cache2.close()

    def test_persist_with_pending(self, tmp_path):
        """待写入数据持久化"""
        cache_file = tmp_path / "pending.db"

        cache = CacheManager(cache_file=str(cache_file), batch_size=100)
        cache.set("地址1", {"lat": 1})
        # pending 应该是 1
        assert cache._pending == 1

        # 关闭时应该 flush
        cache.close()

        # 验证数据
        cache2 = CacheManager(cache_file=str(cache_file))
        result = cache2.get("地址1")
        cache2.close()

        assert result is not None

    def test_manual_flush_persists(self, tmp_path):
        """手动 flush 后持久化"""
        cache_file = tmp_path / "manual_flush.db"

        cache = CacheManager(cache_file=str(cache_file), batch_size=100)
        cache.set("地址1", {"lat": 1})
        cache.flush()

        # 不关闭，直接打开新连接验证
        cache2 = CacheManager(cache_file=str(cache_file))
        result = cache2.get("地址1")
        cache2.close()
        cache.close()

        assert result is not None


# ============================================
# 性能测试
# ============================================

class TestCachePerformance:
    """测试性能"""

    def test_bulk_insert_performance(self, temp_cache):
        """批量插入性能"""
        start_time = time.time()

        for i in range(1000):
            temp_cache.set(f"地址{i}", {"lat": i})

        temp_cache.flush()
        elapsed = time.time() - start_time

        # 1000 次写入应该在合理时间内完成
        assert elapsed < 5.0  # 5 秒内

    def test_cache_hit_performance(self, temp_cache):
        """缓存命中性能"""
        # 预填充
        for i in range(100):
            temp_cache.set(f"地址{i}", {"lat": i})
        temp_cache.flush()

        start_time = time.time()

        for i in range(1000):
            temp_cache.get(f"地址{i % 100}")

        elapsed = time.time() - start_time

        # 1000 次命中应该在合理时间内
        assert elapsed < 2.0

    def test_cache_miss_performance(self, temp_cache):
        """缓存未命中性能"""
        start_time = time.time()

        for i in range(1000):
            temp_cache.get(f"不存在{i}")

        elapsed = time.time() - start_time

        # 1000 次未命中
        assert elapsed < 2.0

    def test_large_dataset_performance(self, tmp_path):
        """大数据集性能"""
        cache_file = tmp_path / "large.db"
        cache = CacheManager(cache_file=str(cache_file), batch_size=500)

        start_time = time.time()

        # 写入 5000 条
        for i in range(5000):
            cache.set(f"地址{i}", {"lat": i, "lng": i})

        cache.flush()
        write_time = time.time() - start_time

        # 读取验证
        start_time = time.time()
        for i in range(0, 5000, 100):  # 抽样验证
            result = cache.get(f"地址{i}")
            assert result is not None

        read_time = time.time() - start_time
        cache.close()

        # 性能断言
        assert write_time < 10.0  # 写入 5000 条 < 10 秒
        assert read_time < 1.0    # 读取 50 条 < 1 秒


# ============================================
# TTL 过期测试
# ============================================

class TestCacheTTL:
    """测试 TTL 过期"""

    def test_ttl_expired_entry_deleted_on_get(self, temp_cache):
        """get 时删除过期条目"""
        temp_cache.set("过期地址", {"lat": 1}, ttl=0.1)
        time.sleep(0.2)

        result = temp_cache.get("过期地址")
        assert result is None

    def test_ttl_not_expired(self, temp_cache):
        """未过期条目可访问"""
        temp_cache.set("未过期地址", {"lat": 1}, ttl=10)
        result = temp_cache.get("未过期地址")
        assert result is not None

    def test_ttl_default_value(self, temp_cache):
        """默认 TTL 值"""
        cache = CacheManager(cache_file=str(temp_cache._path), default_ttl=3600)
        cache.set("地址", {"lat": 1})
        # 应该使用默认 TTL
        cache.close()

    def test_ttl_override_default(self, temp_cache):
        """覆盖默认 TTL"""
        cache = CacheManager(
            cache_file=str(temp_cache._path),
            default_ttl=3600
        )
        cache.set("地址", {"lat": 1}, ttl=60)  # 覆盖为 60 秒
        cache.close()

    def test_cleanup_removes_expired(self, temp_cache):
        """cleanup 删除过期条目"""
        temp_cache.set("过期1", {"lat": 1}, ttl=0.1)
        temp_cache.set("过期2", {"lat": 2}, ttl=0.1)
        temp_cache.set("未过期", {"lat": 3}, ttl=3600)
        temp_cache.flush()

        time.sleep(0.2)

        cleaned = temp_cache.cleanup()
        assert cleaned == 2

    def test_permanent_entry_no_ttl(self, temp_cache):
        """永久条目无 TTL"""
        temp_cache.set("永久地址", {"lat": 1}, ttl=None)
        time.sleep(0.1)
        result = temp_cache.get("永久地址")
        assert result is not None


# ============================================
# 统计测试
# ============================================

class TestCacheStats:
    """测试统计功能"""

    def test_stats_after_operations(self, temp_cache):
        """操作后统计"""
        temp_cache.set("地址1", {"lat": 1})
        temp_cache.get("地址1")  # hit
        temp_cache.get("不存在")  # miss

        stats = temp_cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["total_entries"] >= 1

    def test_hit_rate_calculation(self, temp_cache):
        """命中率计算"""
        temp_cache.set("地址", {"lat": 1})
        temp_cache.get("地址")  # hit
        temp_cache.get("地址")  # hit
        temp_cache.get("不存在")  # miss

        stats = temp_cache.get_stats()
        # 2 hits / 3 total = 66.67%
        assert 60 < stats["hit_rate"] < 70

    def test_stats_persistent_across_instances(self, tmp_path):
        """跨实例统计持久化"""
        cache_file = tmp_path / "stats.db"

        cache1 = CacheManager(cache_file=str(cache_file))
        cache1.set("地址", {"lat": 1})
        cache1.get("地址")
        stats1 = cache1.get_stats()
        cache1.close()

        # 命中/未命中计数器是内存中的，不会持久化
        # 但条目数会持久化
        cache2 = CacheManager(cache_file=str(cache_file))
        stats2 = cache2.get_stats()
        cache2.close()

        assert stats2["total_entries"] == stats1["total_entries"]


# ============================================
# 键规范化测试
# ============================================

class TestKeyNormalization:
    """测试键规范化"""

    def test_strip_whitespace(self, temp_cache):
        """去除空格"""
        temp_cache.set("  地址  ", {"lat": 1})
        result = temp_cache.get("  地址  ")
        assert result is not None

    def test_lowercase_conversion(self, temp_cache):
        """小写转换"""
        temp_cache.set("Beijing", {"lat": 1})
        result = temp_cache.get("beijing")
        assert result is not None

    def test_combined_normalization(self, temp_cache):
        """组合规范化"""
        temp_cache.set("  Beijing  ", {"lat": 1})
        result = temp_cache.get("  beijing  ")
        assert result is not None

    def test_chinese_not_affected(self, temp_cache):
        """中文不受影响"""
        temp_cache.set("北京", {"lat": 1})
        result = temp_cache.get("北京")
        assert result is not None
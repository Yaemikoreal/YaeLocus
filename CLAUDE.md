# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

YaeLocus - 地址转经纬度工具，支持高德/百度/天地图三API轮换，高性能SQLite缓存，Typer/Rich现代化CLI。

**版本**: 1.2.0
**仓库**: https://github.com/Yaemikoreal/YaeLocus

## 运行命令

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式安装（推荐）
pip install -e .

# Windows 一键安装
install.bat

# 配置API密钥（交互式）
geocode-tool config
python -m geocode.cli config

# 运行地理编码
geocode-tool run -i data/清单.xlsx
python -m geocode.cli run -i data/清单.xlsx
python run.py -i data/清单.xlsx

# 单地址转换
geocode-tool geocode "北京市朝阳区"
python -m geocode.cli geocode "天安门" --json

# 缓存管理
geocode-tool cache stats
geocode-tool cache cleanup

# 环境诊断
geocode-tool doctor

# 测试API连通性
geocode-tool test-api

# 运行测试
python -m pytest tests/ -v
python -m pytest tests/test_geocode.py::TestCacheManager -v

# 代码检查
ruff check geocode/
```

## 模块结构

```
geocode/
├── __init__.py    # 模块入口，版本号管理
├── cli.py         # [新增] Typer CLI入口
├── errors.py      # [新增] 异常类定义
├── config.py      # 配置管理（API密钥、优先级）
├── cache.py       # 轻量级SQLite缓存（单类实现）
├── logger.py      # API调用日志
├── geocoder.py    # 核心地理编码类
├── coords.py      # 坐标转换工具
├── models.py      # 数据模型
├── map_visualizer.py  # folium地图生成
├── main.py        # 传统CLI入口
└── __main__.py    # 模块运行入口
```

## 缓存架构

`cache.py` 实现单层SQLite缓存（~180行）：

### CacheManager
- 单类实现，无内存层
- WAL模式 + mmap优化
- 延迟提交（批量写入）
- TTL过期支持
- 数据库损坏自动恢复
- 统计监控（命中率）

### 性能
| 场景 | 性能 |
|------|------|
| 单次写入 | ~0.1ms（延迟提交） |
| 批量写入100条 | ~50ms |
| 单次读取 | ~1ms（mmap） |

## CLI 命令

| 命令 | 说明 |
|------|------|
| `run` | 执行地理编码 |
| `geocode` | 单地址转换（支持 --json 输出） |
| `cache` | 缓存管理（stats/clear/cleanup/export） |
| `config` | 交互式配置API密钥 |
| `doctor` | 环境诊断 |
| `test-api` | 测试API连通性 |

## 核心类

```python
from geocode import Geocoder, CacheManager, APILogger

# 使用上下文管理器（推荐，自动关闭）
with CacheManager("cache.db") as cache:
    geocoder = Geocoder(cache)
    result = geocoder.geocode("北京市朝阳区建国路88号")
    print(result['longitude'], result['latitude'])

# 手动管理
cache = CacheManager(cache_file="cache.db", default_ttl=86400)
logger = APILogger()
geocoder = Geocoder(cache, logger)

# 地理编码
result = geocoder.geocode("地址")

# 缓存统计
stats = geocoder.get_cache_stats()

# 清理过期
geocoder.cleanup_cache()

# 关闭资源（确保缓存持久化）
geocoder.close()
```

## 坐标转换

`coords.py` 提供：
- `gcj02_to_wgs84()` - 高德坐标转WGS-84
- `bd09_to_wgs84()` - 百度坐标转WGS-84
- `bd09_to_gcj02()` - 百度坐标转GCJ-02

## 输出文件

- `output/地址_经纬度_结果.csv` - 转换结果
- `output/地图输出.html` - 交互式地图
- `output/geocache.db` - SQLite缓存数据库
- `output/api调用日志.csv` - API调用记录

## API配额

| API | 免费额度 | 优先级 |
|-----|---------|--------|
| 高德地图 | 5000次/日 | 1 |
| 天地图 | 10000次/日 | 2 |
| 百度地图 | 6000次/日 | 3 |

## 扩展新API

1. 在 `config.py` 添加配置
2. 在 `geocoder.py` 添加 `_geocode_xxx()` 方法
3. 在 `API_PRIORITY` 中添加优先级
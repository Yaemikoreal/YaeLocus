# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

YaeLocus - 地址转经纬度工具，支持高德/百度/天地图三API轮换，高性能SQLite缓存，Typer/Rich现代化CLI。

**版本**: 1.3.0
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

# 多格式输出 (v1.3.0新增)
geocode-tool run -i data/清单.xlsx -f xlsx           # Excel输出
geocode-tool run -i data/清单.xlsx -f geojson        # GeoJSON输出
geocode-tool run -i data/清单.xlsx -o output/result.json -f json  # JSON输出

# 并行处理 (v1.3.0新增)
geocode-tool run -i data/清单.xlsx -w 5              # 5线程并行

# 断点续传 (v1.3.0新增)
geocode-tool run -i data/清单.xlsx --skip-cached     # 跳过已缓存

# 单地址转换
geocode-tool geocode "北京市朝阳区"
python -m geocode.cli geocode "天安门" --json

# 逆地理编码 (v1.3.0新增)
geocode-tool reverse 39.9 116.4
geocode-tool reverse 39.9 116.4 --json

# 坐标转换 (v1.3.0新增)
geocode-tool convert 39.9 116.4 --from gcj02 --to wgs84
geocode-tool convert 39.9 116.4 --from bd09 --to wgs84 --json

# 配额监控 (v1.3.0新增)
geocode-tool quota

# 文件列表 (v1.3.0新增)
geocode-tool files                    # 列出 data/ 目录文件
geocode-tool files --detail           # 显示详细信息（包含地址数量）
geocode-tool files -p output/         # 列出其他目录文件

# 缓存管理
geocode-tool cache stats
geocode-tool cache cleanup

# 环境诊断
geocode-tool doctor

# 测试API连通性
geocode-tool test-api
```

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_geocode.py -v

# 运行单个测试类
python -m pytest tests/test_geocode.py::TestCacheManager -v

# 运行单个测试方法
python -m pytest tests/test_geocode.py::TestCacheManager::test_ttl_expiration -v
```

**测试fixtures**（`tests/conftest.py`）:
- `temp_cache` - 临时缓存管理器
- `temp_logger` - 临时日志记录器
- `mock_config_valid` - Mock有效API密钥配置
- `mock_requests_success` - Mock成功API响应
- `sample_csv/sample_excel` - 测试输入文件

## 模块结构与依赖

```
geocode/
├── __init__.py         # 模块入口，导出核心类
├── cli.py              # Typer CLI（run/geocode/cache/config/doctor/test-api）
├── errors.py           # 异常类（GeocodeError/APIError/FileError/NetworkError）
├── config.py           # API密钥配置（从.env加载）
├── cache.py            # CacheManager（SQLite单类实现）
├── logger.py           # APILogger（CSV日志记录）
├── geocoder.py         # Geocoder（核心逻辑，依赖cache+logger+config+coords）
├── coords.py           # 坐标转换（GCJ-02/BD-09 → WGS-84）
├── models.py           # 数据模型（GeocodeResult/APILog/APIConfig）
├── map_visualizer.py   # folium地图（点聚类+热力图）
├── main.py             # 传统CLI入口
└── __main__.py         # python -m geocode 入口
```

**核心依赖链**: `cli.py` → `Geocoder` → (`CacheManager` + `APILogger` + `Config` + `coords`)

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
| `run` | 执行地理编码（支持 `-f` 多格式输出、`-w` 并行、`--skip-cached` 断点续传） |
| `geocode` | 单地址转换（支持 --json 输出） |
| `reverse` | 逆地理编码：经纬度转地址（v1.3.0新增） |
| `convert` | 坐标系转换工具（v1.3.0新增） |
| `quota` | 查看API配额使用情况（v1.3.0新增） |
| `files` | 列出可处理的输入文件（v1.3.0新增） |
| `cache` | 缓存管理（stats/clear/cleanup/export） |
| `config` | 交互式配置API密钥 |
| `doctor` | 环境诊断 |
| `test-api` | 测试API连通性 |

## 核心类与数据模型

```python
from geocode import Geocoder, CacheManager, APILogger, GeocodeResult

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

**数据模型**（`models.py`）:
- `GeocodeResult` - 地理编码结果（latitude/longitude/formatted_address/source等）
- `APILog` - API调用日志记录
- `APIConfig` - API配置项（name/key/url/daily_limit）

**异常类**（`errors.py`）:
- `NO_API_KEY` - 未配置API密钥
- `FILE_NOT_FOUND` - 输入文件不存在
- `COLUMN_NOT_FOUND` - 地址列不存在
- `API_QUOTA_EXCEEDED` - API配额耗尽

## 坐标转换

`coords.py` 提供：
- `gcj02_to_wgs84()` - 高德坐标转WGS-84
- `bd09_to_wgs84()` - 百度坐标转WGS-84
- `bd09_to_gcj02()` - 百度坐标转GCJ-02
- `wgs84_to_gcj02()` - WGS-84转GCJ-02（逆地理编码需要，v1.3.0新增）

## 输出文件

- `output/地址_经纬度_结果.csv` - 转换结果
- `output/地图输出.html` - 交互式地图
- `output/geocache.db` - SQLite缓存数据库
- `output/api调用日志.csv` - API调用记录

## 配置文件

`.env` 文件存放API密钥，格式：
```
AMAP_KEY=xxx        # 高德地图（32位字符）
BAIDU_AK=xxx        # 百度地图
TIANDITU_TK=xxx     # 天地图
```

**代码检查**：
```bash
ruff check geocode/
ruff check geocode/ --fix
```

## API配额

| API | 免费额度 | 优先级 |
|-----|---------|--------|
| 高德地图 | 5000次/日 | 1 |
| 天地图 | 10000次/日 | 2 |
| 百度地图 | 6000次/日 | 3 |

## 扩展新API

1. 在 `config.py` 添加密钥变量和URL常量
2. 在 `Config.API_PRIORITY` 列表中添加优先级
3. 在 `Config.API_DAILY_LIMITS` 和 `Config.COORDINATE_SYSTEMS` 添加配置
4. 在 `geocoder.py` 添加 `_geocode_xxx()` 方法，返回 `GeocodeResult`
5. 如需坐标转换，在 `coords.py` 添加相应函数
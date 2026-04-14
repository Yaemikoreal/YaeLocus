# YaeLocus - 地址转经纬度工具

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.4.0](https://img.shields.io/badge/version-1.4.0-green.svg)](https://github.com/Yaemikoreal/YaeLocus)
[![PyPI](https://img.shields.io/badge/pypi-yaelocus-blue.svg)](https://pypi.org/project/yaelocus/)

**Author: [Yaemikoreal](https://github.com/Yaemikoreal)**

基于多API混合调用的地理编码工具，支持批量地址转换、高性能缓存、交互式地图可视化。

**项目地址**: https://github.com/Yaemikoreal/YaeLocus

## 功能特性

- **多API轮换**：高德/百度/天地图三API智能轮换，免费额度合计21000次/日
- **现代化CLI**：Typer + Rich 彩色输出，交互式配置向导
- **高性能缓存**：SQLite持久化，断点续传，增量处理
- **坐标转换**：自动转换为WGS-84坐标系
- **交互式地图**：点聚类 + 热力图可视化
- **多格式支持**：CSV、Excel、JSON、GeoJSON 输入输出
- **逆地理编码**：经纬度转地址
- **并行处理**：多线程加速批量转换
- **程序化调用**：支持 `--json` 参数输出结构化数据，便于脚本和程序集成

## 项目结构

```
geocode-tool/
├── geocode/           # 核心模块
│   ├── cli.py         # CLI入口（Typer）
│   ├── geocoder.py    # 地理编码
│   ├── cache.py       # SQLite缓存（~180行）
│   ├── errors.py      # 异常定义
│   └── ...
├── install.bat        # Windows一键安装
├── uninstall.bat      # 卸载脚本
├── .env.example       # API密钥模板
├── CHANGELOG.md       # 更新日志
├── LICENSE            # MIT许可证
└── pyproject.toml     # 项目配置
```

## 快速开始

### 安装

**方式1：PyPI 安装（推荐）**

```bash
pip install yaelocus
```

**方式2：从源码安装**

```bash
git clone https://github.com/Yaemikoreal/YaeLocus.git
cd YaeLocus
pip install -e .
```

**方式3：Windows 一键安装**

双击 `install.bat` 即可自动安装。

安装完成后，可通过以下方式使用：

```bash
# 方式1：使用命令（推荐）
yaelocus --help

# 方式2：模块方式
python -m geocode.cli --help
```

### 配置

```bash
# 交互式配置（推荐）
yaelocus config
```

只需配置至少一个API密钥：

| API | 免费额度 | 申请地址 |
|-----|---------|----------|
| 高德地图 | 5000次/日 | https://lbs.amap.com |
| 天地图 | 10000次/日 | https://www.tianditu.gov.cn |
| 百度地图 | 6000次/日 | https://lbsyun.baidu.com |

### 运行

```bash
# 执行地理编码
yaelocus run -i data/清单.xlsx

# 多格式输出
yaelocus run -i data/清单.xlsx -f xlsx      # Excel 输出
yaelocus run -i data/清单.xlsx -f geojson   # GeoJSON 输出

# 并行处理（5线程）
yaelocus run -i data/清单.xlsx -w 5

# 断点续传（跳过已缓存）
yaelocus run -i data/清单.xlsx --skip-cached

# JSON输出（便于程序集成）
yaelocus run -i data/清单.xlsx --stdout-json
yaelocus geocode "天安门" --json
yaelocus cache stats --json

# 查看可用文件
yaelocus files
yaelocus files --detail

# 查看配额使用
yaelocus quota

# 环境诊断
yaelocus doctor

# 查看缓存统计
yaelocus cache stats
```

## CLI 命令

```bash
# 单地址转换
yaelocus geocode "北京市朝阳区"           # 转换单个地址
yaelocus geocode "天安门" --json         # JSON格式输出

# 逆地理编码（经纬度转地址）
yaelocus reverse 39.9 116.4
yaelocus reverse 39.9 116.4 --json

# 坐标转换
yaelocus convert 39.9 116.4 --from gcj02 --to wgs84
yaelocus convert 39.9 116.4 --from bd09 --to wgs84 --json

# 批量转换
yaelocus run -i <文件>                   # 执行地理编码
yaelocus run -i <文件> -f xlsx           # Excel 输出
yaelocus run -i <文件> -w 5              # 5线程并行
yaelocus run -i <文件> --skip-cached     # 断点续传

# 文件列表
yaelocus files                           # 列出可处理文件
yaelocus files --detail                  # 显示详细信息

# 配额管理
yaelocus quota                           # 查看配额使用

# 缓存管理
yaelocus cache stats                     # 查看缓存统计
yaelocus cache cleanup                   # 清理过期缓存
yaelocus cache export                    # 导出缓存数据

# 配置与诊断
yaelocus config                          # 交互式配置API密钥
yaelocus doctor                          # 环境诊断
yaelocus test-api                        # 测试API连通性
yaelocus --version                       # 显示版本信息
```

### run 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i, --input` | 输入文件（CSV/Excel） | 必填 |
| `-c, --column` | 地址列名 | `地址` |
| `-o, --output` | 输出文件 | 自动生成 |
| `-f, --format` | 输出格式（csv/xlsx/json/geojson） | `csv` |
| `-w, --workers` | 并行线程数 | `1` |
| `--skip-cached` | 跳过已缓存地址 | `False` |
| `-m, --map` | 输出地图HTML | 自动生成 |
| `--ttl` | 缓存过期时间(秒) | 永不过期 |
| `--cleanup` | 清理过期缓存 | - |
| `-v, --verbose` | 详细输出 | - |

## Python API

```python
from geocode import Geocoder, CacheManager, create_map

# 使用上下文管理器自动关闭
with CacheManager("cache.db") as cache:
    geocoder = Geocoder(cache)
    
    # 单个地址转换
    result = geocoder.geocode("北京市朝阳区建国路88号")
    print(result['longitude'], result['latitude'])
    
    # 逆地理编码
    address = geocoder.reverse_geocode(39.9, 116.4)
    print(address['formatted_address'])
    
    # 批量转换
    results = geocoder.batch_geocode(["地址1", "地址2", "地址3"])
    
    # 生成地图
    valid = [r for r in results if r.get("success")]
    create_map(valid, output_file="map.html")
    
    # 缓存统计
    print(geocoder.get_cache_stats())
```

## API配额

| API | 免费额度 | 坐标系 |
|-----|---------|--------|
| 高德地图 | 5000次/日 | GCJ-02 |
| 天地图 | 10000次/日 | CGCS2000 |
| 百度地图 | 6000次/日 | BD-09 |

三者合计 **21000次/日**，智能轮换优先使用高德。

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/地址_经纬度_结果.csv` | 转换结果 |
| `output/地图输出.html` | 交互式地图 |
| `output/geocache.db` | SQLite缓存 |
| `output/api调用日志.csv` | API调用记录 |

## 常见问题

**Q: 首次运行找不到命令？**
```bash
# 确保已安装
pip install yaelocus

# 检查环境
yaelocus doctor
```

**Q: API配额用完了？**
工具会自动轮换三个API，合计21000次/日，通常足够。

**Q: 如何获取API密钥？**
- 高德：https://lbs.amap.com（注册→控制台→应用管理→创建应用→添加Key）
- 天地图：https://www.tianditu.gov.cn（注册→开发资源→申请Key）
- 百度：https://lbsyun.baidu.com（注册→控制台→创建应用）

**Q: 如何卸载？**
```bash
pip uninstall yaelocus
```

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)

## License

[MIT License](LICENSE)

---

**YaeLocus** - Made with ❤️ by [Yaemikoreal](https://github.com/Yaemikoreal)
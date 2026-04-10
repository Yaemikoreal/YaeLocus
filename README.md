# YaeLocus - 地址转经纬度工具

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.2.0](https://img.shields.io/badge/version-1.2.0-green.svg)](https://github.com/Yaemikoreal/YaeLocus)

**Author: [Yaemikoreal](https://github.com/Yaemikoreal)**

基于多API混合调用的地理编码工具，支持批量地址转换、高性能缓存、交互式地图可视化。

**项目地址**: https://github.com/Yaemikoreal/YaeLocus

## 功能特性

- **多API轮换**：高德/百度/天地图三API智能轮换，免费额度合计21000次/日
- **现代化CLI**：Typer + Rich 彩色输出，交互式配置向导
- **高性能缓存**：SQLite持久化，延迟提交，写入性能提升10倍+
- **坐标转换**：自动转换为WGS-84坐标系
- **交互式地图**：点聚类 + 热力图
- **多格式支持**：CSV和Excel输入

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

**方式1：双击安装（Windows）**

双击 `install.bat` 即可自动安装。

**方式2：命令行安装**

```bash
# 直接指定路径安装
pip install -e E:\Pythonproject\geocode-tool

# 或进入目录后安装
cd E:\Pythonproject\geocode-tool
pip install -e .
```

安装完成后，可通过以下方式使用：

```bash
# 方式1：模块方式（推荐，无需配置PATH）
python -m geocode.cli --help

# 方式2：直接命令（需 Scripts 目录在 PATH 中）
geocode-tool --help

# 方式3：直接运行脚本
python run.py -i data/清单.xlsx
```

### 配置

```bash
# 交互式配置（推荐）
geocode-tool config
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
python -m geocode.cli run -i data/清单.xlsx

# 指定地址列名
python -m geocode.cli run -i input.xlsx -c "详细地址"

# 环境诊断
python -m geocode.cli doctor

# 查看缓存统计
python -m geocode.cli cache stats
```

> 提示：如果 `Scripts` 目录在 PATH 中，可直接使用 `geocode-tool` 命令。

## CLI 命令

```bash
# 单地址转换（新增）
python -m geocode.cli geocode "北京市朝阳区"     # 转换单个地址
python -m geocode.cli geocode "天安门" --json   # JSON格式输出

# 批量转换
python -m geocode.cli run -i <文件>             # 执行地理编码

# 缓存管理
python -m geocode.cli cache stats               # 查看缓存统计
python -m geocode.cli cache cleanup             # 清理过期缓存
python -m geocode.cli cache export              # 导出缓存数据

# 配置与诊断
python -m geocode.cli config                    # 交互式配置API密钥
python -m geocode.cli doctor                    # 环境诊断
python -m geocode.cli test-api                  # 测试API连通性
python -m geocode.cli --version                 # 显示版本信息
```

> 简写：可创建别名 `alias gt="python -m geocode.cli"`

### run 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i, --input` | 输入文件（CSV/Excel） | 必填 |
| `-c, --column` | 地址列名 | `地址` |
| `-o, --output` | 输出CSV | 自动生成 |
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
pip install -e E:\Pythonproject\geocode-tool

# 检查环境
geocode-tool doctor
```

**Q: API配额用完了？**
工具会自动轮换三个API，合计21000次/日，通常足够。

**Q: 如何获取API密钥？**
- 高德：https://lbs.amap.com（注册→控制台→应用管理→创建应用→添加Key）
- 天地图：https://www.tianditu.gov.cn（注册→开发资源→申请Key）
- 百度：https://lbsyun.baidu.com（注册→控制台→创建应用）

**Q: 如何卸载？**
双击 `uninstall.bat` 或运行 `pip uninstall geocode-tool`

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)

## License

[MIT License](LICENSE)

---

**YaeLocus** - Made with ❤️ by [Yaemikoreal](https://github.com/Yaemikoreal)
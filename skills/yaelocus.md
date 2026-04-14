---
name: yaelocus
description: YaeLocus 地理编码工具 - 地址转经纬度，支持多API轮换、批量处理、缓存管理。用于执行地理编码、逆地理编码、坐标转换、缓存管理等操作。
trigger:
  - 用户要求地址转经纬度
  - 用户要求批量地理编码
  - 用户要求逆地理编码（经纬度转地址）
  - 用户要求坐标转换
  - 用户提到 yaelocus、geocode-tool、地理编码
  - 用户要求处理地址数据文件
---

# YaeLocus Skill

地理编码工具，支持高德/百度/天地图三API智能轮换，合计21000次/日免费额度。

## 核心功能

| 功能 | 命令 | 说明 |
|------|------|------|
| 批量地理编码 | `yaelocus run` | 地址文件批量转经纬度 |
| 单地址转换 | `yaelocus geocode` | 单个地址转经纬度 |
| 逆地理编码 | `yaelocus reverse` | 经纬度转地址 |
| 坐标转换 | `yaelocus convert` | 坐标系转换 |
| 缓存管理 | `yaelocus cache` | 查看/清理缓存 |
| 配置 | `yaelocus config` | 配置API密钥 |

## 常用命令

### 批量地理编码

```bash
# 基本用法
yaelocus run -i data/地址.xlsx

# 指定输出格式
yaelocus run -i data/地址.xlsx -f xlsx      # Excel
yaelocus run -i data/地址.xlsx -f geojson   # GeoJSON

# 并行处理
yaelocus run -i data/地址.xlsx -w 5

# 断点续传（跳过已缓存）
yaelocus run -i data/地址.xlsx --skip-cached

# AI调用模式（结构化JSON输出）
yaelocus run -i data/地址.xlsx --stdout-json
```

### 单地址转换

```bash
yaelocus geocode "北京市朝阳区"
yaelocus geocode "天安门" --json
```

### 逆地理编码

```bash
yaelocus reverse 39.9 116.4
yaelocus reverse 39.9 116.4 --json
```

### 坐标转换

```bash
# GCJ-02 转 WGS-84
yaelocus convert 39.9 116.4 --from gcj02 --to wgs84

# BD-09 转 WGS-84
yaelocus convert 39.9 116.4 --from bd09 --to wgs84
```

### 缓存管理

```bash
yaelocus cache stats           # 查看统计
yaelocus cache stats --json    # JSON格式
yaelocus cache cleanup         # 清理过期缓存
```

### 程序化调用

```bash
# 结构化JSON输出（便于程序解析）
yaelocus run -i data/地址.xlsx --stdout-json
yaelocus geocode "地址" --json
yaelocus reverse 39.9 116.4 --json
yaelocus cache stats --json
```

## 输出格式

### stdout-json 输出结构

```json
{
  "command": "run",
  "status": "success",
  "results": [
    {
      "original_address": "北京市朝阳区",
      "formatted_address": "北京市朝阳区",
      "longitude": 116.4853,
      "latitude": 39.9289,
      "province": "北京市",
      "city": "朝阳区",
      "source": "amap",
      "success": true
    }
  ],
  "stats": {
    "total": 10,
    "success": 8,
    "failed": 2,
    "success_rate": 80.0,
    "cache_hit_rate": 30.0
  }
}
```

### 错误输出结构

```json
{
  "error": {
    "code": "NO_API_KEY",
    "message": "未配置任何API密钥",
    "suggestion": "运行 'yaelocus config' 配置API密钥"
  },
  "command": "run",
  "status": "error"
}
```

## 应用场景

### 1. 批量地址数据处理

用户有大量地址需要转换为经纬度时：

```bash
yaelocus run -i addresses.xlsx -f xlsx -w 5 --skip-cached
```

### 2. 单地址快速查询

需要快速获取某个地址的经纬度：

```bash
yaelocus geocode "北京市朝阳区建国路88号" --json
```

### 3. 经纬度反向查询

已知坐标需要获取地址信息：

```bash
yaelocus reverse 39.9059 116.4699 --json
```

### 4. 坐标系统一转换

将不同来源的坐标统一为WGS-84：

```bash
# 高德坐标转WGS-84
yaelocus convert 39.9 116.4 --from gcj02 --to wgs84

# 百度坐标转WGS-84
yaelocus convert 39.9 116.4 --from bd09 --to wgs84
```

### 5. AI/程序集成调用

使用 `--stdout-json` 或 `--json` 参数获取结构化输出：

```bash
# 批量处理结果
result=$(yaelocus run -i data.xlsx --stdout-json)

# 单地址结果
result=$(yaelocus geocode "地址" --json)

# 缓存统计
stats=$(yaelocus cache stats --json)
```

## 常见歧义解释

### --stdout-json vs --json

| 参数 | 适用命令 | 说明 |
|------|---------|------|
| `--stdout-json` | `run` | 批量命令的完整结果输出到stdout |
| `--json` / `-j` | `geocode`, `reverse`, `convert`, `cache stats` | 单命令的JSON输出 |

**注意**: `run` 命令使用 `--stdout-json`，其他命令使用 `--json`。

### 输入文件格式

| 参数 | 格式 | 说明 |
|------|------|------|
| `-f csv` | CSV | 默认格式，UTF-8编码 |
| `-f xlsx` | Excel | Excel格式输出 |
| `-f json` | JSON | JSON数组格式 |
| `-f geojson` | GeoJSON | 地理标准格式，适合GIS工具 |

### --skip-cached 行为

- **True（默认）**: 跳过已缓存的地址，仅处理新地址（断点续传）
- **False（--no-skip-cached）**: 重新处理所有地址，更新缓存

### 坐标系说明

| API | 原始坐标系 | 输出坐标系 |
|-----|-----------|-----------|
| 高德 | GCJ-02 | WGS-84（自动转换） |
| 天地图 | CGCS2000 | CGCS2000（无需转换） |
| 百度 | BD-09 | WGS-84（自动转换） |

**注意**: 工具自动将结果转换为 WGS-84，无需手动处理。

### workers 参数

- `-w 1`: 单线程（默认）
- `-w 5`: 5线程并行，适合大批量处理
- 最大值: 10

### 缓存位置

默认缓存文件: `output/geocache.db`

可通过 `--cache` 参数指定其他位置：
```bash
yaelocus run -i data.xlsx --cache custom/cache.db
```

## Python API 用法

```python
from geocode import Geocoder, CacheManager

with CacheManager("cache.db") as cache:
    geocoder = Geocoder(cache)
    
    # 单地址
    result = geocoder.geocode("北京市朝阳区")
    
    # 批量
    results = geocoder.batch_geocode(["地址1", "地址2"])
    
    # 逆地理编码
    address = geocoder.reverse_geocode(39.9, 116.4)
    
    # 统计
    stats = geocoder.get_cache_stats()
```

## 配置要求

首次使用需配置API密钥：

```bash
yaelocus config
```

或在 `.env` 文件中配置：
```
AMAP_KEY=xxx        # 高德地图
BAIDU_AK=xxx        # 百度地图  
TIANDITU_TK=xxx     # 天地图
```

至少配置一个API密钥即可使用。
---
name: yaelocus
description: YaeLocus 地理编码工具 - 地址转经纬度，支持多API轮换、批量处理、缓存管理。专为 AI Agent 优化，提供结构化 JSON 输出、错误恢复路径、HTTP API 端点。包含完整的工具检测、配置检查、命令参考手册。
trigger:
  - 用户要求地址转经纬度
  - 用户要求批量地理编码
  - 用户要求逆地理编码（经纬度转地址）
  - 用户要求坐标转换
  - 用户提到 yaelocus、geocode-tool、地理编码
  - 用户要求处理地址数据文件
  - Agent 需要调用地理编码服务
---

# YaeLocus Skill

地理编码工具，支持高德/百度/天地图三API智能轮换，合计 21000 次/日免费额度。
**专为 AI Agent 优化**：完整工具检测 + 配置检查 + 结构化输出 + 自动错误恢复。

---

## 1. 工具检测与部署

### 1.1 检测工具是否已安装

执行以下命令检测：

```bash
yaelocus --version
```

**响应解读**：

| 响应 | 状态 | Agent 应执行 |
|-----|------|-------------|
| `yaelocus x.x.x` | 已安装 | 继续执行后续命令 |
| `command not found` 或 `not recognized` | 未安装 | 执行安装流程 |
| 其他错误 | 异常 | 检查 PATH 或 Python 环境 |

### 1.2 安装 YaeLocus

**版本选择**：

| 版本 | 说明 | 安装命令 |
|------|------|---------|
| **CLI-only 稳定版**（推荐） | 仅 CLI 功能，适配 AI Agent 和日常使用，稳定可靠 | `pip install yaelocus` |
| **完整 Beta 版** | 包含 Web API + AI 功能，TUI 需额外安装 Node.js 依赖 | `pip install "yaelocus[beta]"` |

**CLI-only 稳定版安装（推荐）**

```bash
pip install yaelocus
```

**完整 Beta 版安装**

```bash
pip install "yaelocus[beta]"

# TUI 需额外安装 Node.js 依赖（可选）
cd tui && npm install && npm run build
```

**extras 分组说明**：

| 分组 | 包含内容 | 安装命令 |
|------|---------|---------|
| 默认（无 extras） | CLI 核心功能 + Rich 回退界面 | `pip install yaelocus` |
| `[ai]` | AI 功能（httpx） | `pip install "yaelocus[ai]"` |
| `[web]` | Web API 服务器（fastapi/uvicorn） | `pip install "yaelocus[web]"` |
| `[beta]` | AI + Web 全部功能 | `pip install "yaelocus[beta]"` |
| `[dev]` | 开发测试工具 | `pip install "yaelocus[dev]"` |

**源码安装**

```bash
# 克隆仓库
git clone https://github.com/Yaemikoreal/YaeLocus.git
cd YaeLocus

# CLI-only 稳定版
pip install -e .

# 完整 Beta 版
pip install -e ".[beta]"

# 开发环境
pip install -e ".[dev,beta]"
```

**指定版本安装**

```bash
pip install yaelocus==1.6.1
pip install "yaelocus[beta]==1.6.1"
```

### 1.3 安装验证

```bash
# 验证版本
yaelocus --version

# 验证命令可用
yaelocus config check --json
```

期望输出：
```json
{
  "status": "success",
  "version": "1.6.1"
}
```

---

## 2. 环境配置检查

### 2.1 检测 API Key 是否配置

**重要**: Agent 在执行地理编码前，必须先检查 API Key 配置。

```bash
yaelocus config check --json
```

**响应解读**：

```json
{
  "command": "config_check",
  "status": "success",
  "apis": [
    {"name": "amap", "available": true, "key_configured": true},
    {"name": "tianditu", "available": false, "key_configured": false},
    {"name": "baidu", "available": false, "key_configured": false}
  ],
  "warnings": []
}
```

| 字段 | 含义 | Agent 应执行 |
|-----|------|-------------|
| `apis` 数组非空且有 `available=true` | 至少一个 API Key 已配置 | 继续执行地理编码 |
| `apis` 数组为空或全部 `available=false` | 未配置任何 API Key | 执行配置流程 |
| `warnings` 非空 | 有配置问题 | 查看警告并处理 |

### 2.2 配置文件位置

| 文件 | 位置 | 说明 |
|-----|------|------|
| `.env` | 项目根目录或工作目录 | 环境变量配置文件 |
| `output/database/geocache.db` | `output/database/` | 缓存数据库 |

**Agent 应告知用户**：配置文件位于 `.env`，可在项目根目录或当前工作目录创建。

### 2.3 API Key 获取指南

Agent 应告知用户如何获取 API Key：

| API | 免费额度/日 | 获取地址 | 说明 |
|-----|----------|---------|------|
| **高德地图** | 5000 | https://lbs.amap.com/ | 需注册开发者账号，创建应用获取 Key（32位字符） |
| **天地图** | 10000 | https://www.tianditu.gov.cn/ | 国家测绘局官方服务，需注册账号 |
| **百度地图** | 6000 | https://lbsyun.baidu.com/ | 需注册开发者账号 |

**总计**: 21000 次/日，三 API 自动轮换。

**建议**: 至少配置高德或天地图其中一个，推荐配置全部三个以最大化配额。

### 2.4 配置 API Key

**方式一：交互式配置向导（推荐）**

```bash
yaelocus config setup
```

Agent 执行此命令后，引导用户交互输入 API Key。

**方式二：手动编辑 .env 文件**

Agent 告知用户创建 `.env` 文件，内容如下：

```
# 地图 API 配置（至少配置一个）
AMAP_KEY=你的高德API密钥        # 32位字符
BAIDU_AK=你的百度AK
TIANDITU_TK=你的天地图TK

# AI 功能配置（可选）
AI_ENABLED=true                 # 启用 AI
AI_PROVIDER=deepseek            # 供应商: deepseek/qwen/glm/moonshot
DEEPSEEK_API_KEY=你的DeepSeek密钥

# 路线规划配置（可选）
ROUTING_MODE=ai                 # 模式: ai（免费）/ api（付费）
```

### 2.5 配置验证

配置完成后，Agent 应再次执行：

```bash
yaelocus config check --json
```

确认 `apis` 数组中有至少一个 `available=true`。

---

## 3. 目录与路径

### 3.1 默认目录结构

```
项目根目录/
├── data/                    # 输入文件目录（默认）
│   ├── 清单.xlsx            # 待处理地址文件
│   └── addresses.csv        # 支持 CSV/XLSX/XLS
│
├── output/                  # 输出目录（自动创建）
│   ├── csv/                 # 结果文件（CSV/XLSX/JSON）
│   │   └── 清单.csv         # 地理编码结果
│   ├── map/                 # 地图文件（HTML）
│   │   └── 清单_map.html    # 可视化地图
│   ├── database/            # 缓存数据库
│   │   └── geocache.db      # SQLite 缓存
│   ├── log/                 # API 日志
│   │   └── api调用日志.csv  # 调用记录
│   ├── export/              # 导出文件
│   └── progress/            # 临时进度文件
│
├── .env                     # 配置文件
├── requirements.txt         # 依赖列表
└── geocode/                 # 源码目录
```

### 3.2 输入文件目录

**默认**: `data/`

**Agent 行为**：
1. 用户未指定路径时，使用 `data/` 目录
2. 查看可处理文件：`yaelocus map list`
3. 查看文件详情：`yaelocus map list --detail --json`

### 3.3 输出文件目录

**默认**: `output/`

| 输出类型 | 子目录 | 文件命名规则 |
|---------|--------|-------------|
| 结果 CSV | `output/csv/` | `{输入文件名}.csv` |
| 结果 XLSX | `output/csv/` | `{输入文件名}.xlsx` |
| 地图 HTML | `output/map/` | `{输入文件名}_map.html` |
| 缓存数据库 | `output/database/` | `geocache.db` |
| API 日志 | `output/log/` | `api调用日志.csv` |

### 3.4 自定义路径

```bash
# 自定义输入路径
yaelocus geocode batch -i /path/to/file.xlsx

# 自定义输出路径
yaelocus geocode batch -i data/清单.xlsx -o /path/to/result.csv

# 自定义缓存路径
yaelocus geocode batch -i data/清单.xlsx --cache /path/to/cache.db
```

---

## 4. 命令参考手册

### 4.1 命令分组结构

```
yaelocus                           # 无参数启动 TUI
│
├── geocode                        # 地理编码操作
│   ├── single <ADDRESS>           # 单地址转换
│   ├── batch                      # 批量转换
│   ├── reverse <LAT> <LON>        # 逆地理编码
│   └── convert <LAT> <LON>        # 坐标转换
│
├── map                            # 地图与可视化
│   ├── list                       # 列出可处理文件
│   └── create                     # 生成地图
│
├── ai                             # AI 功能（需配置 AI_API_KEY）
│   ├── chat <MESSAGE>             # AI 对话
│   ├── analyze                    # 数据分析
│   └── route                      # 交互式路线规划
│
├── config                         # 配置管理
│   ├── setup                      # 交互式配置向导
│   ├── check                      # 环境诊断
│   ├── test-api                   # API 连通性测试
│   └── cache                      # 缓存管理子命令
│       ├── stats                  # 缓存统计
│       ├── clear                  # 清空缓存
│       ├── cleanup                # 清理过期缓存
│       └── export                 # 导出缓存
│
└── serve                          # 启动 API 服务器
```

---

### 4.2 geocode 分组 - 地理编码操作

#### `yaelocus geocode single` - 单地址转换

**用法**：
```bash
yaelocus geocode single <ADDRESS> [--json]
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `ADDRESS` | string | 是 | 要转换的地址（如 "北京市朝阳区建国路88号"） |
| `--json`, `-j` | flag | 否 | JSON 格式输出（Agent 必须使用此参数） |
| `--cache` | Path | 否 | 自定义缓存数据库路径 |
| `--ttl` | int | 否 | 缓存有效期（秒） |

**输出示例（--json）**：
```json
{
  "command": "geocode_single",
  "status": "success",
  "address": "北京市朝阳区",
  "longitude": 116.4853,
  "latitude": 39.9289,
  "formatted_address": "北京市朝阳区",
  "province": "北京市",
  "city": "朝阳区",
  "district": null,
  "source": "amap",
  "confidence": 95
}
```

---

#### `yaelocus geocode batch` - 批量地理编码

**用法**：
```bash
yaelocus geocode batch -i <FILE> [--stdout-json]
```

**参数**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----|------|------|--------|------|
| `-i, --input` | Path | **是** | - | 输入文件路径（CSV/XLSX/XLS） |
| `-c, --column` | string | 否 | "地址" | 地址列名 |
| `-o, --output` | Path | 否 | auto | 输出文件路径 |
| `-m, --map` | Path | 否 | auto | 地图输出路径 |
| `-f, --format` | string | 否 | "csv" | 输出格式：csv/xlsx/json/geojson |
| `--skip-cached` | flag | 否 | True | 跳过已缓存地址（断点续传） |
| `-w, --workers` | int | 否 | 1 | 并行线程数（1-10） |
| `--stdout-json` | flag | **重要** | False | 完整 JSON 输出到 stdout（Agent 必须使用） |
| `-v, --verbose` | flag | 否 | False | 显示详细日志 |
| `--cache` | Path | 否 | default | 自定义缓存路径 |
| `--ttl` | int | 否 | - | 缓存有效期（秒） |
| `--cleanup` | flag | 否 | False | 运行前清理过期缓存 |
| `--no-cluster` | flag | 否 | False | 禁用地图点聚类 |
| `--no-heatmap` | flag | 否 | False | 禁用地图热力图 |

**Agent 注意事项**：
- **必须使用 `--stdout-json`** 获取结构化输出
- 若地址列名不是 "地址"，使用 `-c` 指定正确列名

**输出示例（--stdout-json）**：
```json
{
  "command": "geocode_batch",
  "status": "partial",
  "results": [
    {
      "original_address": "北京市朝阳区",
      "formatted_address": "北京市朝阳区",
      "longitude": 116.4853,
      "latitude": 39.9289,
      "province": "北京市",
      "city": "朝阳区",
      "source": "amap",
      "confidence": 95,
      "success": true
    },
    {
      "original_address": "上海市浦东新区",
      "success": false,
      "error": "API quota exceeded"
    }
  ],
  "stats": {
    "total": 100,
    "success": 85,
    "failed": 10,
    "discarded": 5,
    "success_rate": 85.0,
    "cache_hit_rate": 30.0,
    "api_usage": {"amap": 50, "tianditu": 35}
  },
  "output_files": {
    "result": "output/csv/清单.csv",
    "map": "output/map/清单_map.html",
    "cache": "output/database/geocache.db"
  }
}
```

---

#### `yaelocus geocode reverse` - 逆地理编码

**用法**：
```bash
yaelocus geocode reverse <LAT> <LON> [--json]
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `LAT` | float | **是** | 纬度坐标值 |
| `LON` | float | **是** | 经度坐标值 |
| `--json`, `-j` | flag | **重要** | JSON 格式输出（Agent 必须使用） |
| `--cache` | Path | 否 | 自定义缓存路径 |

**输出示例（--json）**：
```json
{
  "command": "geocode_reverse",
  "status": "success",
  "latitude": 39.9042,
  "longitude": 116.4074,
  "formatted_address": "北京市东城区东华门街道",
  "province": "北京市",
  "city": "东城区",
  "district": "东华门街道",
  "source": "amap"
}
```

---

#### `yaelocus geocode convert` - 坐标系转换

**用法**：
```bash
yaelocus geocode convert <LAT> <LON> --from <SYS> --to <SYS> [--json]
```

**参数**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----|------|------|--------|------|
| `LAT` | float | **是** | - | 纬度坐标值 |
| `LON` | float | **是** | - | 经度坐标值 |
| `--from` | string | 否 | "wgs84" | 源坐标系：wgs84/gcj02/bd09 |
| `--to` | string | 否 | "gcj02" | 目标坐标系：wgs84/gcj02/bd09 |
| `--json`, `-j` | flag | **重要** | - | JSON 格式输出 |

**坐标系说明**：

| 坐标系 | 说明 | 常见来源 |
|--------|------|---------|
| WGS-84 | 国际标准坐标系 | GPS 设备、国际地图 |
| GCJ-02 | 中国加密坐标系（火星坐标） | 高德地图、腾讯地图 |
| BD-09 | 百度加密坐标系 | 百度地图 |

**输出示例（--json）**：
```json
{
  "command": "geocode_convert",
  "status": "success",
  "input": {
    "lat": 39.9042,
    "lon": 116.4074,
    "coordinate_system": "gcj02"
  },
  "output": {
    "lat": 39.9029,
    "lon": 116.4011,
    "coordinate_system": "wgs84"
  }
}
```

---

### 4.3 map 分组 - 地图与可视化

#### `yaelocus map list` - 列出可处理文件

**用法**：
```bash
yaelocus map list [--detail] [--json]
```

**参数**：

| 参数 | 类型 | 说明 |
|-----|------|------|
| `-p, --path` | Path | 指定扫描目录（默认 data/） |
| `-d, --detail` | flag | 显示详细信息（列名、行数） |
| `--json` | flag | JSON 格式输出（Agent 必须使用） |

**输出示例（--detail --json）**：
```json
{
  "command": "map_list",
  "status": "success",
  "files": [
    {
      "name": "清单.xlsx",
      "path": "data/清单.xlsx",
      "size_kb": 125.3,
      "modified": 1715123456.789,
      "columns": ["地址", "名称", "数量"],
      "rows": 100
    }
  ],
  "count": 1
}
```

**Agent 用途**：执行批量地理编码前，先查看文件列名，确定正确的 `-c` 参数。

---

#### `yaelocus map create` - 生成地图

**用法**：
```bash
yaelocus map create -i <CSV_FILE> [-t "标题"]
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `-i, --input` | Path | **是** | 地理编码结果文件（CSV） |
| `-o, --output` | Path | 否 | 输出地图路径（默认自动生成） |
| `-t, --title` | string | 否 | 地图标题 |
| `--no-cluster` | flag | 否 | 禁用点聚类 |
| `--no-heatmap` | flag | 否 | 禁用热力图 |

---

### 4.4 ai 分组 - AI 功能

**前提条件**：需在 `.env` 中配置 `AI_ENABLED=true` 和对应的 AI API Key。

#### `yaelocus ai chat` - AI 对话

**用法**：
```bash
yaelocus ai chat <MESSAGE> [-i <FILE>] [--json]
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `MESSAGE` | string | **是** | 发送给 AI 的消息 |
| `-i, --input` | Path | 否 | 附加上下文文件（CSV/JSON） |
| `--provider` | string | 否 | AI 供应商（deepseek/qwen/glm/moonshot） |
| `--model` | string | 否 | AI 模型名 |
| `--json` | flag | 否 | JSON 格式输出 |

---

#### `yaelocus ai analyze` - AI 数据分析

**用法**：
```bash
yaelocus ai analyze -i <CSV_FILE>
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `-i, --input` | Path | **是** | 地理编码结果文件 |
| `--json` | flag | 否 | JSON 格式输出 |

---

#### `yaelocus ai route` - 交互式路线规划

**用法**：
```bash
yaelocus ai route -i <CSV_FILE>
```

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `-i, --input` | Path | **是** | 地理编码结果文件 |
| `-o, --output` | Path | 否 | 输出地图路径 |

---

### 4.5 config 分组 - 配置管理

#### `yaelocus config setup` - 交互式配置向导

**用法**：
```bash
yaelocus config setup
```

**说明**：无参数，启动交互式配置向导，引导用户配置 API Key 和 AI 供应商。

**Agent 使用场景**：当检测到 `NO_API_KEY` 错误时，引导用户执行此命令。

---

#### `yaelocus config check` - 环境诊断

**用法**：
```bash
yaelocus config check [--json]
```

**输出示例（--json）**：
```json
{
  "command": "config_check",
  "status": "success",
  "apis": [
    {"name": "amap", "available": true, "key_configured": true},
    {"name": "tianditu", "available": false},
    {"name": "baidu", "available": false}
  ],
  "cache": {
    "entries": 150,
    "hit_rate": 35.5,
    "size_mb": 2.3
  },
  "ai": {
    "enabled": true,
    "provider": "deepseek"
  },
  "warnings": []
}
```

---

#### `yaelocus config test-api` - API 连通性测试

**用法**：
```bash
yaelocus config test-api
```

**说明**：测试已配置 API 的连通性，验证 API Key 是否有效。

---

#### `yaelocus config cache` - 缓存管理

**子命令**：

| 子命令 | 说明 | 用法 |
|--------|------|------|
| `stats` | 缓存统计 | `yaelocus config cache stats [--json]` |
| `clear` | 清空缓存 | `yaelocus config cache clear` |
| `cleanup` | 清理过期缓存 | `yaelocus config cache cleanup` |
| `export` | 导出缓存 JSON | `yaelocus config cache export` |

**stats 输出示例（--json）**：
```json
{
  "command": "cache_stats",
  "status": "success",
  "total_entries": 1500,
  "hits": 450,
  "misses": 1050,
  "hit_rate": 30.0,
  "size_mb": 5.2,
  "db_path": "output/database/geocache.db"
}
```

---

### 4.6 serve 命令 - API 服务器

**用法**：
```bash
yaelocus serve [--port 8765]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `--host`, `-h` | string | "127.0.0.1" | 监听地址 |
| `--port`, `-p` | int | 8765 | 监听端口 |
| `--no-gui` | flag | False | 仅启动 API 服务器（不打开浏览器） |

**直接启动模块**：
```bash
python -m geocode.api --port 8765
python -m geocode.api --port 0    # 随机端口
```

---

### 4.7 弃用命令映射（向后兼容）

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| `yaelocus run -i <file>` | `yaelocus geocode batch -i <file>` | 批量转换 |
| `yaelocus geocode "地址"` | `yaelocus geocode single "地址"` | 单地址 |
| `yaelocus reverse` | `yaelocus geocode reverse` | 逆地理编码 |
| `yaelocus convert` | `yaelocus geocode convert` | 坐标转换 |
| `yaelocus cache stats` | `yaelocus config cache stats` | 缓存统计 |
| `yaelocus files` | `yaelocus map list` | 文件列表 |
| `yaelocus doctor` | `yaelocus config check` | 环境诊断 |
| `yaelocus config` | `yaelocus config setup` | 配置向导 |
| `yaelocus ai "消息"` | `yaelocus ai chat "消息"` | AI 对话 |
| `yaelocus route` | `yaelocus ai route` | 路线规划 |

**Agent 注意**：旧命令仍可用但会输出弃用警告，建议使用新命令。

---

## 5. JSON 输出格式

### 5.1 统一响应结构

所有命令（使用 `--json` 或 `--stdout-json`）遵循统一结构：

```json
{
  "command": "<命令名>",
  "status": "success" | "error" | "partial",
  "results": [...],        // 可选，操作结果数组
  "stats": {...},          // 可选，统计信息
  "output_files": {...},   // 可选，输出文件路径
  "error": {...}           // 仅在 status=error 时存在
}
```

### 5.2 状态值含义

| 状态 | 含义 | Agent 行为 |
|-----|------|-----------|
| `success` | 完全成功 | 继续后续操作，告知用户结果路径 |
| `partial` | 部分成功（批量处理中有失败项） | 查看 stats 了解失败比例，决定是否重试 |
| `error` | 完全失败 | 解析 error 字段，执行错误恢复流程 |

---

## 6. Agent 错误处理协议

### 6.1 错误结构

```json
{
  "command": "geocode_batch",
  "status": "error",
  "error": {
    "code": "NO_API_KEY",
    "message": "未配置任何API密钥",
    "suggestion": "运行 'yaelocus config setup' 配置API密钥",
    "recoverable": true,
    "auto_fix_action": "config setup"
  }
}
```

### 6.2 错误码与恢复路径

| 错误码 | 含义 | 可恢复 | Agent 应执行 |
|-------|------|--------|-------------|
| `NO_API_KEY` | 未配置 API 密钥 | **Yes** | 告知用户配置文件位置（`.env`），询问是否需要帮助配置，或执行 `yaelocus config setup` |
| `FILE_NOT_FOUND` | 文件不存在 | **No** | 提示用户提供正确路径，建议执行 `yaelocus map list` 查看可用文件 |
| `COLUMN_NOT_FOUND` | 地址列不存在 | **Yes** | 执行 `yaelocus map list --detail --json` 查看文件列信息，使用正确的 `-c` 参数重试 |
| `API_QUOTA_EXCEEDED` | API 配额耗尽 | **Yes** | 执行 `yaelocus config check --json` 查看其他可用 API，或告知用户等待配额重置（次日） |
| `NETWORK_ERROR` | 网络故障 | **Yes** | 等待 5 秒后重试，或提示用户检查网络 |
| `INVALID_API_KEY` | API 密钥格式错误 | **Yes** | 告知用户检查密钥格式，执行 `yaelocus config setup` 重新配置 |

### 6.3 Agent 错误处理流程

```
1. 解析响应中的 error.code
2. 检查 error.recoverable 字段
3. 若 recoverable=true:
   a. 告知用户 error.message 和 error.suggestion
   b. 询问用户是否需要帮助配置（如 API Key）
   c. 如果有 auto_fix_action，可自动执行该命令
   d. 重试原命令
4. 若 recoverable=false:
   a. 向用户报告 error.message
   b. 提示 error.suggestion
   c. 请求用户提供必要信息（如正确的文件路径）
```

### 6.4 错误恢复示例

**场景：未配置 API Key**

Agent 检测到：
```json
{
  "error": {
    "code": "NO_API_KEY",
    "recoverable": true,
    "auto_fix_action": "config setup"
  }
}
```

Agent 响应：
1. 告知用户："未检测到地图 API Key。配置文件位于 `.env`，您需要至少配置一个 API Key。"
2. 提供获取指南：
   - 高德地图: https://lbs.amap.com/ (5000次/日)
   - 天地图: https://www.tianditu.gov.cn/ (10000次/日)
3. 询问："是否需要我帮助您配置？可执行 `yaelocus config setup` 启动配置向导。"

---

**场景：地址列不存在**

Agent 检测到：
```json
{
  "error": {
    "code": "COLUMN_NOT_FOUND",
    "message": "列 '地址' 不存在",
    "recoverable": true,
    "auto_fix_action": "map list --detail"
  }
}
```

Agent 响应：
1. 执行 `yaelocus map list --detail --json`
2. 解析输出获取正确列名：`{"columns": ["位置", "名称"]}`
3. 告知用户："检测到文件列名为 ['位置', '名称']，将使用 '位置' 作为地址列。"
4. 重试：`yaelocus geocode batch -i data/清单.xlsx -c "位置"`

---

## 7. Agent 完整工作流示例

### 7.1 首次使用流程

```
Step 1: 检测工具安装
→ yaelocus --version
→ 若未安装，执行 pip install yaelocus

Step 2: 检测 API Key 配置
→ yaelocus config check --json
→ 若 apis 为空，告知用户配置位置和获取指南

Step 3: 用户配置 API Key
→ 引导用户执行 yaelocus config setup 或手动创建 .env

Step 4: 验证配置
→ yaelocus config check --json
→ 确认有 available=true 的 API

Step 5: 执行地理编码
→ yaelocus geocode batch -i data/清单.xlsx --stdout-json

Step 6: 处理结果
→ 解析输出，告知用户结果路径和统计信息
```

### 7.2 批量地理编码完整流程

```
Step 1: 查看可处理文件
→ yaelocus map list --detail --json

Step 2: 确认地址列名
→ 从输出中获取 columns 字段

Step 3: 执行批量编码
→ yaelocus geocode batch -i data/清单.xlsx -c "地址" --stdout-json

Step 4: 解析结果
→ 检查 status 字段：
  - success: 告知用户完成
  - partial: 告知成功率，询问是否重试失败项
  - error: 执行错误恢复流程

Step 5: 告知输出路径
→ output_files 中的 result 和 map 路径
```

### 7.3 HTTP API 调用流程（后备方式）

```
Step 1: 启动 API 服务器
→ python -m geocode.api --port 8765

Step 2: 获取 Schema（可选）
→ curl http://localhost:8765/api/schema/geocode_batch

Step 3: 执行命令
→ curl -X POST http://localhost:8765/api/execute \
    -H "Content-Type: application/json" \
    -d '{"command": "geocode batch -i data/清单.xlsx"}'

Step 4: 解析响应
→ JSON 结构与 CLI 输出一致
```

---

## 8. 配置项完整列表

### 8.1 .env 配置项

| 配置项 | 必需 | 说明 |
|--------|------|------|
| `AMAP_KEY` | 推荐 | 高德地图 API Key（32位） |
| `BAIDU_AK` | 可选 | 百度地图 AK |
| `TIANDITU_TK` | 推荐 | 天地图 TK |
| `AI_ENABLED` | 可选 | 启用 AI 功能（true/false） |
| `AI_PROVIDER` | 可选 | AI 供应商（deepseek/qwen/glm/moonshot） |
| `AI_MODEL` | 可选 | AI 模型名 |
| `DEEPSEEK_API_KEY` | 可选 | DeepSeek API Key |
| `QWEN_API_KEY` | 可选 | 通义千问 API Key |
| `GLM_API_KEY` | 可选 | 智谱 GLM API Key |
| `MOONSHOT_API_KEY` | 可选 | Kimi API Key |
| `ROUTING_MODE` | 可选 | 路线模式（ai=免费 / api=付费） |

### 8.2 API 配额详情

| API | 免费额度 | 坐标系 | 配置项 |
|-----|----------|--------|--------|
| 高德 | 5000/日 | GCJ-02 → WGS-84（自动转换） | `AMAP_KEY` |
| 天地图 | 10000/日 | CGCS2000（无需转换） | `TIANDITU_TK` |
| 百度 | 6000/日 | BD-09 → WGS-84（自动转换） | `BAIDU_AK` |

**总计**: 21000 次/日，三 API 自动轮换，首个成功即返回。

---

## 9. Python API 用法

```python
from geocode import Geocoder, CacheManager
from geocode.agent import AgentResponse, AgentError, CommandStatus

# 使用上下文管理器自动关闭
with CacheManager() as cache:
    geocoder = Geocoder(cache)

    # 单地址转换 → dict
    result = geocoder.geocode("北京市朝阳区建国路88号")
    print(result['longitude'], result['latitude'])

    # 逆地理编码
    addr = geocoder.reverse_geocode(39.9, 116.4)
    print(addr['formatted_address'])

    # 批量转换 → list[dict]
    results = geocoder.batch_geocode(["地址1", "地址2", "地址3"])

# 构建 Agent 响应
response = AgentResponse(
    command="geocode_single",
    status=CommandStatus.SUCCESS,
    results=[result]
)
```

---

## 10. Schema 动态查询

Agent 可通过 HTTP API 动态获取 JSON Schema 定义：

```bash
curl http://localhost:8765/api/schema
curl http://localhost:8765/api/schema/geocode_batch
curl http://localhost:8765/api/errors
```

---

## 11. 输出目录汇总

| 目录 | 内容 | 路径 |
|-----|------|------|
| 输入文件 | CSV/XLSX/XLS | `data/` |
| 结果文件 | CSV/XLSX/JSON | `output/csv/` |
| 地图文件 | HTML | `output/map/` |
| 缓存数据库 | SQLite | `output/database/geocache.db` |
| API 日志 | CSV | `output/log/api调用日志.csv` |
| 导出文件 | 各种 | `output/export/` |
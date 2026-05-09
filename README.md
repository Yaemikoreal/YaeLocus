# YaeLocus

**[中文](README.md) | [English](README_EN.md)**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.6.0](https://img.shields.io/badge/version-1.6.0-green.svg)](https://github.com/Yaemikoreal/YaeLocus)
[![PyPI](https://img.shields.io/badge/pypi-yaelocus-blue.svg)](https://pypi.org/project/yaelocus/)
[![Ink TUI](https://img.shields.io/badge/TUI-Ink%20%2B%20React-9cf.svg)](https://github.com/vadimdemedes/ink)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

**Author: [Yaemikoreal](https://github.com/Yaemikoreal)**

基于多 API 混合调用的地理编码工具，支持批量地址转换、高性能缓存、路线规划、行程优化、AI 数据分析和交互式终端界面。

**项目地址**: https://github.com/Yaemikoreal/YaeLocus

## 功能特性

### 核心功能
- **多 API 轮换**: 高德/百度/天地图三 API 智能轮换，免费额度合计 21000 次/日
- **高性能缓存**: SQLite + WAL 持久化，延迟提交优化，断点续传
- **坐标转换**: 自动转换为 WGS-84 坐标系，支持 GCJ-02/BD-09 双向转换
- **逆地理编码**: 经纬度转地址
- **多格式支持**: CSV、Excel、JSON、GeoJSON 输入输出

### 地图与可视化
- **交互式地图**: 点聚类 + 热力图 + 路线可视化（Folium + 高德瓦片）
- **地图生成**: 批量结果地图、路线地图、AI 分析面板

### 新增功能 (v1.6.0)
- **路线规划**: 多模式路线规划（步行/驾车/公交），支持 AI 引擎和 API 引擎
- **行程优化**: DBSCAN 聘类分析 + TSP 求解器，多策略路线推荐
- **AI 功能**: 集成 DeepSeek/Qwen/GLM/Moonshot，支持数据分析和路线规划对话
- **Ink TUI**: React + Ink 5 终端界面，通过 FastAPI 与 Python 后端通信
- **API 服务器**: FastAPI headless 服务，支持 SSE 流式响应
- **向后兼容**: 旧命令自动重定向到新分组命令

## 安装

### 版本选择

| 版本 | 说明 | 安装命令 |
|------|------|---------|
| **CLI-only 稳定版**（推荐） | 仅 CLI 功能，适配 AI Agent 和日常使用 | `pip install yaelocus` |
| **完整 Beta 版** | 包含 Web API + AI 功能，TUI 需额外安装 | `pip install "yaelocus[beta]"` |

### extras 分组

```bash
pip install yaelocus              # CLI-only 稳定版
pip install "yaelocus[ai]"        # + AI 功能
pip install "yaelocus[web]"       # + Web API 服务器
pip install "yaelocus[beta]"      # + AI + Web (完整 Beta 版)
pip install "yaelocus[dev]"       # + 开发测试工具
```

### PyPI 安装（推荐）

```bash
pip install yaelocus
```

### 源码安装

```bash
git clone https://github.com/Yaemikoreal/YaeLocus.git
cd YaeLocus
pip install -e .                    # CLI-only 稳定版
pip install -e ".[beta]"            # 完整 Beta 版
pip install -e ".[dev,beta]"        # 开发环境
```

### Windows 一键安装

双击 `install.bat` 自动安装。

### Ink TUI 安装（Beta 版可选）

```bash
cd tui && npm install && npm run build
```

## 配置

```bash
yaelocus config setup               # 交互式配置向导
```

至少配置一个 API 密钥：

| API | 免费额度 | 坐标系 | 申请地址 |
|-----|---------|--------|----------|
| 高德地图 | 5000次/日 | GCJ-02 | https://lbs.amap.com |
| 天地图 | 10000次/日 | CGCS2000 | https://www.tianditu.gov.cn |
| 百度地图 | 6000次/日 | BD-09 | https://lbsyun.baidu.com |

**AI 功能配置**（可选）:

```
AI_ENABLED=true
AI_PROVIDER=deepseek              # deepseek/qwen/glm/moonshot
DEEPSEEK_API_KEY=xxx              # 对应 API Key
```

## CLI 命令

### 分组结构

无参数运行启动交互式 TUI：

```bash
yaelocus                          # 启动 Ink TUI（优先）或 Rich TUI（回退）
```

#### geocode - 地理编码

```bash
yaelocus geocode single "北京市朝阳区"         # 单地址转换
yaelocus geocode single "天安门" --json        # JSON 输出
yaelocus geocode batch -i data/清单.xlsx       # 批量转换
yaelocus geocode batch -i data/清单.xlsx -w 5  # 5 线程并行
yaelocus geocode batch -i data/清单.xlsx -f xlsx --skip-cached
yaelocus geocode reverse 39.9 116.4            # 逆地理编码
yaelocus geocode reverse 39.9 116.4 --json
yaelocus geocode convert 39.9 116.4 --from gcj02 --to wgs84
yaelocus geocode convert 39.9 116.4 --from bd09 --to wgs84 --json
```

#### map - 地图与可视化

```bash
yaelocus map list                 # 列出 data/ 中可处理文件
yaelocus map list --detail        # 显示详细信息
yaelocus map create -i output/csv/结果.csv -t "我的地图"
```

#### ai - AI 功能

```bash
yaelocus ai chat "分析这些数据" -i output/csv/结果.csv
yaelocus ai analyze -i output/csv/结果.csv    # 数据分析
yaelocus ai route -i output/csv/结果.csv      # AI 路线规划
```

#### config - 配置管理

```bash
yaelocus config setup             # 交互式配置
yaelocus config check             # 环境诊断
yaelocus config test-api          # 测试 API 连通性
yaelocus config cache stats       # 缓存统计
yaelocus config cache stats --json
yaelocus config cache clear       # 清空缓存
yaelocus config cache cleanup     # 清理过期记录
yaelocus config cache export      # 导出缓存 JSON
```

#### serve - API 服务器

```bash
yaelocus serve                    # 启动 API 服务器 + Ink TUI
yaelocus serve --web              # 旧版 Web 界面
yaelocus serve --no-gui           # 仅 API 服务器

# Headless 模式（供前端调用）
python -m geocode.api --port 8765
python -m geocode.api --port 0    # 随机端口
```

### 向后兼容

旧命令自动重定向到新分组命令：

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

## Python API

```python
from geocode import Geocoder, CacheManager, create_map, ItineraryOptimizer

# 基础用法：上下文管理器自动关闭
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

# 地图可视化
valid = [r for r in results if r.get("success")]
create_map(valid, output_file="output/map/结果地图.html")

# 行程优化（DBSCAN 聚类 + TSP 求解）
optimizer = ItineraryOptimizer()
optimizer.analyze(valid)                # 聚类分析
routes = optimizer.recommend_routes()   # 多策略路线推荐

# AI 功能（可选模块）
from geocode import AIClient
client = AIClient()
response = client.chat("分析这些地点的分布特征", context=str(valid))
```

## TUI 双模式

无参数运行 `yaelocus` 时自动选择：

| 模式 | 技术 | 条件 |
|------|------|------|
| **Ink TUI** | React + Ink 5 + FastAPI | Node.js 可用 + tui/node_modules 存在 |
| **Rich TUI** | Python + Rich | 回退方案 |

**Ink TUI 特性**:
- 8 个组件: Messages, PromptInput, MapPicker, HelpPanel, Toast 等
- 4 个 hooks: useStream（SSE 流式）、useAPI、useCommandHistory、useTypeahead
- Agent Loop: 支持 `[CMD]...[/CMD]` 协议执行命令
- 端口协商: API server 启动时写入 `~/.yaelocus_port.json`

## 项目结构

```
geocode-tool/
├── geocode/                  # 核心模块
│   ├── __init__.py           # 公共 API 导出 (__version__ = "1.6.0")
│   ├── geocoder.py           # 地理编码核心
│   ├── cache.py              # SQLite 缓存（WAL + 延迟提交）
│   ├── config.py             # API 密钥 + OutputPaths
│   ├── coords.py             # 坐标转换（gcj02/bd09/wgs84）
│   ├── api.py                # FastAPI headless 服务器
│   ├── router.py             # RouteWizard 交互式向导
│   ├── map_visualizer.py     # Folium 地图生成
│   ├── models.py             # GeocodeResult, APILog dataclass
│   ├── errors.py             # GeocodeError 异常体系
│   │
│   ├── cli/                  # CLI 分组结构
│   │   ├── app.py            # Typer 入口 + 弃用别名
│   │   ├── groups.py         # 四组子命令定义
│   │   ├── repl.py           # Rich TUI (~1065 行)
│   │   ├── utils.py          # Console + CITY_COORDS
│   │   ├── completions.py    # 命令补全引擎
│   │   ├── theme.py          # TUI 语义化色彩
│   │   └── commands/         # 命令实现
│   │       ├── geocode.py    # single/batch/reverse/convert
│   │       ├── map.py        # list/create
│   │       ├── ai_.py        # chat/analyze/route
│   │       ├── config.py     # setup/check/test-api
│   │       ├── cache.py      # cache stats/clear/export/cleanup
│   │       └── serve.py      # API 服务器
│   │
│   ├── ai/                   # AI 模块（可选）
│   │   ├── client.py         # AIClient（流式/非流式）
│   │   ├── providers.py      # DeepSeek/Qwen/GLM/Moonshot
│   │   └── system_prompt.py  # TUI Agent 动态提示词
│   │
│   ├── routing/              # 路线规划
│   │   ├── models.py         # RoutePoint, RouteResult, TravelMode
│   │   ├── directions.py     # DirectionsClient（高德/百度）
│   │   ├── planner.py        # RoutePlanner
│   │   └── ai_engine.py      # AIDirectionEngine
│   │
│   ├── optimizer/            # 行程优化
│   │   ├── analyzer.py       # LocationAnalyzer（DBSCAN）
│   │   ├── planner.py        # RouteRecommender
│   │   ├── tsp.py            # TSP 求解器（贪心 + 2-opt）
│   │   └── models.py         # LocationCluster, RecommendedRoute
│   │
│   └── web/                  # 旧版 Web GUI
│       └── app.py            # 内联 HTML 模板
│
├── tui/                      # Ink TUI（React + Ink 5）
│   ├── package.json          # 依赖与构建脚本
│   ├── src/
│   │   └── index.tsx         # 入口组件
│   │   └── components/       # 8 个 UI 组件
│   │   └ hooks/              # 4 个 React hooks
│   └── dist/
│       └── index.js          # esbuild 打包输出
│
├── tests/                    # pytest 测试套件
├── data/                     # 输入数据目录
├── output/                   # 输出目录
│   ├── csv/                  # 转换结果
│   ├── map/                  # 地图 HTML
│   ├── database/             # SQLite 缓存
│   ├── log/                  # API 调用日志
│   └── export/               # 导出文件
│
├── skills/                   # Claude Code Skill
│   └── yaelocus.md           # AI 调用技能定义
├── install.bat               # Windows 一键安装
├── pyproject.toml            # 项目配置
├── CHANGELOG.md              # 更新日志
├── CLAUDE.md                 # Claude Code 项目指南
└── .env.example              # API 密钥模板
```

## API 服务器

FastAPI headless 服务，供 Ink TUI 或其他前端调用：

| 端点 | 说明 |
|------|------|
| `/api/health` | 健康检查 |
| `/api/config` | 配置信息 |
| `/api/geocode/single` | 单地址转换 |
| `/api/geocode/batch` | 批量转换 |
| `/api/geocode/reverse` | 逆地理编码 |
| `/api/geocode/convert` | 坐标转换 |
| `/api/chat` | AI 对话 |
| `/api/chat/stream` | SSE 流式 AI 对话 |
| `/api/cache/stats` | 缓存统计 |
| `/api/files` | 文件浏览 |
| `/api/execute` | 命令执行（TUI Agent 协议） |

## Claude Code Skill

本项目提供 Claude Code Skill，便于 AI 助手直接调用地理编码功能。

```bash
cp skills/yaelocus.md ~/.claude/skills/
```

**触发条件**: 地址转换、批量地理编码、经纬度查询、路线规划等。

## 常见问题

**Q: 首次运行找不到命令？**
```bash
pip install yaelocus
yaelocus config check
```

**Q: API 配额用完了？**
工具自动轮换三个 API，合计 21000 次/日。

**Q: Ink TUI 无法启动？**
```bash
cd tui && npm install && npm run build
```

**Q: 如何获取 API 密钥？**
- 高德: https://lbs.amap.com（注册 → 控制台 → 应用管理 → 创建应用 → 添加 Key）
- 天地图: https://www.tianditu.gov.cn（注册 → 开发资源 → 申请 Key）
- 百度: https://lbsyun.baidu.com（注册 → 控制台 → 创建应用）

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

# 更新日志

所有重要的变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.7.0] - 2026-06-05

### 新增
- **精确度级别检测**: 新增 `precision_level` 字段，省/市/区县级结果自动标记为不可信
- **智能重试策略**: 单地址编码时，首个 API 结果置信度不足会继续尝试其他 API 以获取最优结果
- **批量编码字段扩展**: 批量结果新增 `formatted_address`、省市区、精确度级别、状态等字段
- **CSV 写入安全机制**: 文件锁 + 重试（3次）+ 备用路径回退，避免并发写入冲突
- **缓存损坏恢复增强**: 损坏数据库自动备份（`.corrupted.{timestamp}`）后再重建

### 优化
- 高德/天地图/百度 API 现在均提取精确度级别信息（`level` 字段）
- `ConfidenceValidator` 新增 `formatted_address` 缺失检测
- 新增 `is_imprecise_result()` 工具函数供 API 模块调用
- 批量编码结果与原始 DataFrame 地址列精确匹配（不再依赖顺序）

### 修复
- 百度 API 结果现在正确提取省市区行政区划信息
- 缓存持久化线程异常处理增强，单次写入失败不会导致线程退出

## [1.6.0] - 2026-05-09

### 新增
- **Agent 集成模块** (`geocode/agent/`): JSON Schema 定义 + 错误恢复路径
- **HTTP API 端点**: `/api/schema`, `/api/errors` 供 AI Agent 查询
- **Skill 文件增强**: `skills/yaelocus.md` 完整 Agent 使用手册
- **发布版本拆分**: CLI-only 稳定版 vs 完整 Beta 版 (extras 分组)

### extras 分组
- `[ai]` - AI 功能 (httpx)
- `[web]` - Web API 服务器 (fastapi/uvicorn)
- `[beta]` - 完整 Beta 版 (AI + Web)
- `[dev]` - 开发测试工具

### 安装方式
```bash
pip install yaelocus              # CLI-only 稳定版
pip install "yaelocus[beta]"      # 完整 Beta 版
```

### 文档
- Skill 文件新增：工具检测、API Key 配置、完整命令参考、路径说明
- 错误恢复协议：Agent 可自动处理 `NO_API_KEY`, `COLUMN_NOT_FOUND` 等错误

## [1.5.0] - 2026-04-20

### 新增
- **命令分组重构**: `geocode`, `map`, `ai`, `config` 四组 Typer 子应用
- **TUI 双模式**: Ink TUI (React) + Rich TUI 回退
- **API 服务器**: FastAPI headless 服务器，Ink TUI 后端
- **AI 集成**: DeepSeek/Qwen/GLM/Moonshot 多供应商支持
- **路线规划**: `ai route` 交互式路线规划向导

### 变更
- 弃用旧扁平命令，自动重定向到新分组命令
- 入口点统一为 `yaelocus` (无参数启动 TUI)

## [1.4.0] - 2026-04-14

### 新增
- `--stdout-json` 参数：run 命令输出结构化 JSON，便于 AI 程序解析
- `--json/-j` 参数：cache stats 命令支持 JSON 输出
- 统一错误输出格式：JSON 结构化错误信息

### 优化
- HTTP Session 复用：减少 TCP 连接开销，性能提升 20-50%
- 重试机制：网络错误自动重试（最多 3 次，指数退避）
- 批量缓存预查询：`get_batch()` 方法减少数据库往返次数

### 变更
- `MAX_RETRIES` 配置从 1 改为 3

## [1.3.1] - 2026-04-14

### 变更
- PyPI 包名统一为 `yaelocus`
- 安装方式简化：`pip install yaelocus`

## [1.3.0] - 2026-04-13

### 新增
- 多格式输出支持：Excel (.xlsx)、JSON、GeoJSON (`-f` 参数)
- `quota` 命令：查看API配额使用情况
- `reverse` 命令：逆地理编码（经纬度转地址）
- `convert` 命令：坐标系转换工具
- `files` 命令：列出可处理的输入文件（支持 `-p` 指定目录、`--detail` 显示地址数量）
- `--skip-cached` 参数：断点续传/增量处理
- `--workers` 参数：并行请求处理（多线程）
- `wgs84_to_gcj02()` 坐标转换函数

### 变更
- run命令新增输出格式、并行处理、断点续传参数
- 输出逻辑重构，支持按格式/扩展名自动识别

## [1.2.0] - 2026-04-10

### 优化
- 重构缓存系统：单层SQLite，代码量减少60%（420行 -> 180行）
- 延迟提交优化：批量写入性能提升10倍+
- 添加数据库损坏自动恢复机制
- WAL模式 + mmap优化读取性能
- TTL缓存过期支持

### 文档
- 添加 MIT LICENSE
- 完善 README.md

## [1.1.0] - 2024-04-09

### 新增
- 支持TTL缓存过期
- 添加缓存统计功能
- 添加过期缓存清理命令

## [1.0.0] - 2024-04-01

### 新增
- 支持高德/百度/天地图三API智能轮换
- SQLite持久化缓存
- 坐标系统转换（GCJ-02/BD-09 -> WGS-84）
- folium交互式地图可视化
- CSV/Excel格式支持
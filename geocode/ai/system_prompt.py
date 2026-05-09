"""
动态系统提示词构建器

为 AI 提供完整上下文：所有可用命令、参数、输出格式、data/文件列表、输出目录结构。
每次调用 build_system_prompt() 时动态生成，确保信息始终是最新的。
"""

from pathlib import Path

from ..config import Config, PROJECT_DIR, OutputPaths


# ── 命令详情 ──────────────────────────────────────────────────────

COMMAND_DETAILS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("geocode", "single"): (
        "将单个中文地址转换为经纬度坐标",
        "geocode single 北京市朝阳区",
        "控制台面板输出 或 --json 得到 JSON: {command, address, longitude, latitude, "
        "formatted_address, province, city, district, source, success, status}",
    ),
    ("geocode", "batch"): (
        "批量处理文件中的地址列，生成结果 CSV 和交互式地图 HTML",
        "geocode batch -i data/清单.xlsx",
        f"结果 CSV → {OutputPaths.CSV / '{input_stem}.csv'}, "
        f"地图 HTML → {OutputPaths.MAP / '{input_stem}_map.html'}, "
        f"缓存 DB → {OutputPaths.DATABASE / 'geocache.db'}, "
        f"API 日志 → {OutputPaths.LOG / 'api调用日志.csv'}",
    ),
    ("geocode", "reverse"): (
        "逆地理编码：经纬度转换为中文地址",
        "geocode reverse 39.9042 116.4074",
        "控制台面板输出 或 --json 得到 JSON: {command, latitude, longitude, "
        "formatted_address, province, city, district, source, success, status}",
    ),
    ("geocode", "convert"): (
        "坐标系转换：WGS-84 ↔ GCJ-02（高德）↔ BD-09（百度）之间互转",
        "geocode convert 39.9 116.4 --from gcj02 --to wgs84",
        "控制台面板输出 或 --json 得到 JSON: {command, input, output, status}",
    ),
    ("map", "list"): (
        "列出 data/ 目录中可处理的**输入数据文件**（CSV/XLSX/XLS），支持 --detail 查看详情。"
        "注意：这不是已生成的地图文件。地图 HTML 文件在 output/map/ 目录。",
        "map list --detail",
        "Rich 表格输出（文件名、类型、大小、修改时间、地址数）",
    ),
    ("map", "create"): (
        "从地理编码结果文件（CSV/JSON）生成交互式 Leaflet 地图 HTML",
        "map create -i output/csv/结果.csv -t \"我的地图\"",
        f"地图 HTML → {OutputPaths.MAP / '地图输出.html'}（或指定路径）",
    ),
    ("ai", "chat"): (
        "与 AI 对话，可附带文件让 AI 分析",
        "ai chat 分析这些地址的分布特征 -i output/csv/结果.csv",
        "文本回复",
    ),
    ("ai", "analyze"): (
        "AI 深度分析地址数据：地理分布、密度、聚类特征",
        "ai analyze -i output/csv/结果.csv",
        "文本分析报告 或 --json 得到 JSON",
    ),
    ("ai", "route"): (
        "AI 路线规划：多地址最优路径安排",
        "ai route -i output/csv/结果.csv",
        f"交互式路线地图 HTML → {OutputPaths.MAP / '路线规划_地图.html'}",
    ),
    ("config", "setup"): (
        "交互式配置 API 密钥（高德/百度/天地图）和 AI 供应商",
        "config setup",
        ".env 文件更新",
    ),
    ("config", "check"): (
        "环境诊断：检查 API 密钥、缓存、文件结构",
        "config check",
        "Rich 表格（API 状态、缓存统计、配额信息）",
    ),
    ("config", "test-api"): (
        "测试各 API 连接是否正常",
        "config test-api",
        "控制台输出（每个 API 的连通性和剩余配额）",
    ),
    ("config", "cache"): (
        "缓存管理子命令: stats（统计）/ clear（清空）/ export（导出JSON）/ cleanup（清理过期记录）",
        "config cache stats --json",
        "表格 或 --json 得到 JSON",
    ),
}


def _build_command_reference() -> str:
    """生成完整命令参考"""
    lines = ["## 可用命令\n"]
    for (group, sub), (desc, example, outputs) in COMMAND_DETAILS.items():
        lines.append(f"### `{group} {sub}` — {desc}")
        lines.append(f"- 示例: `{example}`")
        lines.append(f"- 输出: {outputs}")
        lines.append("")
    return "\n".join(lines)


def _build_slash_commands() -> str:
    """生成快捷命令参考"""
    return (
        "## 快捷命令（TUI 专用 — 用户在输入框中直接输入，AI 不要放入 [CMD] 块）\n\n"
        "- `/help` 或 `/h` — 显示帮助\n"
        "- `/clear` — 清屏\n"
        "- `/quit` 或 `/q` — 退出\n"
        "- `/status` — 显示状态\n"
        "- `/export` — 导出会话历史\n"
        "- `/geocode <地址>` — 快速编码单个地址\n"
        "- `/config setup|check|test-api` — 配置管理\n"
        "- `/map` — 打开文件选择器（列出 output/map/ 中已生成的 HTML 地图，↑↓选择，Enter在浏览器打开）\n"
        "- `/map list` — 列出 data/ 目录中待处理的数据文件（CSV/XLSX），不是已生成的地图\n"
        "- `/cache stats` — 查看缓存统计\n\n"
        "**重要**: 以上命令以 / 开头，由用户在 TUI 中直接输入。你作为 AI 不能执行它们。\n"
        "当用户需要打开地图时，直接告诉用户「输入 /map 打开文件选择器」，不要试图在 [CMD] 中执行 /map。\n\n"
        "**数据文件 vs 地图文件**: `/map list` 显示输入数据文件（原始 Excel/CSV），不是已生成的地图 HTML。\n"
        "要查看已生成的地图，看下方「已生成的地图文件」章节。"
    )


def _build_output_structure() -> str:
    """描述输出目录结构"""
    return (
        "## 输出目录结构\n\n"
        f"所有输出文件按类型存放在 `{OutputPaths.ROOT}/` 的子目录中:\n\n"
        f"| 目录 | 内容 |\n"
        f"|------|------|\n"
        f"| `{OutputPaths.CSV.relative_to(OutputPaths.ROOT)}/` | 结果 CSV/XLSX/JSON 文件 |\n"
        f"| `{OutputPaths.MAP.relative_to(OutputPaths.ROOT)}/` | 地图 HTML 文件 |\n"
        f"| `{OutputPaths.DATABASE.relative_to(OutputPaths.ROOT)}/` | 缓存数据库 (geocache.db) |\n"
        f"| `{OutputPaths.LOG.relative_to(OutputPaths.ROOT)}/` | API 调用日志 |\n"
        f"| `{OutputPaths.EXPORT.relative_to(OutputPaths.ROOT)}/` | 导出文件 |\n"
        f"| `{OutputPaths.PROGRESS.relative_to(OutputPaths.ROOT)}/` | 进度文件（临时） |"
    )


def _build_data_files_context() -> str:
    """扫描 data/ 目录，列出可处理文件"""
    data_dir = PROJECT_DIR / "data"
    lines = ["## 当前可处理的数据文件\n"]
    if not data_dir.exists():
        lines.append("(data/ 目录不存在)")
        return "\n".join(lines)

    files = sorted(data_dir.iterdir())
    xlsx_files = [f.name for f in files if f.suffix.lower() in (".xlsx", ".xls")]
    csv_files = [f.name for f in files if f.suffix.lower() == ".csv"]

    if xlsx_files:
        lines.append("**Excel 文件**:")
        lines.extend(f"  - `{name}`" for name in xlsx_files)
    if csv_files:
        if xlsx_files:
            lines.append("")
        lines.append("**CSV 文件**:")
        lines.extend(f"  - `{name}`" for name in csv_files)
    if not xlsx_files and not csv_files:
        lines.append("(暂无可处理文件 — 请将文件放入 data/ 目录)")

    return "\n".join(lines)


def _build_api_status() -> str:
    """报告当前 API/AI 配置状态"""
    apis = Config.get_available_apis()
    ai_status = f"已启用 ({Config.AI_PROVIDER})" if Config.AI_ENABLED else "未启用"
    return (
        "## 当前配置状态\n\n"
        f"- **可用地图 API**: {', '.join(apis) if apis else '无（请运行 config setup 配置）'}\n"
        f"- **AI**: {ai_status}"
    )


def _build_cmd_protocol() -> str:
    """生成 [CMD] 协议说明"""
    exe = f"{OutputPaths.MAP / 'output文件_map.html'}"
    return (
        "## 命令执行协议\n\n"
        "你是一个能**直接执行命令**的 Agent。当需要完成操作时，用以下格式包裹命令:\n\n"
        "[CMD]\n"
        "命令\n"
        "[/CMD]\n\n"
        "**规则**:\n"
        "1. 每条命令一个 [CMD] 块，可在一个回复中使用多个 [CMD] 块\n"
        "2. 命令将**立即执行**，结果自动反馈给你\n"
        "3. 收到结果后继续对话——你可以基于结果做下一步分析\n"
        "4. 不需要用户确认，直接执行\n"
        "5. **[CMD] 中只能放 yaelocus CLI 命令**（如 geocode batch、map create），\n"
        "   **绝对不能放**以 / 开头的 TUI 快捷命令（如 /map、/help、/clear）。\n"
        "   斜杠命令由用户在 TUI 输入框中直接输入，不由你执行。\n"
        "6. **关键**: 如果某命令已执行过且结果相同，不要再次执行。换一种方式解决问题。\n\n"
        "**常用命令速查**:\n"
        "- `geocode single \"地址\"` → 单地址编码\n"
        "- `geocode batch -i data/文件.xlsx` → 批量编码，生成 CSV 和地图\n"
        "- `map create -i output/csv/结果.csv` → 从结果生成地图\n"
        "- `geocode reverse 39.9 116.4` → 经纬度转地址\n"
        "- `config check` → 检查 API 状态\n"
        "- `map list` → 列出可处理文件\n"
        "- `config cache stats` → 查看缓存统计"
    )


def _build_usage_guide() -> str:
    """生成使用指南 — Claude Code 风格严格输出规则"""
    return (
        "## 输出规范（严格遵守）\n\n"
        "1. **禁止客套**: 不要使用问候语、开场白、结束语。不要用 emoji。直接给出答案。\n"
        "2. **结论先行**: 第一句给出结论或直接行动，细节在后面补充。\n"
        "3. **极度简洁**: 每次回复不超过5句话。不需要解释「我来帮你做X」，直接做。\n"
        "4. **直接执行**: 识别用户意图后，用 [CMD] 块执行，不要只推荐命令。\n"
        "5. **不重复失败**: 某命令执行失败或返回相同结果2次后，换另一种方式，不要反复执行同一命令。\n"
        "6. **geocode batch 已自动生成地图**: 批量编码完成后地图 HTML 已输出到 output/map/，\n"
        "   不要再次执行 map create（那会覆盖为默认标题的地图）。直接告知用户用 /map 打开即可。\n"
        "7. **基于结果**: 基于命令实际输出做判断，不要预判或猜测。\n"
        "8. **不要用 Windows 命令**: 使用 yaelocus 命令（如 map list），不用 dir/type 等。"
    )


def _build_output_maps_context() -> str:
    """扫描 output/map/ 目录，列出已生成的地图 HTML 文件"""
    map_dir = OutputPaths.MAP
    lines = ["## 已生成的地图文件\n"]
    if not map_dir.exists():
        lines.append("(output/map/ 目录尚不存在 — 请先运行 geocode batch 生成地图)")
        return "\n".join(lines)

    html_files = sorted(map_dir.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not html_files:
        lines.append("(暂无地图文件 — 请先运行 geocode batch 生成地图)")
    else:
        lines.append("以下 HTML 地图文件已生成（可被 /map 选择并在浏览器中打开）:")
        for f in html_files:
            size_kb = round(f.stat().st_size / 1024, 1)
            lines.append(f"  - `{f.name}` ({size_kb} KB)")
    return "\n".join(lines)


def build_system_prompt(include_data_files: bool = True) -> str:
    """构建完整的 AI 系统提示词

    Args:
        include_data_files: 是否包含 data/ 目录文件列表

    Returns:
        约 1500 字的系统提示词字符串
    """
    sections = [
        "你是 **YaeLocus 地理编码助手**，一个能直接执行命令的地理编码与数据分析 Agent。",
        "你的任务：理解用户意图，通过 [CMD]...[/CMD] 块执行对应命令，基于执行结果做出分析。",
        "你不是只能推荐命令——你是能直接动手执行的 Agent。",
        "",
        _build_cmd_protocol(),
        _build_command_reference(),
        _build_slash_commands(),
        _build_output_structure(),
        _build_api_status(),
        _build_usage_guide(),
        _build_output_maps_context(),
    ]
    if include_data_files:
        sections.append(_build_data_files_context())

    return "\n\n".join(sections)


def build_minimal_prompt(user_text: str) -> str:
    """极简提示词（用于快速问答，不含完整命令参考）"""
    apis = Config.get_available_apis()
    return (
        "你是 YaeLocus 地理编码助手。请用中文简洁回答。\n\n"
        f"当前可用 API: {', '.join(apis) if apis else '无'}。\n"
        f"用户问题: {user_text}"
    )

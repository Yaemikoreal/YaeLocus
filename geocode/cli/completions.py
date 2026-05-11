"""
命令/文件路径 Tab 自动补全器

支持：
- 分组命令补全 (geocode/map/ai/config)
- 斜杠命令补全 (/help, /geocode, /config, etc.)
- 文件路径补全 (data/ 和 output/ 目录)
"""

from pathlib import Path
from typing import List, Optional, Tuple
from ..config import PROJECT_DIR, OutputPaths

# ── 命令树 ─────────────────────────────────────────────────────

_COMMAND_TREE = {
    "geocode": ["single", "batch", "reverse", "convert"],
    "map":     ["list", "create"],
    "ai":      ["chat", "analyze", "route"],
    "config":  ["setup", "check", "test-api", "cache"],
    "serve":   [],
}

_SLASH_COMMANDS = [
    "/help", "/h",
    "/clear",
    "/quit", "/q", "/exit",
    "/status",
    "/export",
    "/geocode ",
    "/config ",
    "/map ",
    "/cache ",
]


def _scan_directory(dir_path: Path) -> list[str]:
    if not dir_path.exists():
        return []
    patterns = [".csv", ".xlsx", ".xls", ".json", ".html"]
    files = []
    for f in dir_path.iterdir():
        if f.is_file() and f.suffix.lower() in patterns:
            files.append(f.name)
    return sorted(files)


def get_completions(text: str) -> list[str]:
    """返回补全候选列表"""
    if not text:
        completions = list(_COMMAND_TREE.keys())
        completions.extend(_SLASH_COMMANDS)
        return sorted(completions)

    # 斜杠命令补全
    if text.startswith("/"):
        prefix_lower = text.lower()
        candidates = []
        for sc in _SLASH_COMMANDS:
            if sc.startswith(prefix_lower) or sc.lower().startswith(prefix_lower):
                candidates.append(sc)
        if not candidates:
            candidates = [c for c in _SLASH_COMMANDS if prefix_lower in c.lower()]
        return sorted(candidates)

    parts = text.strip().split()

    # 文件路径补全 (检测 -i, -o, --input, --output, --cache 等)
    file_flags = ["-i", "--input", "-o", "--output", "-m", "--map", "--cache"]
    if len(parts) >= 2 and parts[-2] in file_flags:
        search_dir = OutputPaths.for_flag(parts[-2])
        prefix = parts[-1]
        return [f for f in _scan_directory(search_dir) if f.startswith(prefix)]

    # 分组命令补全
    if len(parts) == 1:
        prefix = parts[0].lower()
        candidates = []
        for cmd in _COMMAND_TREE:
            if cmd.startswith(prefix):
                candidates.append(cmd + " ")
        # Also check geocode single top-level
        if "geocode" in candidates:
            candidates[candidates.index("geocode ")] = "geocode single "
        return sorted(candidates)

    if len(parts) == 2:
        group = parts[0].lower()
        prefix = parts[1].lower()
        subcommands = _COMMAND_TREE.get(group, [])
        if subcommands:
            return [sc + " " for sc in subcommands if sc.startswith(prefix)]
        return []

    return []


def match_command(text: str) -> Optional[Tuple[str, str, List[str]]]:
    """匹配已注册命令

    Returns:
        (group, command, args_list) 或 None
    """
    parts = text.strip().split()
    if not parts:
        return None

    first = parts[0].lower()
    args = parts[1:]

    if first in ("/help", "/clear", "/quit", "/q", "/exit", "/status", "/export"):
        return ("_special", first[1:] if first[1:] != "q" else "quit", args)

    # /geocode addr → geocode single addr
    if first == "/geocode" and args:
        return ("geocode", "single", args)
    if first == "/config" and args:
        sub = args[0].lower()
        remain = args[1:]
        if sub in ("setup", "check", "test-api"):
            return ("config", sub, remain)
        if sub == "cache":
            cache_args = args[1:]
            return ("config", "cache", cache_args)
        return None
    if first == "/map" and args:
        sub = args[0].lower()
        if sub == "list":
            return ("map", "list", args[1:])
        return None

    if first in _COMMAND_TREE and args:
        second = args[0].lower()
        if second in _COMMAND_TREE[first]:
            return (first, second, args[1:])

    if first == "serve":
        return ("_standalone", "serve", args)

    return None


# ── 内联建议（ghost text）─────────────────────────────────────────────

def get_inline_suggestion(text: str) -> Optional[str]:
    """返回光标后应显示的 ghost text 后缀，或 None

    仅对 / 命令和已注册命令组生效。
    若恰好 1 个补全候选且以当前输入开头，返回剩余后缀。
    """
    if not text:
        return None

    completions = get_completions(text)
    if len(completions) != 1:
        return None

    suggestion = completions[0]
    # / 命令：保留尾部空格（如 /geocode ）
    if text.startswith("/") and suggestion.startswith(text):
        return suggestion[len(text):]
    # 常规命令组补全
    parts = text.strip().split()
    if len(parts) == 1:
        clean = suggestion.strip()
        if clean.startswith(parts[0]):
            return clean[len(parts[0]):]
    return None

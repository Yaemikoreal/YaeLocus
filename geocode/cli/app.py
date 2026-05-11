"""
CLI 主应用入口

创建 Typer app，注册命令分组，处理全局回调
"""

import sys

import typer

from .. import __version__
from .groups import ai_group, config_group, geocode_group, map_group, tui_group
from .utils import console, print_version, setup_windows_encoding

# Windows 编码兼容
setup_windows_encoding()


def _version_callback(value: bool):
    """--version / -V 回调"""
    if value:
        print_version(__version__)
        raise typer.Exit()


def _show_welcome():
    """显示欢迎界面：logo + 版本 + 常用命令"""
    from rich.table import Table

    # Logo - 简洁文本样式
    console.print()
    console.print("[bold cyan]YaeLocus[/bold cyan] [dim]v{}[/dim]".format(__version__))
    console.print("[dim]地址转经纬度 · AI 分析[/dim]")
    console.print()

    # 常用命令表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("命令", style="yellow")
    table.add_column("说明")
    table.add_row("yaelocus tui", "启动交互式终端界面")
    table.add_row("yaelocus gui", "启动新版 Web 图形界面")
    table.add_row("yaelocus geocode single <地址>", "单地址地理编码")
    table.add_row("yaelocus geocode batch -i <文件>", "批量地理编码")
    table.add_row("yaelocus config setup", "配置 API 密钥")
    table.add_row("yaelocus --help", "查看完整帮助")

    console.print(table)
    console.print()
    console.print("[dim]运行 'yaelocus tui' 进入交互模式，或使用上述命令直接操作[/dim]")


def _create_app() -> typer.Typer:
    """创建并配置 Typer 应用"""
    app = typer.Typer(
        name="yaelocus",
        help="地址转经纬度 | 路线规划 | AI 分析 | 行程优化",
        add_completion=False,
        no_args_is_help=False,  # 无参数时交给回调处理（显示欢迎界面）
    )

    # 全局回调
    @app.callback(invoke_without_command=True)
    def main_callback(
        ctx: typer.Context,
        version: bool = typer.Option(
            None, "--version", "-V",
            callback=_version_callback,
            is_eager=True,
            help="显示版本信息",
        ),
    ):
        """YaeLocus - 地址转经纬度 + 路线规划 + AI 分析"""
        if ctx.invoked_subcommand is None:
            # 无子命令 → 显示欢迎界面
            _show_welcome()

    # 注册分组
    app.add_typer(geocode_group)
    app.add_typer(map_group)
    app.add_typer(ai_group)
    app.add_typer(config_group)
    app.add_typer(tui_group)

    # 注册独立命令 (serve)
    from .commands.serve import register_serve
    register_serve(app)

    # 注册已弃用的扁平别名（向后兼容）
    _register_deprecated_aliases(app)

    return app


def _launch_repl():
    """启动交互式 TUI — 自动检测: Ink TUI > Rich TUI 回退"""
    import subprocess

    from ..config import PROJECT_DIR

    # 检查 web extras 是否安装（Ink TUI 需要启动 API server）
    try:
        from ..api import create_api_app  # noqa: F401
        has_web = True
    except ImportError:
        has_web = False

    tui_dir = PROJECT_DIR / "tui"
    tui_entry = tui_dir / "dist" / "index.js"
    tui_src = tui_dir / "src" / "index.tsx"
    node_modules = tui_dir / "node_modules"

    # 检查 Node.js 是否可用
    has_node = False
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        has_node = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Ink TUI 需要: web extras + Node.js + tui 依赖
    ink_ready = has_web and has_node and node_modules.exists() and (tui_entry.exists() or tui_src.exists())

    if ink_ready:
        _launch_ink_tui(PROJECT_DIR, tui_dir, tui_src, tui_entry)
    else:
        _launch_rich_fallback()


def _launch_ink_tui(project_dir, tui_dir, tui_src, tui_entry):
    """启动 Ink TUI + Python API sidecar"""
    import os
    import socket
    import subprocess
    import sys
    import time

    # 1. 找空闲端口
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()

    # 2. 启动 Python API server
    api_proc = subprocess.Popen(
        [sys.executable, '-m', 'geocode.api', '--port', str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(project_dir),
    )

    # 3. 等待 server 就绪
    import urllib.request
    for _ in range(15):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)

    # 4. 启动 Ink TUI
    env = os.environ.copy()
    env['YAELOCUS_PORT'] = str(port)

    entry = str(tui_src) if tui_src.exists() else str(tui_entry)
    if str(entry).endswith('.tsx'):
        # Use tsx to run TypeScript directly
        tsx_cmd = str(tui_dir / "node_modules" / ".bin" / "tsx.cmd") if sys.platform == 'win32' else str(tui_dir / "node_modules" / ".bin" / "tsx")
        cmd = [tsx_cmd, entry]
    else:
        cmd = ['node', entry]

    try:
        subprocess.run(cmd, cwd=str(tui_dir), env=env)
    except KeyboardInterrupt:
        pass
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()


def _launch_rich_fallback():
    """回退: 使用旧版 Rich TUI 或纯文本提示"""
    try:
        from .repl import ReplSession
        session = ReplSession()
        session.run()
    except ImportError:
        console.print("[yellow]交互式 TUI 需要 Node.js 和 tui/ 依赖[/yellow]")
        console.print("[dim]安装: cd tui && npm install && npm run build[/dim]")
        console.print("[dim]或直接使用 CLI 命令: yaelocus --help[/dim]")
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print("\n[dim]已退出[/dim]")
        raise typer.Exit(0) from None


def _register_deprecated_aliases(app: typer.Typer):
    """注册向后兼容的弃用别名"""

    @app.command("run", hidden=True)
    def _deprecated_run(
        input: str = typer.Option(..., "-i", "--input", help="输入文件路径"),
        column: str = typer.Option("地址", "-c", "--column", help="地址列名"),
        output: str = typer.Option(None, "-o", "--output", help="输出文件路径"),
        map_file: str = typer.Option(None, "-m", "--map", help="地图输出路径"),
        cache_file: str = typer.Option(None, "--cache", help="缓存数据库路径"),
        ttl: int = typer.Option(None, "--ttl", help="缓存有效期（秒）"),
        batch_size: int = typer.Option(100, "--batch-size"),
        cleanup: bool = typer.Option(False, "--cleanup"),
        no_cluster: bool = typer.Option(False, "--no-cluster"),
        no_heatmap: bool = typer.Option(False, "--no-heatmap"),
        output_format: str = typer.Option("csv", "-f", "--format"),
        skip_cached: bool = typer.Option(True, "--skip-cached/--no-skip-cached"),
        workers: int = typer.Option(1, "-w", "--workers"),
        verbose: bool = typer.Option(False, "-v", "--verbose"),
        stdout_json: bool = typer.Option(False, "--stdout-json"),
        json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
    ):
        """[DEPRECATED] 请使用 yaelocus geocode batch"""
        sys.stderr.write("[DEPRECATED] yaelocus run → 请改用 yaelocus geocode batch\n")
        from .commands.geocode import batch
        batch(
            input=input, column=column, output=output, map_file=map_file,
            cache_file=cache_file, ttl=ttl, batch_size=batch_size, cleanup=cleanup,
            no_cluster=no_cluster, no_heatmap=no_heatmap, output_format=output_format,
            skip_cached=skip_cached, workers=workers, verbose=verbose,
            stdout_json=stdout_json or json_output,
        )

    @app.command("geocode", hidden=True)
    def _deprecated_geocode_single(
        address: str = typer.Argument(..., help="要转换的地址"),
        cache_file: str = typer.Option(None, "--cache"),
        ttl: int = typer.Option(None, "--ttl"),
        json_output: bool = typer.Option(False, "--json", "-j"),
    ):
        """[DEPRECATED] 请使用 yaelocus geocode single"""
        sys.stderr.write("[DEPRECATED] yaelocus geocode → 请改用 yaelocus geocode single\n")
        from .commands.geocode import single
        single(address=address, cache_file=cache_file, ttl=ttl, json_output=json_output)

    @app.command("reverse", hidden=True)
    def _deprecated_reverse(
        lat: float = typer.Argument(...),
        lon: float = typer.Argument(...),
        cache_file: str = typer.Option(None, "--cache"),
        ttl: int = typer.Option(None, "--ttl"),
        json_output: bool = typer.Option(False, "--json", "-j"),
    ):
        """[DEPRECATED] 请使用 yaelocus geocode reverse"""
        sys.stderr.write("[DEPRECATED] yaelocus reverse → 请改用 yaelocus geocode reverse\n")
        from .commands.geocode import reverse_cmd
        reverse_cmd(lat=lat, lon=lon, cache_file=cache_file, ttl=ttl, json_output=json_output)

    @app.command("convert", hidden=True)
    def _deprecated_convert(
        lat: float = typer.Argument(...),
        lon: float = typer.Argument(...),
        from_sys: str = typer.Option("wgs84", "--from"),
        to_sys: str = typer.Option("gcj02", "--to"),
        json_output: bool = typer.Option(False, "--json", "-j"),
    ):
        """[DEPRECATED] 请使用 yaelocus geocode convert"""
        sys.stderr.write("[DEPRECATED] yaelocus convert → 请改用 yaelocus geocode convert\n")
        from .commands.geocode import convert_cmd
        convert_cmd(lat=lat, lon=lon, from_sys=from_sys, to_sys=to_sys, json_output=json_output)

    @app.command("doctor", hidden=True)
    def _deprecated_doctor():
        """[DEPRECATED] 请使用 yaelocus config check"""
        sys.stderr.write("[DEPRECATED] yaelocus doctor → 请改用 yaelocus config check\n")
        from .commands.config import check
        check()

    @app.command("files", hidden=True)
    def _deprecated_files(
        path: str = typer.Option(None, "-p", "--path"),
        detail: bool = typer.Option(False, "-d", "--detail"),
    ):
        """[DEPRECATED] 请使用 yaelocus map list"""
        sys.stderr.write("[DEPRECATED] yaelocus files → 请改用 yaelocus map list\n")
        from .commands.map import list_files_cmd
        list_files_cmd(path=path, detail=detail)

    @app.command("cache", hidden=True)
    def _deprecated_cache(
        action: str = typer.Argument(..., help="操作: stats|clear|export|cleanup"),
        cache_file: str = typer.Option(None, "--cache"),
        json_output: bool = typer.Option(False, "--json", "-j"),
    ):
        """[DEPRECATED] 请使用 yaelocus config cache"""
        sys.stderr.write("[DEPRECATED] yaelocus cache → 请改用 yaelocus config cache\n")
        from .commands.cache import cache_cmd
        cache_cmd(action=action, cache_file=cache_file, json_output=json_output)

    @app.command("ai", hidden=True)
    def _deprecated_ai(
        message: str = typer.Argument(..., help="发送给 AI 的消息"),
        input_file: str = typer.Option(None, "-i", "--input"),
        system: str = typer.Option("", "--system"),
        provider: str = typer.Option("", "--provider"),
        model: str = typer.Option("", "--model"),
        json_output: bool = typer.Option(False, "--json", "-j"),
    ):
        """[DEPRECATED] 请使用 yaelocus ai chat"""
        sys.stderr.write("[DEPRECATED] yaelocus ai → 请改用 yaelocus ai chat\n")
        from .commands.ai_ import chat
        chat(message=message, input_file=input_file, system=system,
             provider=provider, model=model, json_output=json_output)

    @app.command("test-api", hidden=True)
    def _deprecated_test_api():
        """[DEPRECATED] 请使用 yaelocus config test-api"""
        sys.stderr.write("[DEPRECATED] yaelocus test-api → 请改用 yaelocus config test-api\n")
        from .commands.config import test_api
        test_api()

    @app.command("config", hidden=True)
    def _deprecated_config():
        """[DEPRECATED] 请使用 yaelocus config setup"""
        sys.stderr.write("[DEPRECATED] yaelocus config → 请改用 yaelocus config setup\n")
        from .commands.config import setup
        setup()

    @app.command("route", hidden=True)
    def _deprecated_route(
        input_file: str = typer.Option(..., "-i", "--input", help="地理编码结果文件"),
        map_file: str = typer.Option(None, "-o", "--output", help="输出地图路径"),
    ):
        """[DEPRECATED] 请使用 yaelocus ai route"""
        sys.stderr.write("[DEPRECATED] yaelocus route → 请改用 yaelocus ai route\n")
        from .commands.ai_ import route
        route(input_file=input_file, map_file=map_file)

    @app.command("quota", hidden=True)
    def _deprecated_quota():
        """[DEPRECATED] 请使用 yaelocus config check"""
        sys.stderr.write("[DEPRECATED] yaelocus quota → 请使用 yaelocus config check\n")
        from .commands.config import _legacy_quota
        _legacy_quota()


# 创建 app 实例（供 pyproject.toml 入口点引用）
app = _create_app()

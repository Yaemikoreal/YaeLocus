"""
服务命令：启动 API 服务器 / Web GUI
"""

import json
import signal
import socket
import subprocess
import sys
from pathlib import Path

import typer

from ..utils import console
from ... import __version__
from ...config import PROJECT_DIR

# 端口文件路径
_PORT_FILE = Path.home() / ".yaelocus_port.json"


def _find_available_port(host: str, start_port: int, max_attempts: int = 10) -> int:
    """尝试找到可用端口，优先递增端口

    Args:
        host: 监听地址
        start_port: 起始端口
        max_attempts: 最大尝试次数

    Returns:
        可用的端口号
    """
    # 尝试递增端口
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue

    # 全部失败，使用随机端口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _cleanup_port_file() -> None:
    """清理端口文件"""
    try:
        if _PORT_FILE.exists():
            _PORT_FILE.unlink()
    except Exception:
        pass


def _signal_handler(signum, frame) -> None:
    """处理 Ctrl+C 信号"""
    console.print("\n[yellow]正在停止服务...[/yellow]")
    _cleanup_port_file()
    sys.exit(0)


def _ensure_frontend_built(web_gui_dir: Path) -> None:
    """检测并自动构建前端（首次运行或源码有更新时触发）

    Args:
        web_gui_dir: web_gui 目录路径
    """
    dist_index = web_gui_dir / "dist" / "index.html"
    node_modules = web_gui_dir / "node_modules"
    package_json = web_gui_dir / "package.json"

    # 1. 检查 Node.js
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True, shell=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]未检测到 Node.js，Web GUI 需要 Node.js 运行时[/red]")
        console.print("[dim]请安装 Node.js: https://nodejs.org/[/dim]")
        console.print("[dim]或使用旧版: yaelocus serve[/dim]")
        raise typer.Exit(1)

    need_install = not node_modules.exists()
    need_build = not dist_index.exists()

    # 2. 检查是否需要构建（源码比 dist 新）
    if not need_build:
        dist_mtime = dist_index.stat().st_mtime
        src_dir = web_gui_dir / "src"
        if src_dir.exists():
            for f in src_dir.rglob("*"):
                if f.is_file() and f.stat().st_mtime > dist_mtime:
                    need_build = True
                    break
        # 也检查 package.json 是否更新
        if package_json.stat().st_mtime > dist_mtime:
            need_build = True

    if not need_install and not need_build:
        return  # 已是最新，秒级跳过

    console.print()
    console.print("[bold cyan]前端构建[/bold cyan]")

    # 3. npm install
    if need_install:
        console.print(f"[dim]安装前端依赖... ({node_modules} 不存在)[/dim]")
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=str(web_gui_dir),
                check=True,
                shell=True,
            )
        except subprocess.CalledProcessError:
            console.print("[red]npm install 失败，请检查 npm 是否已安装[/red]")
            console.print("[dim]可手动执行: cd web_gui && npm install[/dim]")
            raise typer.Exit(1)

    # 4. npm run build
    if need_build or need_install:
        reason = "dist 过期" if need_build else "首次构建"
        console.print(f"[dim]编译前端... ({reason})[/dim]")
        try:
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(web_gui_dir),
                check=True,
                shell=True,
            )
        except subprocess.CalledProcessError:
            console.print("[red]前端构建失败，请检查错误信息[/red]")
            console.print(f"[dim]可手动执行: cd {web_gui_dir} && npm run build[/dim]")
            raise typer.Exit(1)

    console.print("[green]前端构建完成[/green]")
    console.print()


def register_serve(app: typer.Typer):
    """在 app 上注册 serve / gui 命令"""

    @app.command("serve")
    def serve_command(
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
        port: int = typer.Option(8765, "--port", "-p", help="监听端口"),
        no_gui: bool = typer.Option(False, "--no-gui", help="仅启动 API 服务器（不打开浏览器）"),
    ):
        """启动 API 服务器

        启动 FastAPI 服务器，提供 REST API 和 Web GUI（需构建前端）。
        新版 React GUI: yaelocus gui

        示例:
            yaelocus serve
            yaelocus serve -p 8080
            yaelocus serve --no-gui
        """
        try:
            from ...api import create_api_app
        except ImportError as e:
            console.print(f"[red]API 依赖未安装: {e}[/red]")
            console.print("[dim]请运行: pip install yaelocus[web][/dim]")
            raise typer.Exit(1)

        # 注册信号处理器（Windows 只支持 SIGINT）
        signal.signal(signal.SIGINT, _signal_handler)

        # 检测端口可用性
        actual_port = _find_available_port(host, port)
        if actual_port != port:
            console.print(f"[yellow]端口 {port} 已被占用，切换到端口 {actual_port}[/yellow]")

        # 写入端口文件
        try:
            _PORT_FILE.write_text(json.dumps({"port": actual_port, "host": host}))
        except Exception:
            pass

        console.print(f"[bold cyan]YaeLocus[/bold cyan] [dim]v{__version__}[/dim]")
        console.print(f"[dim]API 服务器:[/dim] [bold]http://{host}:{actual_port}[/bold]")
        console.print("[dim]按 Ctrl+C 停止[/dim]")
        console.print()

        import uvicorn
        import threading
        import webbrowser

        if not no_gui:
            threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{actual_port}")).start()

        app = create_api_app()
        try:
            uvicorn.run(app, host=host, port=actual_port, log_level="warning")
        finally:
            _cleanup_port_file()

    @app.command("gui")
    def gui_command(
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
        port: int = typer.Option(8765, "--port", "-p", help="监听端口"),
        no_open: bool = typer.Option(False, "--no-open", help="不自动打开浏览器"),
    ):
        """启动新版 Web GUI（React SPA）

        启动 FastAPI 服务器并提供新版 React 前端界面。
        首次使用需先构建前端: cd web_gui && npm install && npm run build

        示例:
            yaelocus gui
            yaelocus gui -p 8080
            yaelocus gui --no-open
        """
        # 自动检测并构建前端（首次运行或源码有更新时触发）
        _ensure_frontend_built(PROJECT_DIR / "web_gui")

        try:
            from ...api import create_api_app
        except ImportError as e:
            console.print(f"[red]API 依赖未安装: {e}[/red]")
            console.print("[dim]请运行: pip install fastapi uvicorn[/dim]")
            raise typer.Exit(1)

        # 注册信号处理器（Windows 只支持 SIGINT）
        signal.signal(signal.SIGINT, _signal_handler)

        # 检测端口可用性
        actual_port = _find_available_port(host, port)
        if actual_port != port:
            console.print(f"[yellow]端口 {port} 已被占用，切换到端口 {actual_port}[/yellow]")

        # 写入端口文件
        try:
            _PORT_FILE.write_text(json.dumps({"port": actual_port, "host": host}))
        except Exception:
            pass

        console.print()
        console.print(f"[bold cyan]YaeLocus[/bold cyan] [dim]v{__version__}[/dim]")
        console.print(f"[dim]新版 Web GUI:[/dim] [bold]http://{host}:{actual_port}[/bold]")
        console.print("[dim]按 Ctrl+C 停止[/dim]")
        console.print()

        import uvicorn
        import threading
        import webbrowser

        if not no_open:
            threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{actual_port}")).start()

        app = create_api_app()
        try:
            uvicorn.run(app, host=host, port=actual_port, log_level="warning")
        finally:
            _cleanup_port_file()

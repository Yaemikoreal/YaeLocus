"""
服务命令：启动 API 服务器 / Web GUI
"""

import subprocess
from pathlib import Path

import typer

from ..utils import console
from ... import __version__
from ...config import PROJECT_DIR


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
        subprocess.run(["node", "--version"], capture_output=True, check=True)
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
        """启动 API 服务器（旧版 Web GUI）

        默认启动 FastAPI 服务器并在浏览器中打开旧版 Web GUI。
        使用 --no-gui 仅启动服务器不打开浏览器。

        新版 GUI 请使用: yaelocus gui

        示例:
            yaelocus serve
            yaelocus serve -p 8080
            yaelocus serve --no-gui
        """
        try:
            from ...web import run_server
        except ImportError as e:
            console.print(f"[red]Web GUI 依赖未安装: {e}[/red]")
            console.print("[dim]请运行: pip install fastapi uvicorn[/dim]")
            raise typer.Exit(1)

        console.print(f"[bold blue]YaeLocus[/bold blue] [dim]v{__version__}[/dim]")
        if no_gui:
            console.print(f"[dim]API 服务器: http://{host}:{port}[/dim]")
            console.print("[dim]按 Ctrl+C 停止[/dim]")
            run_server(host=host, port=port, open_browser=False)
        else:
            console.print(f"[dim]旧版 Web GUI: http://{host}:{port}[/dim]")
            console.print("[dim]按 Ctrl+C 停止[/dim]")
            run_server(host=host, port=port, open_browser=True)

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

        console.print()
        console.print(f"[bold cyan]YaeLocus[/bold cyan] [dim]v{__version__}[/dim]")
        console.print(f"[dim]新版 Web GUI:[/dim] [bold]http://{host}:{port}[/bold]")
        console.print("[dim]按 Ctrl+C 停止[/dim]")
        console.print()

        import uvicorn
        import threading
        import webbrowser

        if not no_open:
            threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}")).start()

        app = create_api_app()
        uvicorn.run(app, host=host, port=port, log_level="warning")

"""
服务命令：启动 API 服务器 / Web GUI
"""

import typer

from ..utils import console
from ... import __version__
from ...config import PROJECT_DIR


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
        import sys
        from pathlib import Path

        # 检查前端是否已构建
        web_gui_dist = PROJECT_DIR / "web_gui" / "dist"
        index_html = web_gui_dist / "index.html"

        if not index_html.exists():
            console.print()
            console.print("[bold yellow]前端尚未构建[/bold yellow]")
            console.print()
            console.print("[dim]新版 Web GUI 是基于 React + TypeScript 的单页应用，[/dim]")
            console.print("[dim]首次使用前需要构建前端资源：[/dim]")
            console.print()
            console.print(f"  [bold]cd {PROJECT_DIR / 'web_gui'}[/bold]")
            console.print("  [bold]npm install[/bold]")
            console.print("  [bold]npm run build[/bold]")
            console.print()
            console.print("[dim]构建完成后再次运行: yaelocus gui[/dim]")
            console.print()
            console.print("[dim]开发模式（支持热更新）: cd web_gui && npm run dev[/dim]")
            raise typer.Exit(1)

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

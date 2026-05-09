"""
服务命令：启动 API 服务器 / Web GUI
"""

import typer

from ..utils import console
from ... import __version__
from ...config import PROJECT_DIR


def register_serve(app: typer.Typer):
    """在 app 上注册 serve 命令"""

    @app.command("serve")
    def serve_command(
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
        port: int = typer.Option(8765, "--port", "-p", help="监听端口"),
        no_gui: bool = typer.Option(False, "--no-gui", help="仅启动 API 服务器（不打开浏览器）"),
    ):
        """启动 API 服务器

        默认启动 FastAPI 服务器并在浏览器中打开 Web GUI。
        使用 --no-gui 仅启动服务器不打开浏览器。

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
            console.print(f"[dim]Web GUI: http://{host}:{port}[/dim]")
            console.print("[dim]按 Ctrl+C 停止[/dim]")
            run_server(host=host, port=port, open_browser=True)

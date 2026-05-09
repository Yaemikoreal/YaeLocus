"""
缓存管理命令
"""

import json
import sqlite3
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from ..utils import console, OK, FAIL, resolve_path
from ...config import OutputPaths
from ...cache import CacheManager


def cache_cmd(
    action: str = typer.Argument(..., help="操作: stats|clear|export|cleanup"),
    cache_file: Path = typer.Option(None, "--cache", help="缓存数据库文件"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
):
    """缓存管理

    示例:
        yaelocus config cache stats
        yaelocus config cache clear
        yaelocus config cache stats --json
    """
    cache_path = resolve_path(str(cache_file) if cache_file else str(OutputPaths.DATABASE / "geocache.db"))

    if not cache_path.exists():
        console.print(f"[red]{FAIL} 缓存文件不存在: {cache_path}[/red]")
        raise typer.Exit(1)

    cache_manager = CacheManager(cache_file=str(cache_path))

    if action == "stats":
        stats = cache_manager.get_stats()
        if json_output:
            output = {
                "command": "cache_stats",
                "stats": {
                    "total_entries": stats['total_entries'],
                    "hits": stats['hits'],
                    "misses": stats['misses'],
                    "hit_rate": stats['hit_rate'],
                    "pending_writes": stats['pending_writes'],
                    "expired_entries": stats['expired_entries'],
                },
                "status": "success",
            }
            print(json.dumps(output, ensure_ascii=False))
        else:
            table = Table(title="缓存统计", show_header=True, header_style="bold cyan")
            table.add_column("指标", style="cyan")
            table.add_column("数值", justify="right")
            table.add_row("缓存条目", str(stats['total_entries']))
            table.add_row("命中次数", str(stats['hits']))
            table.add_row("未命中次数", str(stats['misses']))
            table.add_row("命中率", f"{stats['hit_rate']}%")
            table.add_row("待写入", str(stats['pending_writes']))
            table.add_row("过期条目", str(stats['expired_entries']))
            console.print(table)

    elif action == "clear":
        count = cache_manager.count()
        cache_manager.clear()
        cache_manager.close()
        console.print(f"[green]{OK}[/green] 已清空 {count} 条缓存")

    elif action == "cleanup":
        cleaned = cache_manager.cleanup()
        cache_manager.close()
        console.print(f"[green]{OK}[/green] 清理过期缓存: {cleaned} 条")

    elif action == "export":
        export_path = resolve_path(str(OutputPaths.EXPORT / "cache_export.json"))
        conn = sqlite3.connect(str(cache_path))
        rows = conn.execute("SELECT address, data, created_at, source FROM cache").fetchall()
        data = [{"address": r[0], "result": json.loads(r[1]), "created": r[2], "source": r[3]} for r in rows]
        conn.close()
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"[green]{OK}[/green] 已导出 {len(data)} 条缓存到 {export_path}")

    else:
        console.print(f"[red]{FAIL} 未知操作: {action}[/red]")
        console.print("可用操作: stats, clear, cleanup, export")
        cache_manager.close()
        raise typer.Exit(1)

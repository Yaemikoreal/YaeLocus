"""
地图命令：列出文件、生成地图
"""

import json
import os
from pathlib import Path

import typer
import pandas as pd
from rich.panel import Panel
from rich.table import Table

from ..utils import console, OK, FAIL, resolve_path
from ...config import PROJECT_DIR, OutputPaths
from ...map_visualizer import create_map


def list_files_cmd(
    path: Path = typer.Option(None, "-p", "--path", help="指定目录路径"),
    detail: bool = typer.Option(False, "-d", "--detail", help="显示详细信息"),
):
    """列出可处理的输入文件

    示例:
        yaelocus map list
        yaelocus map list -p output/ --detail
    """
    from datetime import datetime

    dir_path = resolve_path(str(path)) if path else PROJECT_DIR / "data"

    console.print(Panel.fit(
        f"[bold cyan]可处理文件列表[/bold cyan]\n[dim]目录: {dir_path}[/dim]",
        border_style="cyan"
    ))

    if not dir_path.exists():
        console.print(f"[red]{FAIL} 目录不存在: {dir_path}[/red]")
        raise typer.Exit(1)

    supported_extensions = [".csv", ".xlsx", ".xls"]
    files_list = []

    for file_path in sorted(dir_path.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            file_stat = file_path.stat()
            size_kb = file_stat.st_size / 1024
            mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            address_count = None
            if detail:
                try:
                    suffix = file_path.suffix.lower()
                    if suffix in [".xlsx", ".xls"]:
                        df = pd.read_excel(file_path, engine="openpyxl" if suffix == ".xlsx" else "xlrd")
                    else:
                        df = pd.read_csv(file_path, encoding="utf-8-sig")
                    address_col = None
                    for col in df.columns:
                        if "地址" in col.lower():
                            address_col = col
                            break
                    address_count = df[address_col].dropna().astype(str).count() if address_col else df.shape[0]
                except Exception:
                    address_count = "无法读取"

            files_list.append({
                "name": file_path.name,
                "type": file_path.suffix.upper().lstrip("."),
                "size": f"{size_kb:.1f} KB",
                "modified": mod_time,
                "count": address_count,
            })

    if not files_list:
        console.print("[yellow]目录中没有可处理的文件[/yellow]")
        return

    tbl = Table(show_header=True, header_style="bold cyan")
    tbl.add_column("文件名", style="cyan")
    tbl.add_column("类型", justify="center")
    tbl.add_column("大小", justify="right")
    tbl.add_column("修改时间", justify="center")
    if detail:
        tbl.add_column("地址数", justify="right")

    for f in files_list:
        if detail:
            count_str = str(f["count"]) if f["count"] is not None else "-"
            tbl.add_row(f["name"], f["type"], f["size"], f["modified"], count_str)
        else:
            tbl.add_row(f["name"], f["type"], f["size"], f["modified"])

    if os.environ.get('YAELOCUS_TUI'):
        # TUI 模式 — 纯文本简洁输出
        console.print(f"共 {len(files_list)} 个文件")
        for f in files_list:
            detail_str = f" | {f['count']}条" if detail and f.get('count') is not None else ""
            console.print(f"  {f['name']} ({f['size']}{detail_str})")
    else:
        console.print(tbl)
        console.print(f"\n[green]共 {len(files_list)} 个可处理文件[/green]")
        if files_list:
            console.print(f"\n[dim]提示: 使用 'geocode batch -i data/{files_list[0]['name']}' 开始处理[/dim]")


def create(
    input_file: Path = typer.Option(..., "-i", "--input", help="地理编码结果文件 (CSV/JSON)"),
    output: Path = typer.Option(str(OutputPaths.MAP / "地图输出.html"), "-o", "--output", help="输出地图路径"),
    title: str = typer.Option("地址分布地图", "-t", "--title", help="地图标题"),
    no_cluster: bool = typer.Option(False, "--no-cluster", help="禁用点聚类"),
    no_heatmap: bool = typer.Option(False, "--no-heatmap", help="禁用热力图"),
):
    """从结果文件生成地图

    示例:
        yaelocus map create -i output/结果.csv
        yaelocus map create -i output/结果.json -t "我的地图"
    """
    input_path = resolve_path(str(input_file))
    if not input_path.exists():
        console.print(f"[red]{FAIL} 文件不存在: {input_path}[/red]")
        raise typer.Exit(1)

    # 加载数据
    try:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            first_char = f.read(1)
            f.seek(0)
            if first_char == "[":
                data = json.load(f)
                results = [r for r in data if r.get("success") or r.get("状态") == "成功"]
            elif first_char == "{":
                loaded = json.load(f)
                results = loaded.get("results", [loaded])
            else:
                raise ValueError("无法识别的 JSON 格式")
    except (json.JSONDecodeError, ValueError):
        try:
            df = pd.read_csv(input_path, encoding="utf-8-sig")
            results = []
            for _, row in df.iterrows():
                status = row.get("状态", "成功")
                if status == "成功":
                    results.append({
                        "original_address": str(row.get("原始地址", "")),
                        "formatted_address": str(row.get("标准化地址", "")),
                        "latitude": float(row.get("纬度", 0)),
                        "longitude": float(row.get("经度", 0)),
                        "source": str(row.get("数据来源", "")),
                        "coordinate_system": str(row.get("坐标系", "")),
                        "success": True,
                    })
        except Exception as e:
            console.print(f"[red]{FAIL} 读取文件失败: {e}[/red]")
            raise typer.Exit(1)

    if not results:
        console.print(f"[yellow]没有有效的坐标数据[/yellow]")
        raise typer.Exit(1)

    output_path = resolve_path(str(output))
    map_path = create_map(
        data=results,
        output_file=str(output_path),
        title=title,
        use_cluster=not no_cluster,
        use_heatmap=not no_heatmap,
    )
    console.print(f"[green]{OK} 地图已生成:[/green] {map_path}")
    console.print(f"  [dim]共 {len(results)} 个点位[/dim]")

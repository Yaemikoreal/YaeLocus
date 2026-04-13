"""
现代化 CLI 入口

使用 Typer + Rich 提供彩色输出和现代交互体验

Windows兼容: 使用ASCII符号替代Unicode符号
"""

import sys
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from . import __version__
from .cache import CacheManager
from .config import Config, PROJECT_DIR
from .errors import NO_API_KEY, FILE_NOT_FOUND, COLUMN_NOT_FOUND
from .geocoder import Geocoder
from .logger import APILogger
from .map_visualizer import create_map

# Windows兼容: 设置UTF-8环境
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = typer.Typer(
    name="YaeLocus",
    help="地址转经纬度 + 地图标注工具",
    add_completion=False
)
console = Console(force_terminal=True)

# ASCII符号替代Unicode（Windows兼容）
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def resolve_path(file_path: str) -> Path:
    """解析路径，相对路径基于项目根目录"""
    path = Path(file_path)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def print_version(value: bool):
    """打印版本信息"""
    if value:
        console.print(Panel.fit(
            f"[bold blue]YaeLocus[/bold blue] [dim]v{__version__}[/dim]\n"
            f"[dim]地址转经纬度工具[/dim]",
            border_style="blue"
        ))
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None, "--version", "-V",
        callback=print_version,
        is_eager=True,
        help="显示版本信息"
    )
):
    """地址转经纬度 + 地图标注工具"""
    pass


@app.command()
def run(
    input: Path = typer.Option(
        ...,
        "-i", "--input",
        help="输入文件路径，支持 CSV/XLSX/XLS 格式"
    ),
    column: str = typer.Option(
        "地址",
        "-c", "--column",
        help="地址列名，默认为'地址'"
    ),
    output: Path = typer.Option(
        None,
        "-o", "--output",
        help="输出文件路径，默认 output/地址_经纬度_结果.csv"
    ),
    map_file: Path = typer.Option(
        None,
        "-m", "--map",
        help="地图输出路径，默认 output/地图输出.html"
    ),
    cache_file: Path = typer.Option(
        None,
        "--cache",
        help="缓存数据库路径，默认 output/geocache.db"
    ),
    ttl: int = typer.Option(
        None,
        "--ttl",
        help="缓存有效期（秒），默认永久有效"
    ),
    batch_size: int = typer.Option(
        100,
        "--batch-size",
        help="缓存批量写入阈值，默认 100"
    ),
    cleanup: bool = typer.Option(
        False,
        "--cleanup",
        help="运行前清理过期缓存"
    ),
    no_cluster: bool = typer.Option(
        False,
        "--no-cluster",
        help="地图禁用点聚类功能"
    ),
    no_heatmap: bool = typer.Option(
        False,
        "--no-heatmap",
        help="地图禁用热力图功能"
    ),
    output_format: str = typer.Option(
        "csv",
        "-f", "--format",
        help="输出格式: csv|xlsx|json|geojson"
    ),
    skip_cached: bool = typer.Option(
        True,
        "--skip-cached/--no-skip-cached",
        help="跳过已缓存的地址（断点续传），默认启用"
    ),
    workers: int = typer.Option(
        1,
        "-w", "--workers",
        help="并行线程数 (1-10)，默认单线程"
    ),
    verbose: bool = typer.Option(
        False,
        "-v", "--verbose",
        help="显示详细日志信息"
    ),
):
    """
    执行批量地理编码

    将地址文件中的地址批量转换为经纬度坐标，生成结果文件和地图可视化。

    支持断点续传（跳过已缓存）、并行处理、多格式输出。

    示例:
        yaelocus run -i data/清单.xlsx               # 基本用法
        yaelocus run -i data/清单.xlsx -f xlsx       # 输出 Excel
        yaelocus run -i data/清单.xlsx -w 5          # 5线程并行
        yaelocus run -i data/清单.xlsx --skip-cached # 断点续传
    """
    # 显示标题
    console.print(Panel.fit(
        f"[bold blue]YaeLocus[/bold blue] [dim]v{__version__}[/dim]\n"
        f"[dim]地址转经纬度工具[/dim]",
        border_style="blue"
    ))

    # 首次运行欢迎提示
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        console.print(f"\n[dim]首次使用？欢迎！如果觉得有用，欢迎给项目点个 ⭐️[/dim]")
        console.print(f"[dim]GitHub: https://github.com/Yaemikoreal/YaeLocus[/dim]\n")

    # 检查配置
    if not Config.validate():
        console.print(f"\n[red][FAIL] 错误 [{NO_API_KEY.code}][/red]")
        console.print(f"   {NO_API_KEY.message}")
        console.print(f"\n[yellow][TIP] 建议:[/yellow] {NO_API_KEY.suggestion}")
        raise typer.Exit(1)

    available_apis = Config.get_available_apis()
    console.print(f"[green][OK][/green] 可用API: {', '.join(available_apis)}")

    # 设置默认路径
    input_path = resolve_path(str(input))
    output_path = resolve_path(str(output) if output else "output/地址_经纬度_结果.csv")
    map_path = resolve_path(str(map_file) if map_file else "output/地图输出.html")
    cache_path = resolve_path(str(cache_file) if cache_file else "output/geocache.db")
    log_path = resolve_path("output/api调用日志.csv")

    # 检查输入文件
    if not input_path.exists():
        console.print(f"\n[red][FAIL] 错误 [{FILE_NOT_FOUND.code}][/red]")
        console.print(f"   {FILE_NOT_FOUND.message}: {input_path}")
        raise typer.Exit(1)

    # 初始化缓存
    cache_manager = CacheManager(
        cache_file=str(cache_path),
        default_ttl=ttl,
        batch_size=batch_size
    )

    cache_stats = cache_manager.get_stats()
    console.print(f"[green][OK][/green] 缓存状态: {cache_stats['total_entries']} 条记录")

    # 清理过期缓存
    if cleanup:
        cleaned = cache_manager.cleanup()
        console.print(f"[yellow]清理过期缓存: {cleaned} 条[/yellow]")

    # 加载地址数据
    import pandas as pd

    try:
        suffix = input_path.suffix.lower()
        if suffix in [".xlsx", ".xls"]:
            engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
            df = pd.read_excel(input_path, engine=engine)
        else:
            df = pd.read_csv(input_path, encoding="utf-8-sig")

        if column not in df.columns:
            console.print(f"\n[red][FAIL] 错误 [{COLUMN_NOT_FOUND.code}][/red]")
            console.print(f"   列 '{column}' 不存在")
            console.print(f"   可用列: {list(df.columns)}")
            console.print(f"\n[yellow][TIP] 建议:[/yellow] {COLUMN_NOT_FOUND.suggestion}")
            cache_manager.close()
            raise typer.Exit(1)

        addresses = df[column].dropna().astype(str).tolist()
    except Exception as e:
        console.print(f"\n[red][FAIL] 读取文件失败[/red]")
        console.print(f"   {str(e)}")
        cache_manager.close()
        raise typer.Exit(1)

    # 断点续传：跳过已缓存结果
    addresses_to_process = []
    cached_results = {}
    skipped_count = 0

    if skip_cached:
        for addr in addresses:
            cached = cache_manager.get(addr)
            if cached is not None:
                cached_results[addr] = cached
                skipped_count += 1
            else:
                addresses_to_process.append(addr)
        console.print(f"[cyan]跳过已缓存: {skipped_count} 条[/cyan]")
        console.print(f"[cyan]待处理: {len(addresses_to_process)} 条[/cyan]")
    else:
        addresses_to_process = addresses

    console.print(f"\n[cyan]输入文件:[/cyan] {input_path}")
    console.print(f"[cyan]地址总数:[/cyan] {len(addresses)} 条")

    # 初始化地理编码器
    api_logger = APILogger(str(log_path))
    geocoder = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    # 执行地理编码（带进度条）
    console.print("\n[bold]开始地理编码...[/bold]")

    if len(addresses_to_process) == 0:
        # 所有地址已缓存
        console.print("[green][OK] 所有地址已缓存，无需处理[/green]")
        new_results_map = {}
    elif workers > 1:
        # 并行处理
        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_workers = min(workers, 10)
        new_results_map = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("并行处理", total=len(addresses_to_process))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(geocoder.geocode, addr): addr
                    for addr in addresses_to_process
                }

                for future in as_completed(futures):
                    addr = futures[future]
                    new_results_map[addr] = future.result()
                    progress.update(task, advance=1)
    else:
        # 串行处理
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("处理地址", total=len(addresses_to_process))

            new_results_map = {}
            for addr in addresses_to_process:
                result = geocoder.geocode(addr)
                new_results_map[addr] = result
                progress.update(task, advance=1)

    # 合并结果：按原始顺序排列
    results = []
    for addr in addresses:
        if addr in cached_results:
            results.append(cached_results[addr])
        elif addr in new_results_map:
            results.append(new_results_map[addr])
        else:
            results.append({"success": False, "original_address": addr, "error": "Not processed"})

    # 先获取统计（在关闭前）
    cache_stats = geocoder.get_cache_stats()

    # 手动提交缓存并关闭
    geocoder.close()

    # 保存结果
    output_data = []
    for r in results:
        output_data.append({
            "原始地址": r.get("original_address", ""),
            "标准化地址": r.get("formatted_address", ""),
            "经度": r.get("longitude", ""),
            "纬度": r.get("latitude", ""),
            "省": r.get("province", ""),
            "市": r.get("city", ""),
            "区": r.get("district", ""),
            "数据来源": r.get("source", ""),
            "坐标系": r.get("coordinate_system", ""),
            "状态": "成功" if r.get("success") else "失败",
        })

    output_df = pd.DataFrame(output_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 根据格式输出
    actual_format = output_format.lower()
    if actual_format == "xlsx" or output_path.suffix.lower() == ".xlsx":
        output_df.to_excel(output_path, index=False, engine="openpyxl")
    elif actual_format == "json" or output_path.suffix.lower() == ".json":
        output_df.to_json(output_path, orient="records", force_ascii=False, indent=2)
    elif actual_format == "geojson" or output_path.suffix.lower() == ".geojson":
        import json
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r.get("经度", 0), r.get("纬度", 0)]
                    },
                    "properties": {
                        "address": r.get("原始地址", ""),
                        "formatted_address": r.get("标准化地址", ""),
                        "province": r.get("省", ""),
                        "city": r.get("市", ""),
                        "district": r.get("区", ""),
                        "source": r.get("数据来源", ""),
                        "coordinate_system": r.get("坐标系", ""),
                        "status": r.get("状态", "")
                    }
                }
                for r in output_data if r.get("经度") and r.get("纬度") and r.get("状态") == "成功"
            ]
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    else:
        output_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # 生成地图
    valid_results = [r for r in results if r.get("success")]
    if valid_results:
        create_map(
            data=valid_results,
            output_file=str(map_path),
            title="地址分布地图",
            use_cluster=not no_cluster,
            use_heatmap=not no_heatmap,
        )

    # 显示统计表格
    success_count = len(valid_results)
    api_stats = api_logger.get_stats()

    table = Table(title="\n处理结果统计", show_header=True, header_style="bold cyan")
    table.add_column("指标", style="cyan")
    table.add_column("数值", justify="right")

    table.add_row("总地址数", str(len(addresses)))
    table.add_row("[OK] 成功", f"[green]{success_count}[/green]")
    table.add_row("[FAIL] 失败", f"[red]{len(addresses) - success_count}[/red]")
    table.add_row("成功率", f"{success_count / len(addresses) * 100:.1f}%")
    table.add_row("缓存命中率", f"{cache_stats['hit_rate']}%")

    console.print(table)

    if api_stats["api_usage"]:
        api_table = Table(title="API调用统计", show_header=True, header_style="bold cyan")
        api_table.add_column("API", style="cyan")
        api_table.add_column("调用次数", justify="right")
        for api, count in api_stats["api_usage"].items():
            api_table.add_row(api, str(count))
        console.print(api_table)

    # 输出文件
    console.print(f"\n[green][OK] 处理完成![/green]")
    console.print(f"  [cyan]结果:[/cyan] {output_path}")
    if valid_results:
        console.print(f"  [cyan]地图:[/cyan] {map_path}")
    console.print(f"  [cyan]缓存:[/cyan] {cache_path}")

    if verbose:
        console.print(f"  [dim]日志: {log_path}[/dim]")


@app.command()
def cache(
    action: str = typer.Argument(
        ...,
        help="操作: stats|clear|export|cleanup"
    ),
    cache_file: Path = typer.Option(
        None,
        "--cache",
        help="缓存数据库文件"
    ),
):
    """
    缓存管理

    支持查看统计、清空缓存、导出数据、清理过期条目。
    """
    cache_path = resolve_path(str(cache_file) if cache_file else "output/geocache.db")

    if not cache_path.exists():
        console.print(f"[red][FAIL] 缓存文件不存在: {cache_path}[/red]")
        raise typer.Exit(1)

    cache_manager = CacheManager(cache_file=str(cache_path))

    if action == "stats":
        stats = cache_manager.get_stats()
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
        console.print(f"[green][OK][/green] 已清空 {count} 条缓存")

    elif action == "cleanup":
        cleaned = cache_manager.cleanup()
        cache_manager.close()
        console.print(f"[green][OK][/green] 清理过期缓存: {cleaned} 条")

    elif action == "export":
        import json
        export_path = resolve_path("output/cache_export.json")
        import sqlite3
        conn = sqlite3.connect(str(cache_path))
        rows = conn.execute("SELECT address, data, created_at, source FROM cache").fetchall()
        data = [{"address": r[0], "result": json.loads(r[1]), "created": r[2], "source": r[3]} for r in rows]
        conn.close()
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"[green][OK][/green] 已导出 {len(data)} 条缓存到 {export_path}")

    else:
        console.print(f"[red][FAIL] 未知操作: {action}[/red]")
        console.print("可用操作: stats, clear, cleanup, export")
        cache_manager.close()
        raise typer.Exit(1)


@app.command()
def config():
    """
    交互式配置API密钥

    配置高德、百度、天地图API密钥。
    """
    console.print(Panel.fit(
        "[bold yellow]API密钥配置[/bold yellow]",
        border_style="yellow"
    ))
    console.print("请配置至少一个API密钥\n")

    env_path = PROJECT_DIR / ".env"
    existing = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    existing[key] = val

    # 高德
    amap_key = typer.prompt(
        "高德地图 API Key (留空跳过)",
        default=existing.get('AMAP_KEY', ''),
        show_default=False
    )
    if amap_key:
        if len(amap_key) != 32:
            console.print("[red][FAIL] 格式错误: 应为32位字符[/red]")
        else:
            console.print("[green][OK] 格式正确[/green]")
            existing['AMAP_KEY'] = amap_key

    # 百度
    baidu_key = typer.prompt(
        "百度地图 AK (留空跳过)",
        default=existing.get('BAIDU_AK', ''),
        show_default=False
    )
    if baidu_key:
        console.print("[green][OK] 已配置[/green]")
        existing['BAIDU_AK'] = baidu_key

    # 天地图
    tianditu_key = typer.prompt(
        "天地图 TK (留空跳过)",
        default=existing.get('TIANDITU_TK', ''),
        show_default=False
    )
    if tianditu_key:
        console.print("[green][OK] 已配置[/green]")
        existing['TIANDITU_TK'] = tianditu_key

    # 保存配置
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# API密钥配置\n")
        for key, val in existing.items():
            f.write(f"{key}={val}\n")

    console.print(f"\n[green][OK] 配置已保存到 {env_path}[/green]")


@app.command()
def doctor():
    """
    环境诊断

    检查配置文件、API密钥、网络连通性等。
    """
    console.print(Panel.fit(
        "[bold cyan]环境诊断[/bold cyan]",
        border_style="cyan"
    ))

    issues = []

    # 检查配置文件
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        console.print("[red][FAIL][/red] .env 文件不存在")
        issues.append("运行 'geocode-tool config' 创建配置")
    else:
        console.print("[green][OK][/green] .env 文件存在")

    # 检查API密钥
    apis = Config.get_available_apis()
    if not apis:
        console.print("[red][FAIL][/red] 未配置任何API密钥")
        issues.append("运行 'geocode-tool config' 配置密钥")
    else:
        console.print(f"[green][OK][/green] 已配置API: {', '.join(apis)}")

    # 检查缓存目录
    output_dir = PROJECT_DIR / "output"
    if not output_dir.exists():
        console.print("[yellow][WARN][/yellow] output 目录不存在 (将自动创建)")
    else:
        console.print("[green][OK][/green] output 目录存在")

    # 总结
    if issues:
        console.print("\n[yellow]需要修复:[/yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
    else:
        console.print("\n[green][OK] 环境检查通过[/green]")


@app.command()
def test_api():
    """
    测试API连通性

    测试各API是否能正常响应。
    """
    console.print(Panel.fit(
        "[bold cyan]API连通性测试[/bold cyan]",
        border_style="cyan"
    ))

    apis = Config.get_available_apis()
    if not apis:
        console.print("[red][FAIL] 未配置任何API密钥[/red]")
        raise typer.Exit(1)

    import requests

    for api in apis:
        console.print(f"\n[cyan]测试 {api}...[/cyan]")
        try:
            if api == "amap":
                key = Config.AMAP_KEY
                url = f"https://restapi.amap.com/v3/geocode/geo?key={key}&address=北京"
                resp = requests.get(url, timeout=10)
            elif api == "baidu":
                key = Config.BAIDU_AK
                url = f"https://api.map.baidu.com/geocoding/v3/?ak={key}&address=北京&output=json"
                resp = requests.get(url, timeout=10)
            elif api == "tianditu":
                # 天地图地理编码 API 使用 ds 参数
                url = Config.TIANDITU_URL
                params = {"ds": '{"keyWord":"北京"}', "tk": Config.TIANDITU_TK}
                resp = requests.get(url, params=params, timeout=10)
            else:
                continue

            if resp.status_code == 200:
                console.print(f"[green][OK][/green] {api} 连接正常")
            else:
                console.print(f"[red][FAIL][/red] {api} 返回状态码: {resp.status_code}")
        except Exception as e:
            console.print(f"[red][FAIL][/red] {api} 连接失败: {str(e)}")


@app.command()
def geocode(
    address: str = typer.Argument(
        ...,
        help="要转换的地址"
    ),
    cache_file: Path = typer.Option(
        None,
        "--cache",
        help="缓存数据库文件"
    ),
    ttl: int = typer.Option(
        None,
        "--ttl",
        help="缓存过期时间(秒)"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="JSON格式输出"
    ),
):
    """
    转换单个地址为经纬度

    示例:
        geocode "北京市朝阳区建国路88号"
        geocode "天安门" --json
    """
    # 首次运行欢迎提示
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        console.print(f"[dim]首次使用？欢迎！如果觉得有用，欢迎给项目点个 ⭐️[/dim]")
        console.print(f"[dim]GitHub: https://github.com/Yaemikoreal/YaeLocus[/dim]\n")

    # 检查配置
    if not Config.validate():
        console.print(f"[red][FAIL] 错误: {NO_API_KEY.message}[/red]")
        console.print(f"[yellow][TIP] {NO_API_KEY.suggestion}[/yellow]")
        raise typer.Exit(1)

    # 初始化
    cache_path = resolve_path(str(cache_file) if cache_file else "output/geocache.db")
    log_path = resolve_path("output/api调用日志.csv")

    cache_manager = CacheManager(
        cache_file=str(cache_path),
        default_ttl=ttl
    )
    api_logger = APILogger(str(log_path))
    geocoder_obj = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    # 执行转换
    result = geocoder_obj.geocode(address)
    geocoder_obj.close()

    # 输出结果
    if json_output:
        import json
        output = {
            "address": address,
            "longitude": result.get("longitude"),
            "latitude": result.get("latitude"),
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "success": result.get("success", False)
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if result.get("success"):
            console.print(Panel(
                f"[bold]地址:[/bold] {address}\n"
                f"[bold]经度:[/bold] [green]{result.get('longitude', '')}[/green]\n"
                f"[bold]纬度:[/bold] [green]{result.get('latitude', '')}[/green]\n"
                f"[bold]标准化地址:[/bold] {result.get('formatted_address', '')}\n"
                f"[bold]省市区:[/bold] {result.get('province', '')} {result.get('city', '')} {result.get('district', '')}\n"
                f"[bold]数据来源:[/bold] [cyan]{result.get('source', '')}[/cyan]",
                title="[bold blue]转换结果[/bold blue]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold]地址:[/bold] {address}\n"
                f"[bold]状态:[/bold] [red]转换失败[/red]\n"
                f"[bold]错误:[/bold] {result.get('error', '未知错误')}",
                title="[bold red]转换失败[/bold red]",
                border_style="red"
            ))
            raise typer.Exit(1)


@app.command()
def reverse(
    lat: float = typer.Argument(
        ...,
        help="纬度坐标值"
    ),
    lon: float = typer.Argument(
        ...,
        help="经度坐标值"
    ),
    cache_file: Path = typer.Option(
        None,
        "--cache",
        help="缓存数据库路径，默认 output/geocache.db"
    ),
    ttl: int = typer.Option(
        None,
        "--ttl",
        help="缓存有效期（秒），默认永久有效"
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="以 JSON 格式输出结果"
    ),
):
    """
    逆地理编码（经纬度转地址）

    将经纬度坐标转换为详细地址信息，返回省市区和标准地址。

    示例:
        yaelocus reverse 39.9 116.4
        yaelocus reverse 39.9042 116.4074 --json
    """
    # 检查配置
    if not Config.validate():
        console.print(f"[red][FAIL] 错误: {NO_API_KEY.message}[/red]")
        console.print(f"[yellow][TIP] {NO_API_KEY.suggestion}[/yellow]")
        raise typer.Exit(1)

    # 初始化
    cache_path = resolve_path(str(cache_file) if cache_file else "output/geocache.db")
    log_path = resolve_path("output/api调用日志.csv")

    cache_manager = CacheManager(
        cache_file=str(cache_path),
        default_ttl=ttl
    )
    api_logger = APILogger(str(log_path))
    geocoder_obj = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    # 执行逆地理编码
    result = geocoder_obj.reverse_geocode(lat, lon)
    geocoder_obj.close()

    # 输出结果
    if json_output:
        import json
        output = {
            "latitude": lat,
            "longitude": lon,
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "success": result.get("success", False)
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if result.get("success"):
            console.print(Panel(
                f"[bold]输入坐标:[/bold] {lat}, {lon}\n"
                f"[bold]地址:[/bold] [green]{result.get('formatted_address', '')}[/green]\n"
                f"[bold]省市区:[/bold] {result.get('province', '')} {result.get('city', '')} {result.get('district', '')}\n"
                f"[bold]数据来源:[/bold] [cyan]{result.get('source', '')}[/cyan]",
                title="[bold blue]逆地理编码结果[/bold blue]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold]输入坐标:[/bold] {lat}, {lon}\n"
                f"[bold]状态:[/bold] [red]转换失败[/red]\n"
                f"[bold]错误:[/bold] {result.get('error', '未知错误')}",
                title="[bold red]逆地理编码失败[/bold red]",
                border_style="red"
            ))
            raise typer.Exit(1)


@app.command()
def convert(
    lat: float = typer.Argument(
        ...,
        help="纬度坐标值"
    ),
    lon: float = typer.Argument(
        ...,
        help="经度坐标值"
    ),
    from_sys: str = typer.Option(
        "wgs84",
        "--from",
        help="源坐标系: wgs84|gcj02|bd09"
    ),
    to_sys: str = typer.Option(
        "gcj02",
        "--to",
        help="目标坐标系: wgs84|gcj02|bd09"
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="以 JSON 格式输出结果"
    ),
):
    """
    坐标系转换

    在不同坐标系之间转换经纬度坐标:
      wgs84 - GPS原始坐标（国际标准坐标系）
      gcj02 - 国测局坐标（高德地图、天地图使用）
      bd09  - 百度偏移坐标（百度地图使用）

    示例:
        yaelocus convert 39.9 116.4 --from gcj02 --to wgs84
        yaelocus convert 39.9 116.4 --from bd09 --to wgs84 --json
    """
    from .coords import gcj02_to_wgs84, bd09_to_wgs84, bd09_to_gcj02

    # 转换逻辑
    result_lat, result_lon = lat, lon
    from_sys = from_sys.lower()
    to_sys = to_sys.lower()

    # 坐标系转换矩阵
    if from_sys == to_sys:
        # 无需转换
        pass
    elif from_sys == "gcj02" and to_sys == "wgs84":
        result_lat, result_lon = gcj02_to_wgs84(lat, lon)
    elif from_sys == "bd09" and to_sys == "wgs84":
        result_lat, result_lon = bd09_to_wgs84(lat, lon)
    elif from_sys == "bd09" and to_sys == "gcj02":
        result_lat, result_lon = bd09_to_gcj02(lat, lon)
    elif from_sys == "wgs84" and to_sys == "gcj02":
        # WGS-84 转 GCJ-02 需要反向计算
        console.print("[yellow][WARN] wgs84 -> gcj02 转换暂不支持[/yellow]")
        console.print("[dim]建议使用 gcj02_to_wgs84 或 bd09_to_wgs84[/dim]")
        raise typer.Exit(1)
    else:
        console.print(f"[red][FAIL] 不支持的转换: {from_sys} -> {to_sys}[/red]")
        raise typer.Exit(1)

    # 输出结果
    if json_output:
        import json
        output = {
            "input": {"lat": lat, "lon": lon, "coordinate_system": from_sys},
            "output": {"lat": result_lat, "lon": result_lon, "coordinate_system": to_sys}
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        console.print(Panel(
            f"[bold]输入坐标:[/bold] {lat}, {lon} ({from_sys})\n"
            f"[bold]输出坐标:[/bold] [green]{result_lat:.6f}, {result_lon:.6f}[/green] ({to_sys})",
            title="[bold blue]坐标转换结果[/bold blue]",
            border_style="green"
        ))


@app.command()
def quota():
    """
    查看API配额使用情况

    显示各API今日已用次数、剩余配额和使用率状态:
      - 高德地图: 5000次/日
      - 天地图: 10000次/日
      - 百度地图: 6000次/日

    示例:
        yaelocus quota
    """
    console.print(Panel.fit(
        "[bold cyan]API配额状态[/bold cyan]",
        border_style="cyan"
    ))

    # 从日志文件统计今日调用次数（简化版）
    log_path = resolve_path("output/api调用日志.csv")
    if not log_path.exists():
        console.print("[yellow]无调用日志[/yellow]")
        console.print("[dim]运行 'yaelocus run' 后再查看配额[/dim]")
        return

    import pandas as pd
    from datetime import datetime

    try:
        df = pd.read_csv(log_path)
        today = datetime.now().strftime("%Y-%m-%d")
        today_logs = df[df['timestamp'].str.startswith(today) if 'timestamp' in df.columns else False]

        table = Table(title="今日配额统计", show_header=True, header_style="bold cyan")
        table.add_column("API", style="cyan")
        table.add_column("已用", justify="right")
        table.add_column("限额", justify="right")
        table.add_column("剩余", justify="right")

        limits = {"amap": 5000, "tianditu": 10000, "baidu": 6000}
        for api, limit in limits.items():
            used = len(today_logs[today_logs['api_name'] == api]) if 'api_name' in today_logs.columns else 0
            remaining = limit - used
            table.add_row(api, str(used), str(limit), str(remaining))

        console.print(table)
        console.print("\n[dim]提示: 配额每日零点重置[/dim]")
    except Exception as e:
        console.print(f"[red]读取日志失败: {e}[/red]")


def _list_files(path: Path, detail: bool) -> None:
    """列出可处理文件的核心逻辑"""
    import pandas as pd
    from datetime import datetime

    # 确定目录路径
    if path:
        dir_path = resolve_path(str(path))
    else:
        dir_path = PROJECT_DIR / "data"

    console.print(Panel.fit(
        f"[bold cyan]可处理文件列表[/bold cyan]\n"
        f"[dim]目录: {dir_path}[/dim]",
        border_style="cyan"
    ))

    # 检查目录是否存在
    if not dir_path.exists():
        console.print(f"[red][FAIL] 目录不存在: {dir_path}[/red]")
        raise typer.Exit(1)

    # 查找可处理文件
    supported_extensions = [".csv", ".xlsx", ".xls"]
    files_list = []

    for file_path in dir_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            # 获取文件信息
            file_stat = file_path.stat()
            size_kb = file_stat.st_size / 1024
            mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            # 获取地址数量（可选）
            address_count = None
            if detail:
                try:
                    suffix = file_path.suffix.lower()
                    if suffix in [".xlsx", ".xls"]:
                        df = pd.read_excel(file_path, engine="openpyxl" if suffix == ".xlsx" else "xlrd")
                    else:
                        df = pd.read_csv(file_path, encoding="utf-8-sig")

                    # 查找地址列
                    address_col = None
                    for col in df.columns:
                        if "地址" in col.lower():
                            address_col = col
                            break
                    if address_col:
                        address_count = df[address_col].dropna().astype(str).count()
                    else:
                        address_count = df.shape[0]
                except Exception:
                    address_count = "无法读取"

            files_list.append({
                "name": file_path.name,
                "type": file_path.suffix.upper().lstrip("."),
                "size": f"{size_kb:.1f} KB",
                "modified": mod_time,
                "count": address_count
            })

    # 输出结果
    if not files_list:
        console.print(f"[yellow]目录中没有可处理的文件[/yellow]")
        console.print(f"[dim]支持的格式: CSV, XLSX, XLS[/dim]")
        return

    table = Table(title="", show_header=True, header_style="bold cyan")
    table.add_column("文件名", style="cyan")
    table.add_column("类型", justify="center")
    table.add_column("大小", justify="right")
    table.add_column("修改时间", justify="center")

    if detail:
        table.add_column("地址数", justify="right")

    for f in files_list:
        if detail:
            count_str = str(f["count"]) if f["count"] is not None else "-"
            table.add_row(f["name"], f["type"], f["size"], f["modified"], count_str)
        else:
            table.add_row(f["name"], f["type"], f["size"], f["modified"])

    console.print(table)
    console.print(f"\n[green]共 {len(files_list)} 个可处理文件[/green]")

    # 提示使用方式
    if files_list:
        console.print(f"\n[dim]提示: 使用 'run -i data/{files_list[0]['name']}' 开始处理[/dim]")


@app.command("ll")
@app.command("files")
def list_files(
    path: Path = typer.Option(
        None,
        "-p", "--path",
        help="指定目录路径，默认 data/"
    ),
    detail: bool = typer.Option(
        False,
        "-d", "--detail",
        help="显示详细信息（读取文件统计地址数量）"
    ),
):
    """
    列出可处理的输入文件

    扫描指定目录中的 CSV/Excel 文件，便于快速选择输入文件。
    ll 是 files 的简写别名。

    示例:
        yaelocus files              # 列出 data/ 目录文件
        yaelocus ll                 # ll 是 files 的别名
        yaelocus files -p output/   # 列出其他目录
        yaelocus files --detail     # 显示地址数量
    """
    _list_files(path, detail)


if __name__ == "__main__":
    app()
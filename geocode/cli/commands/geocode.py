"""
地理编码命令：单地址、批量、逆地理编码、坐标转换
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import typer
import pandas as pd
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from ..utils import (
    console, OK, FAIL, WARN,
    resolve_path, _write_progress,
    _print_error_json,
)


class _NoopProgress:
    """TUI 模式空进度条 — 静默跳过所有进度输出"""
    def __init__(self, *args, **kwargs): pass
    def add_task(self, *args, **kwargs): return 0
    def update(self, task_id, advance=1): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


from ... import __version__
from ...cache import CacheManager
from ...config import Config, OutputPaths, PROJECT_DIR
from ...errors import NO_API_KEY, FILE_NOT_FOUND, COLUMN_NOT_FOUND
from ...geocoder import Geocoder
from ...logger import APILogger
from ...map_visualizer import create_map


def single(
    address: str = typer.Argument(..., help="要转换的地址"),
    cache_file: Optional[Path] = typer.Option(None, "--cache", help="缓存数据库文件"),
    ttl: Optional[int] = typer.Option(None, "--ttl", help="缓存过期时间(秒)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
):
    """转换单个地址为经纬度

    示例:
        yaelocus geocode single "北京市朝阳区"
        yaelocus geocode single "天安门" --json
    """
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        console.print(f"[dim]首次使用？欢迎！GitHub: https://github.com/Yaemikoreal/YaeLocus[/dim]\n")

    if not Config.validate():
        if json_output:
            _print_error_json(NO_API_KEY, "geocode")
        else:
            console.print(f"[red]{FAIL} 错误: {NO_API_KEY.message}[/red]")
            console.print(f"[yellow][TIP] {NO_API_KEY.suggestion}[/yellow]")
        raise typer.Exit(1)

    cache_path = resolve_path(str(cache_file) if cache_file else str(OutputPaths.DATABASE / "geocache.db"))
    log_path = resolve_path(str(OutputPaths.LOG / "api调用日志.csv"))

    cache_manager = CacheManager(cache_file=str(cache_path), default_ttl=ttl)
    api_logger = APILogger(str(log_path))
    geocoder_obj = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    result = geocoder_obj.geocode(address)
    geocoder_obj.close()

    if json_output:
        output = {
            "command": "geocode",
            "address": address,
            "longitude": result.get("longitude"),
            "latitude": result.get("latitude"),
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "success": result.get("success", False),
            "status": "success" if result.get("success") else "error",
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


def batch(
    input: Path = typer.Option(..., "-i", "--input", help="输入文件路径，支持 CSV/XLSX/XLS"),
    column: str = typer.Option("地址", "-c", "--column", help="地址列名"),
    city: Optional[str] = typer.Option(None, "--city", help="指定地市（如眉山市，提高模糊地址精度）"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="输出文件路径"),
    map_file: Optional[Path] = typer.Option(None, "-m", "--map", help="地图输出路径"),
    cache_file: Optional[Path] = typer.Option(None, "--cache", help="缓存数据库路径"),
    ttl: Optional[int] = typer.Option(None, "--ttl", help="缓存有效期（秒）"),
    batch_size: int = typer.Option(100, "--batch-size", help="缓存批量写入阈值"),
    cleanup: bool = typer.Option(False, "--cleanup", help="运行前清理过期缓存"),
    no_cluster: bool = typer.Option(False, "--no-cluster", help="禁用点聚类"),
    no_heatmap: bool = typer.Option(False, "--no-heatmap", help="禁用热力图"),
    output_format: str = typer.Option("csv", "-f", "--format", help="输出格式: csv|xlsx|json|geojson"),
    skip_cached: bool = typer.Option(True, "--skip-cached/--no-skip-cached", help="跳过已缓存地址"),
    workers: int = typer.Option(1, "-w", "--workers", help="并行线程数 (1-10)"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
    stdout_json: bool = typer.Option(False, "--stdout-json", help="输出 JSON 到 stdout"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出（同 --stdout-json）"),
):
    """批量地理编码

    将地址文件中的地址批量转换为经纬度坐标，生成结果文件和地图可视化。

    示例:
        yaelocus geocode batch -i data/清单.xlsx
        yaelocus geocode batch -i data/清单.xlsx -f xlsx -w 5
        yaelocus geocode batch -i data/清单.xlsx --json
    """
    stdout_json = stdout_json or json_output

    if not stdout_json:
        from ..utils import print_version
        print_version(__version__)

    env_path = PROJECT_DIR / ".env"
    if not stdout_json and not env_path.exists():
        console.print(f"\n[dim]首次使用？欢迎！GitHub: https://github.com/Yaemikoreal/YaeLocus[/dim]\n")

    if not Config.validate():
        if stdout_json:
            _print_error_json(NO_API_KEY, "geocode_batch")
        else:
            console.print(f"\n[red]{FAIL} 错误 [{NO_API_KEY.code}][/red]")
            console.print(f"   {NO_API_KEY.message}")
            console.print(f"\n[yellow][TIP] 建议:[/yellow] {NO_API_KEY.suggestion}")
        raise typer.Exit(1)

    available_apis = Config.get_available_apis()
    if not stdout_json:
        console.print(f"[green]{OK}[/green] 可用API: {', '.join(available_apis)}")

    input_path = resolve_path(str(input))
    input_stem = input_path.stem if input_path.stem else "result"
    output_path = resolve_path(str(output) if output else str(OutputPaths.CSV / f"{input_stem}.csv"))
    map_path = resolve_path(str(map_file) if map_file else str(OutputPaths.MAP / f"{input_stem}_map.html"))
    cache_path = resolve_path(str(cache_file) if cache_file else str(OutputPaths.DATABASE / "geocache.db"))
    log_path = resolve_path(str(OutputPaths.LOG / "api调用日志.csv"))

    _tui = os.environ.get('YAELOCUS_TUI')
    _Progress = _NoopProgress if (stdout_json or _tui) else Progress

    if not input_path.exists():
        if stdout_json:
            _print_error_json(FILE_NOT_FOUND, "geocode_batch")
        else:
            console.print(f"\n[red]{FAIL} 错误 [{FILE_NOT_FOUND.code}][/red]")
            console.print(f"   {FILE_NOT_FOUND.message}: {input_path}")
        raise typer.Exit(1)

    cache_manager = CacheManager(cache_file=str(cache_path), default_ttl=ttl, batch_size=batch_size)
    cache_manager.start_watchdog(interval=30.0)

    progress_file = resolve_path(str(OutputPaths.PROGRESS / ".geocode_progress.json"))
    cache_stats = cache_manager.get_stats()
    if not stdout_json:
        console.print(f"[green]{OK}[/green] 缓存状态: {cache_stats['total_entries']} 条记录")

    if cleanup:
        cleaned = cache_manager.cleanup()
        if not stdout_json:
            console.print(f"[yellow]清理过期缓存: {cleaned} 条[/yellow]")

    # 加载数据
    try:
        suffix = input_path.suffix.lower()
        if suffix in [".xlsx", ".xls"]:
            engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
            df = pd.read_excel(input_path, engine=engine)
        else:
            df = pd.read_csv(input_path, encoding="utf-8-sig")

        if column not in df.columns:
            if stdout_json:
                _print_error_json(COLUMN_NOT_FOUND, "geocode_batch")
            else:
                console.print(f"\n[red]{FAIL} 错误 [{COLUMN_NOT_FOUND.code}][/red]")
                console.print(f"   列 '{column}' 不存在")
                console.print(f"   可用列: {list(df.columns)}")
            cache_manager.close()
            raise typer.Exit(1)

        # === 无效数据过滤 ===
        from ...preprocessing import InvalidAddressFilter

        raw_addresses = df[column].dropna().tolist()
        filter_obj = InvalidAddressFilter()

        # 预过滤
        valid_raw = []
        invalid_raw = []
        for addr in raw_addresses:
            is_valid, reason = filter_obj.is_valid(addr)
            if is_valid:
                valid_raw.append(str(addr).strip())
            else:
                invalid_raw.append((addr, reason))

        addresses = valid_raw

        # === 指定地市前缀处理 ===
        if city:
            # 统一地市名称（确保以"市"结尾）
            city_normalized = city.strip()
            if not city_normalized.endswith("市") and not city_normalized.endswith("区") and not city_normalized.endswith("县"):
                city_normalized = city_normalized + "市"

            # 检查地址是否包含"市"的信息
            # 如果地址没有包含任何"市"关键字，则添加指定地市前缀
            # 如果地址已包含"市"（即使是其他市），则不添加
            addresses_with_city = []

            for addr in addresses:
                # 检查地址是否已包含"市"的信息
                if "市" in addr:
                    # 地址已包含"市"的信息，不添加前缀
                    addresses_with_city.append(addr)
                else:
                    # 地址没有包含"市"的信息，添加指定地市前缀
                    addresses_with_city.append(f"{city_normalized}{addr}")

            addresses = addresses_with_city

            if not stdout_json:
                console.print(f"[cyan]指定地市: {city_normalized}[/cyan]")

        # 输出过滤统计
        if not stdout_json and invalid_raw:
            console.print(f"[yellow]过滤无效数据: {len(invalid_raw)} 条[/yellow]")
            reasons_count = {}
            for _, reason in invalid_raw:
                reasons_count[reason] = reasons_count.get(reason, 0) + 1
            for reason, count in reasons_count.items():
                console.print(f"[dim]  - {reason}: {count} 条[/dim]")
    except Exception as e:
        if stdout_json:
            error_output = {
                "error": {"code": "FILE_READ_ERROR", "message": str(e)},
                "command": "geocode_batch", "status": "error",
            }
            print(json.dumps(error_output, ensure_ascii=False))
        else:
            console.print(f"\n[red]{FAIL} 读取文件失败[/red]\n   {str(e)}")
        cache_manager.close()
        raise typer.Exit(1)

    # 断点续传
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
        if not stdout_json:
            console.print(f"[cyan]跳过已缓存: {skipped_count} 条[/cyan]")
            console.print(f"[cyan]待处理: {len(addresses_to_process)} 条[/cyan]")
    else:
        addresses_to_process = addresses

    if not stdout_json:
        console.print(f"\n[cyan]输入文件:[/cyan] {input_path}")
        console.print(f"[cyan]地址总数:[/cyan] {len(addresses)} 条")

    # 写入初始进度
    if not stdout_json:
        _write_progress(progress_file, {
            "input_file": str(input_path),
            "total": len(addresses),
            "processed": skipped_count + len(cached_results),
            "completed": False,
            "last_update": time.time(),
        })

    api_logger = APILogger(str(log_path))
    geocoder = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    if not stdout_json:
        console.print("\n[bold]开始地理编码...[/bold]")

    if len(addresses_to_process) == 0:
        if not stdout_json:
            console.print(f"[green]{OK} 所有地址已缓存，无需处理[/green]")
        new_results_map = {}
    elif workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_workers = min(workers, 10)
        new_results_map = {}
        processed_since_flush = 0

        with _Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
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
                    processed_since_flush += 1
                    if processed_since_flush >= 50:
                        _write_progress(progress_file, {
                            "input_file": str(input_path),
                            "total": len(addresses),
                            "processed": skipped_count + len(cached_results) + len(new_results_map),
                            "completed": False,
                            "last_update": time.time(),
                        })
                        processed_since_flush = 0
    else:
        with _Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("处理地址", total=len(addresses_to_process))
            new_results_map = {}
            processed_since_flush = 0
            for addr in addresses_to_process:
                result = geocoder.geocode(addr)
                new_results_map[addr] = result
                progress.update(task, advance=1)
                processed_since_flush += 1
                if processed_since_flush >= 50:
                    _write_progress(progress_file, {
                        "input_file": str(input_path),
                        "total": len(addresses),
                        "processed": skipped_count + len(cached_results) + len(new_results_map),
                        "completed": False,
                        "last_update": time.time(),
                    })
                    processed_since_flush = 0

    # 合并结果
    results = []
    for addr in addresses:
        if addr in cached_results:
            results.append(cached_results[addr])
        elif addr in new_results_map:
            results.append(new_results_map[addr])
        else:
            results.append({"success": False, "original_address": addr, "error": "Not processed"})

    cache_stats = geocoder.get_cache_stats()
    geocoder.close()

    if not stdout_json:
        _write_progress(progress_file, {
            "input_file": str(input_path),
            "total": len(addresses),
            "processed": len(addresses),
            "completed": True,
            "last_update": time.time(),
        })

    # === 置信度过滤（丢弃低置信度结果） ===
    # 统计置信度
    trustworthy_results = []
    low_confidence_results = []
    for r in results:
        if r.get("success"):
            confidence = r.get("confidence", {})
            if confidence.get("is_trustworthy", True):
                trustworthy_results.append(r)
            else:
                low_confidence_results.append(r)

    discarded_count = len(low_confidence_results)
    success_count = len(trustworthy_results)
    api_stats = api_logger.get_stats()

    # 输出丢弃统计
    if not stdout_json and discarded_count > 0:
        console.print(f"[yellow]丢弃低置信度结果: {discarded_count} 条[/yellow]")

    if stdout_json:
        output_data = []
        # 仅输出可信结果（用户选择直接丢弃）
        for r in trustworthy_results:
            output_data.append({
                "original_address": r.get("original_address", ""),
                "formatted_address": r.get("formatted_address", ""),
                "longitude": r.get("longitude"),
                "latitude": r.get("latitude"),
                "province": r.get("province", ""),
                "city": r.get("city", ""),
                "district": r.get("district", ""),
                "source": r.get("source", ""),
                "coordinate_system": r.get("coordinate_system", ""),
                "success": True,
                "confidence": r.get("confidence", {}).get("total", 100),
            })

        json_output_data = {
            "command": "geocode_batch",
            "status": "success",
            "results": output_data,
            "stats": {
                "total": len(addresses),
                "success": success_count,
                "discarded": discarded_count,
                "failed": len(addresses) - success_count - discarded_count,
                "success_rate": round(success_count / len(addresses) * 100, 1) if addresses else 0,
                "cache_hit_rate": cache_stats['hit_rate'],
                "api_usage": api_stats.get("api_usage", {}),
            },
            "output_files": {
                "result": str(output_path),
                "map": str(map_path) if success_count > 0 else None,
                "cache": str(cache_path),
            },
        }
        print(json.dumps(json_output_data, ensure_ascii=False))
        return

    # 保存结果（仅输出可信结果）
    output_data = []
    for r in trustworthy_results:
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
            "置信度": r.get("confidence", {}).get("total", 100),
            "状态": "成功",
        })

    output_df = pd.DataFrame(output_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    actual_format = output_format.lower()
    if actual_format == "xlsx" or output_path.suffix.lower() == ".xlsx":
        output_df.to_excel(output_path, index=False, engine="openpyxl")
    elif actual_format == "json" or output_path.suffix.lower() == ".json":
        output_df.to_json(output_path, orient="records", force_ascii=False, indent=2)
    elif actual_format == "geojson" or output_path.suffix.lower() == ".geojson":
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
                        "status": r.get("状态", ""),
                    },
                }
                for r in output_data if r.get("经度") and r.get("纬度") and r.get("状态") == "成功"
            ],
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    else:
        output_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # 生成地图（仅使用可信结果）
    if trustworthy_results:
        create_map(
            data=trustworthy_results,
            output_file=str(map_path),
            title="地址分布地图",
            use_cluster=not no_cluster,
            use_heatmap=not no_heatmap,
        )

    # 统计输出（success_count 已在前面计算）
    _tui = os.environ.get('YAELOCUS_TUI')
    rate = f"{success_count / len(addresses) * 100:.1f}%"

    if _tui:
        # TUI 模式 — 纯文本简洁输出
        console.print(f"已完成 {success_count}/{len(addresses)} 成功 ({rate})")
        if discarded_count > 0:
            console.print(f"[dim]丢弃低置信度: {discarded_count}[/dim]")
        console.print(f"结果: {output_path}")
        if trustworthy_results:
            console.print(f"地图: {map_path}")
    elif not stdout_json:
        table = Table(title="\n处理结果统计", show_header=True, header_style="bold cyan")
        table.add_column("指标", style="cyan")
        table.add_column("数值", justify="right")
        table.add_row("总地址数", str(len(addresses)))
        table.add_row(f"{OK} 成功", f"[green]{success_count}[/green]")
        if discarded_count > 0:
            table.add_row("[yellow]丢弃低置信度[/yellow]", f"[yellow]{discarded_count}[/yellow]")
        table.add_row(f"{FAIL} 失败", f"[red]{len(addresses) - success_count - discarded_count}[/red]")
        table.add_row("成功率", rate)
        table.add_row("缓存命中率", f"{cache_stats['hit_rate']}%")
        console.print(table)

        if api_stats["api_usage"]:
            api_table = Table(title="API调用统计", show_header=True, header_style="bold cyan")
            api_table.add_column("API", style="cyan")
            api_table.add_column("调用次数", justify="right")
            for api, count in api_stats["api_usage"].items():
                api_table.add_row(api, str(count))
            console.print(api_table)

        console.print(f"\n[green]{OK} 处理完成![/green]")
        console.print(f"  [cyan]结果:[/cyan] {output_path}")
        if success_count > 0:
            console.print(f"  [cyan]地图:[/cyan] {map_path}")
        console.print(f"  [cyan]缓存:[/cyan] {cache_path}")
        if verbose:
            console.print(f"  [dim]日志: {log_path}[/dim]")

    # 路线规划后处理 (仅交互式终端)
    if not stdout_json and not os.environ.get('YAELOCUS_TUI') and sys.stdin.isatty():
        console.print()
        if typer.confirm("是否需要进行路线规划？", default=False):
            from ...router import RouteWizard
            wizard = RouteWizard(csv_path=str(output_path), map_path=None)
            wizard.run()


def reverse_cmd(
    lat: float = typer.Argument(..., help="纬度坐标值"),
    lon: float = typer.Argument(..., help="经度坐标值"),
    cache_file: Optional[Path] = typer.Option(None, "--cache", help="缓存数据库路径"),
    ttl: Optional[int] = typer.Option(None, "--ttl", help="缓存有效期（秒）"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
):
    """逆地理编码（经纬度转地址）

    示例:
        yaelocus geocode reverse 39.9 116.4
        yaelocus geocode reverse 39.9042 116.4074 --json
    """
    if not Config.validate():
        console.print(f"[red]{FAIL} 错误: {NO_API_KEY.message}[/red]")
        console.print(f"[yellow][TIP] {NO_API_KEY.suggestion}[/yellow]")
        raise typer.Exit(1)

    cache_path = resolve_path(str(cache_file) if cache_file else str(OutputPaths.DATABASE / "geocache.db"))
    log_path = resolve_path(str(OutputPaths.LOG / "api调用日志.csv"))

    cache_manager = CacheManager(cache_file=str(cache_path), default_ttl=ttl)
    api_logger = APILogger(str(log_path))
    geocoder_obj = Geocoder(cache_manager, api_logger, cache_ttl=ttl)

    result = geocoder_obj.reverse_geocode(lat, lon)
    geocoder_obj.close()

    if json_output:
        output = {
            "command": "geocode_reverse",
            "latitude": lat,
            "longitude": lon,
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "success": result.get("success", False),
            "status": "success" if result.get("success") else "error",
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


def convert_cmd(
    lat: float = typer.Argument(..., help="纬度坐标值"),
    lon: float = typer.Argument(..., help="经度坐标值"),
    from_sys: str = typer.Option("wgs84", "--from", help="源坐标系: wgs84|gcj02|bd09"),
    to_sys: str = typer.Option("gcj02", "--to", help="目标坐标系: wgs84|gcj02|bd09"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
):
    """坐标系转换

    示例:
        yaelocus geocode convert 39.9 116.4 --from gcj02 --to wgs84
    """
    from ...coords import gcj02_to_wgs84, bd09_to_wgs84, bd09_to_gcj02, wgs84_to_gcj02

    result_lat, result_lon = lat, lon
    from_sys = from_sys.lower()
    to_sys = to_sys.lower()

    if from_sys == to_sys:
        pass
    elif from_sys == "gcj02" and to_sys == "wgs84":
        result_lat, result_lon = gcj02_to_wgs84(lat, lon)
    elif from_sys == "bd09" and to_sys == "wgs84":
        result_lat, result_lon = bd09_to_wgs84(lat, lon)
    elif from_sys == "bd09" and to_sys == "gcj02":
        result_lat, result_lon = bd09_to_gcj02(lat, lon)
    elif from_sys == "wgs84" and to_sys == "gcj02":
        result_lat, result_lon = wgs84_to_gcj02(lat, lon)
    else:
        console.print(f"[red]{FAIL} 不支持的转换: {from_sys} -> {to_sys}[/red]")
        raise typer.Exit(1)

    if json_output:
        output = {
            "command": "geocode_convert",
            "input": {"lat": lat, "lon": lon, "coordinate_system": from_sys},
            "output": {"lat": result_lat, "lon": result_lon, "coordinate_system": to_sys},
            "status": "success",
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        console.print(Panel(
            f"[bold]输入坐标:[/bold] {lat}, {lon} ({from_sys})\n"
            f"[bold]输出坐标:[/bold] [green]{result_lat:.6f}, {result_lon:.6f}[/green] ({to_sys})",
            title="[bold blue]坐标转换结果[/bold blue]",
            border_style="green"
        ))

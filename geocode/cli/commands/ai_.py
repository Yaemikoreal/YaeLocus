"""
AI 命令：对话、分析、路线规划
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from ...config import Config
from ..utils import FAIL, WARN, console, resolve_path

logger = logging.getLogger(__name__)

STATUS_COLUMNS = ["状态", "status", "State", "state"]
ADDRESS_COLUMNS = ["原始地址", "标准化地址", "original_address", "formatted_address", "address"]
LAT_COLUMNS = ["纬度", "latitude", "lat", "LAT"]
LON_COLUMNS = ["经度", "longitude", "lng", "lon", "LON"]


def _find_column(df, candidates: list) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def chat(
    message: str = typer.Argument(..., help="发送给 AI 的消息"),
    input_file: Optional[Path] = typer.Option(None, "-i", "--input", help="附加上下文文件 (CSV/JSON)"),
    system: str = typer.Option("", "--system", help="自定义系统提示词"),
    provider: str = typer.Option("", "--provider", help="AI 供应商"),
    model: str = typer.Option("", "--model", help="AI 模型名"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="流式输出"),
):
    """与 AI 对话

    示例:
        yaelocus ai chat "分析这些地址的地理分布特征"
        yaelocus ai chat -i output/结果.csv "分析这些地址"
    """
    if not Config.AI_ENABLED:
        console.print(f"[red]{FAIL} AI 功能未启用[/red]")
        console.print("[yellow][TIP] 在 .env 中设置 AI_ENABLED=true[/yellow]")
        raise typer.Exit(1)

    messages = []
    sys_msg = system.strip() or "你是一个有帮助的助手。请用中文回答。"
    messages.append({"role": "system", "content": sys_msg})

    user_content = message
    if input_file:
        input_path = resolve_path(str(input_file))
        if input_path.exists():
            try:
                with open(input_path, encoding="utf-8") as f:
                    file_content = f.read()
                if len(file_content) > 10000:
                    file_content = file_content[:10000] + "\n...(截断)"
                    console.print(f"[yellow]{WARN} 文件内容已截断至 10000 字符[/yellow]")
                user_content = f"以下是参考数据:\n{file_content}\n\n{message}"
            except Exception as e:
                console.print(f"[yellow]{WARN} 读取文件失败: {e}[/yellow]")
        else:
            console.print(f"[yellow]{WARN} 文件不存在: {input_path}[/yellow]")

    messages.append({"role": "user", "content": user_content})

    try:
        from ...ai import AIClient
        from ...ai.client import AIClientError
        client_kwargs = {}
        if provider:
            client_kwargs["provider"] = provider
        if model:
            client_kwargs["model"] = model
        client = AIClient(**client_kwargs)
    except Exception as e:
        console.print(f"[red]{FAIL} AI 客户端初始化失败: {e}[/red]")
        raise typer.Exit(1)

    try:
        if stream:
            full_text = ""
            console.print("[cyan]● AI 思考中...[/cyan]", end="")
            for token in client.chat_stream(messages=messages, temperature=0.7):
                if not full_text:
                    console.print("\r[cyan]● AI 回复:[/cyan]")
                full_text += token
                console.print(token, end="", highlight=False)
            console.print()
            answer = full_text.strip() if full_text else ""
            if not answer:
                console.print(f"[yellow]{WARN} AI 未返回任何内容[/yellow]")
                raise typer.Exit(1)
        else:
            with console.status("[cyan]AI 思考中...[/cyan]"):
                resp = client.chat(messages=messages, temperature=0.7)
                from ...ai.client import AIClientError
                try:
                    answer = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                except (KeyError, IndexError, TypeError):
                    console.print(f"[red]{FAIL} AI 返回了意外的响应格式[/red]")
                    raise typer.Exit(1)
    except AIClientError as e:
        console.print(f"[red]{FAIL} AI 调用失败 [{e.code}]: {e}[/red]")
        client.close()
        raise typer.Exit(1)
    except (ConnectionError, PermissionError) as e:
        console.print(f"[red]{FAIL} AI 调用失败: {e}[/red]")
        client.close()
        raise typer.Exit(1)

    client.close()

    if json_output:
        output = {
            "command": "ai_chat",
            "provider": provider or Config.AI_PROVIDER,
            "model": model or Config.AI_MODEL or "",
            "response": answer,
            "status": "success",
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        console.print(Panel(answer, title=f"[bold blue]{provider or 'AI'} 回复[/bold blue]", border_style="blue"))


def route(
    input_file: Path = typer.Option(..., "-i", "--input", help="地理编码结果文件 (CSV/JSON)"),
    map_file: Optional[Path] = typer.Option(None, "-o", "--output", help="输出地图路径"),
    num_routes: int = typer.Option(3, "-n", "--num-routes", help="推荐路线数量"),
    travel_mode: str = typer.Option("driving", "-m", "--mode", help="出行方式 (driving/transit/walking/bicycling)"),
    start_address: str = typer.Option("", "-s", "--start", help="起点地址（不指定则AI自动优化）"),
    headless: bool = typer.Option(False, "--headless", help="非交互模式（通过参数指定规划配置）"),
):
    """交互式路线规划

    基于地理编码结果进行 AI 路线规划。

    示例:
        yaelocus ai route -i output/结果.csv
        yaelocus ai route -i output/结果.csv --headless -n 3 -m driving
    """
    from ...router import RouteWizard

    input_path = resolve_path(str(input_file))
    if not input_path.exists():
        console.print(f"[red]{FAIL} 文件不存在: {input_path}[/red]")
        raise typer.Exit(1)

    params = {
        "num_routes": num_routes,
        "travel_mode": travel_mode,
        "start_address": start_address,
    }
    if start_address:
        from ..utils import _resolve_address_coords
        try:
            coord = _resolve_address_coords(start_address)
            if coord:
                params["start_point"] = (coord["lat"], coord["lon"])
                console.print(f"  [green]起点坐标: {coord['lat']:.4f}, {coord['lon']:.4f}[/green]")
        except Exception:
            pass

    wizard = RouteWizard(
        csv_path=str(input_path),
        map_path=str(resolve_path(str(map_file))) if map_file else None,
        headless=headless or bool(os.environ.get("YAELOCUS_TUI")),
        params=params,
    )
    success = wizard.run()
    if not success:
        raise typer.Exit(1)


def analyze(
    input_file: Path = typer.Option(..., "-i", "--input", help="地理编码结果文件 (CSV)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="流式输出"),
):
    """AI 数据分析

    分析地址的地理分布特征、密度、聚类等。

    示例:
        yaelocus ai analyze -i output/结果.csv
    """
    if not Config.AI_ENABLED:
        console.print(f"[red]{FAIL} AI 功能未启用[/red]")
        raise typer.Exit(1)

    input_path = resolve_path(str(input_file))
    if not input_path.exists():
        console.print(f"[red]{FAIL} 文件不存在: {input_path}[/red]")
        raise typer.Exit(1)

    import pandas as pd
    try:
        if str(input_path).endswith((".xlsx", ".xls")):
            df = pd.read_excel(str(input_path))
        else:
            df = pd.read_csv(input_path, encoding="utf-8-sig")
    except Exception as e:
        console.print(f"[red]{FAIL} 读取文件失败: {e}[/red]")
        raise typer.Exit(1)

    status_col = _find_column(df, STATUS_COLUMNS)
    if status_col and status_col in df.columns:
        df = df[df[status_col] == "成功"]

    if len(df) < 2:
        console.print("[yellow]有效地址不足（至少需要2个）[/yellow]")
        raise typer.Exit(1)

    addr_col = _find_column(df, ADDRESS_COLUMNS)
    lat_col = _find_column(df, LAT_COLUMNS)
    lon_col = _find_column(df, LON_COLUMNS)

    addresses_summary = []
    for _, row in df.iterrows():
        addr = str(row.get(addr_col, "")) if addr_col else ""
        lat = row.get(lat_col, "") if lat_col else ""
        lon = row.get(lon_col, "") if lon_col else ""
        addresses_summary.append(f"- {addr}: ({lat}, {lon})")

    max_items = 50
    if len(addresses_summary) > max_items:
        console.print(f"[yellow]{WARN} 地址数量 {len(addresses_summary)} 超过 {max_items}，仅分析前 {max_items} 条[/yellow]")
        addresses_summary = addresses_summary[:max_items]

    prompt = (
        f"请分析以下 {len(addresses_summary)} 个地址的地理分布特征:\n\n"
        + "\n".join(addresses_summary)
        + "\n\n请从以下维度分析:\n"
        "1. 地理分布概况（城市/区域分布）\n"
        "2. 密度特征（集中/分散）\n"
        "3. 出行建议（如何分组访问效率最高）\n"
        "4. 异常点识别（位置明显偏离的点）\n"
    )

    try:
        from ...ai import AIClient
        from ...ai.client import AIClientError
        client = AIClient()
    except Exception as e:
        console.print(f"[red]{FAIL} AI 客户端初始化失败: {e}[/red]")
        raise typer.Exit(1)

    try:
        if stream:
            console.print("[cyan]● AI 分析中...[/cyan]")
            full_text = ""
            for token in client.chat_stream(
                messages=[
                    {"role": "system", "content": "你是地理数据分析专家。请用中文回答。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            ):
                full_text += token
                console.print(token, end="", highlight=False)
            console.print()
            answer = full_text.strip() if full_text else ""
            if not answer:
                console.print(f"[yellow]{WARN} AI 未返回任何内容[/yellow]")
                raise typer.Exit(1)
        else:
            with console.status("[cyan]AI 分析中...[/cyan]"):
                resp = client.chat(messages=[
                    {"role": "system", "content": "你是地理数据分析专家。请用中文回答。"},
                    {"role": "user", "content": prompt},
                ])
                answer = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except AIClientError as e:
        console.print(f"[red]{FAIL} AI 分析失败 [{e.code}]: {e}[/red]")
        client.close()
        raise typer.Exit(1)

    client.close()

    if json_output:
        print(json.dumps({
            "command": "ai_analyze",
            "total_addresses": len(addresses_summary),
            "analysis": answer,
            "status": "success",
        }, ensure_ascii=False))
    else:
        console.print(Panel(answer, title="[bold cyan]AI 分析结果[/bold cyan]", border_style="cyan"))

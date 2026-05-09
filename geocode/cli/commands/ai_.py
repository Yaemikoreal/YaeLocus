"""
AI 命令：对话、分析、路线规划
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from ..utils import console, OK, FAIL, WARN, resolve_path
from ...config import Config, PROJECT_DIR


def chat(
    message: str = typer.Argument(..., help="发送给 AI 的消息"),
    input_file: Optional[Path] = typer.Option(None, "-i", "--input", help="附加上下文文件 (CSV/JSON)"),
    system: str = typer.Option("", "--system", help="自定义系统提示词"),
    provider: str = typer.Option("", "--provider", help="AI 供应商"),
    model: str = typer.Option("", "--model", help="AI 模型名"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
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
                with open(input_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                if len(file_content) > 10000:
                    file_content = file_content[:10000] + "\n...(截断)"
                user_content = f"以下是参考数据:\n{file_content}\n\n{message}"
            except Exception as e:
                console.print(f"[yellow]{WARN} 读取文件失败: {e}[/yellow]")
        else:
            console.print(f"[yellow]{WARN} 文件不存在: {input_path}[/yellow]")

    messages.append({"role": "user", "content": user_content})

    try:
        from ...ai import AIClient
        client_kwargs = {}
        if provider:
            client_kwargs["provider"] = provider
        if model:
            client_kwargs["model"] = model
        client = AIClient(**client_kwargs)
    except Exception as e:
        console.print(f"[red]{FAIL} AI 客户端初始化失败: {e}[/red]")
        raise typer.Exit(1)

    with console.status("[cyan]AI 思考中...[/cyan]"):
        try:
            resp = client.chat(messages=messages)
            answer = resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
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
):
    """交互式路线规划

    基于地理编码结果进行 AI 路线规划。

    示例:
        yaelocus ai route -i output/结果.csv
    """
    from ...router import RouteWizard

    input_path = resolve_path(str(input_file))
    if not input_path.exists():
        console.print(f"[red]{FAIL} 文件不存在: {input_path}[/red]")
        raise typer.Exit(1)

    wizard = RouteWizard(
        csv_path=str(input_path),
        map_path=str(resolve_path(str(map_file))) if map_file else None,
    )
    wizard.run()


def analyze(
    input_file: Path = typer.Option(..., "-i", "--input", help="地理编码结果文件 (CSV)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
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
        df = pd.read_csv(input_path, encoding="utf-8-sig")
    except Exception as e:
        console.print(f"[red]{FAIL} 读取文件失败: {e}[/red]")
        raise typer.Exit(1)

    if "状态" in df.columns:
        df = df[df["状态"] == "成功"]

    if len(df) < 2:
        console.print(f"[yellow]有效地址不足（至少需要2个）[/yellow]")
        raise typer.Exit(1)

    # 构建地址摘要
    addresses_summary = []
    for _, row in df.iterrows():
        addr = row.get("原始地址", row.get("标准化地址", ""))
        lat = row.get("纬度", "")
        lon = row.get("经度", "")
        addresses_summary.append(f"- {addr}: ({lat}, {lon})")

    prompt = (
        f"请分析以下 {len(addresses_summary)} 个地址的地理分布特征:\n\n"
        + "\n".join(addresses_summary[:50])
        + "\n\n请从以下维度分析:\n"
        "1. 地理分布概况（城市/区域分布）\n"
        "2. 密度特征（集中/分散）\n"
        "3. 出行建议（如何分组访问效率最高）\n"
        "4. 异常点识别（位置明显偏离的点）\n"
    )

    try:
        from ...ai import AIClient
        client = AIClient()
        with console.status("[cyan]AI 分析中...[/cyan]"):
            resp = client.chat(messages=[
                {"role": "system", "content": "你是地理数据分析专家。请用中文回答。"},
                {"role": "user", "content": prompt},
            ])
            answer = resp["choices"][0]["message"]["content"].strip()
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
    except Exception as e:
        console.print(f"[red]{FAIL} AI 分析失败: {e}[/red]")
        raise typer.Exit(1)

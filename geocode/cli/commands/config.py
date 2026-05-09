"""
配置管理命令：设置、诊断、API 测试、配额查看
"""

import typer
from rich.panel import Panel
from rich.table import Table

from ..utils import console, OK, FAIL, WARN
from ...config import Config, PROJECT_DIR


def setup():
    """交互式配置向导（API 密钥 + AI 供应商）"""
    console.print(Panel.fit("[bold yellow]API密钥配置[/bold yellow]", border_style="yellow"))
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
    amap_key = typer.prompt("高德地图 API Key (留空跳过)", default=existing.get('AMAP_KEY', ''), show_default=False)
    if amap_key:
        if len(amap_key) != 32:
            console.print(f"[red]{FAIL} 格式错误: 应为32位字符[/red]")
        else:
            console.print(f"[green]{OK} 格式正确[/green]")
            existing['AMAP_KEY'] = amap_key

    # 百度
    baidu_key = typer.prompt("百度地图 AK (留空跳过)", default=existing.get('BAIDU_AK', ''), show_default=False)
    if baidu_key:
        console.print(f"[green]{OK} 已配置[/green]")
        existing['BAIDU_AK'] = baidu_key

    # 天地图
    tianditu_key = typer.prompt("天地图 TK (留空跳过)", default=existing.get('TIANDITU_TK', ''), show_default=False)
    if tianditu_key:
        console.print(f"[green]{OK} 已配置[/green]")
        existing['TIANDITU_TK'] = tianditu_key

    # AI 配置
    console.print("\n" + "─" * 40)
    console.print("[bold yellow]AI 功能配置[/bold yellow]")
    console.print("[dim]配置后可用 AI 进行路线规划、数据分析等[/dim]\n")

    enable = typer.confirm("是否启用 AI 功能?", default=existing.get("AI_ENABLED", "false").lower() == "true")
    existing["AI_ENABLED"] = "true" if enable else "false"

    if enable:
        from ...ai.providers import BUILTIN_PROVIDERS

        console.print("\n[cyan]选择 AI 供应商:[/cyan]")
        for i, p in enumerate(BUILTIN_PROVIDERS, 1):
            status = "[已配置]" if existing.get(p.api_key_env) else "[未配置]"
            console.print(f"  {i}. {p.display_name} ({p.name}) {status}")

        provider_input = typer.prompt("输入供应商编号或名称", default=existing.get("AI_PROVIDER", "deepseek"))
        existing["AI_PROVIDER"] = provider_input

        for p in BUILTIN_PROVIDERS:
            current = existing.get(p.api_key_env, "")
            key = typer.prompt(f"{p.display_name} API Key (留空跳过)", default=current, show_default=False)
            if key:
                existing[p.api_key_env] = key

        model = typer.prompt("AI 模型名（留空使用供应商默认）", default=existing.get("AI_MODEL", ""), show_default=False)
        if model:
            existing["AI_MODEL"] = model

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# 配置\n")
        for key, val in existing.items():
            f.write(f"{key}={val}\n")

    console.print(f"\n[green]{OK} 配置已保存到 {env_path}[/green]")


def check():
    """环境诊断：检查配置文件、API密钥、网络连通性"""
    console.print(Panel.fit("[bold cyan]环境诊断[/bold cyan]", border_style="cyan"))

    issues = []

    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        console.print(f"[red]{FAIL}[/red] .env 文件不存在")
        issues.append("运行 'config setup' 创建配置")
    else:
        console.print(f"[green]{OK}[/green] .env 文件存在")

    apis = Config.get_available_apis()
    if not apis:
        console.print(f"[red]{FAIL}[/red] 未配置任何API密钥")
        issues.append("运行 'config setup' 配置密钥")
    else:
        console.print(f"[green]{OK}[/green] 已配置API: {', '.join(apis)}")

    from ...ai.providers import get_all_providers
    ai_providers = get_all_providers()
    configured_ais = [p.display_name for p in ai_providers if p.is_available]
    if configured_ais:
        console.print(f"[green]{OK}[/green] AI 供应商已配置: {', '.join(configured_ais)}")
    else:
        console.print(f"[yellow]{WARN}[/yellow] 未配置 AI 供应商")
        if Config.AI_ENABLED:
            issues.append("AI 已启用但未配置 API Key，运行 'config setup' 配置")

    output_dir = PROJECT_DIR / "output"
    if not output_dir.exists():
        console.print(f"[yellow]{WARN}[/yellow] output 目录不存在 (将自动创建)")
    else:
        console.print(f"[green]{OK}[/green] output 目录存在")

    # 缓存统计
    cache_path = PROJECT_DIR / "output" / "geocache.db"
    if cache_path.exists():
        try:
            from ...cache import CacheManager
            cm = CacheManager(str(cache_path))
            stats = cm.get_stats()
            cm.close()
            console.print(f"[green]{OK}[/green] 缓存: {stats['total_entries']} 条 (命中率 {stats['hit_rate']}%)")
        except Exception:
            console.print(f"[yellow]{WARN}[/yellow] 缓存读取失败")

    # 配额统计
    _show_quota()

    if issues:
        console.print("\n[yellow]需要修复:[/yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
    else:
        console.print(f"\n[green]{OK} 环境检查通过[/green]")


def test_api():
    """测试API连通性"""
    console.print(Panel.fit("[bold cyan]API连通性测试[/bold cyan]", border_style="cyan"))

    apis = Config.get_available_apis()
    if not apis:
        console.print(f"[red]{FAIL} 未配置任何API密钥[/red]")
        raise typer.Exit(1)

    import requests

    for api_name in apis:
        console.print(f"\n[cyan]测试 {api_name}...[/cyan]")
        try:
            if api_name == "amap":
                key = Config.AMAP_KEY
                url = f"https://restapi.amap.com/v3/geocode/geo?key={key}&address=北京"
                resp = requests.get(url, timeout=10)
            elif api_name == "baidu":
                key = Config.BAIDU_AK
                url = f"https://api.map.baidu.com/geocoding/v3/?ak={key}&address=北京&output=json"
                resp = requests.get(url, timeout=10)
            elif api_name == "tianditu":
                url = Config.TIANDITU_URL
                params = {"ds": '{"keyWord":"北京"}', "tk": Config.TIANDITU_TK}
                resp = requests.get(url, params=params, timeout=10)
            else:
                continue

            if resp.status_code == 200:
                console.print(f"[green]{OK}[/green] {api_name} 连接正常")
            else:
                console.print(f"[red]{FAIL}[/red] {api_name} 返回状态码: {resp.status_code}")
        except Exception as e:
            console.print(f"[red]{FAIL}[/red] {api_name} 连接失败: {str(e)}")


def _show_quota():
    """显示 API 配额使用情况"""
    from datetime import datetime
    import pandas as pd
    from ..utils import resolve_path

    log_path = resolve_path("output/api调用日志.csv")
    if not log_path.exists():
        return

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


def _legacy_quota():
    """旧版 quota 命令（供弃用别名使用）"""
    console.print(Panel.fit("[bold cyan]API配额状态[/bold cyan]", border_style="cyan"))
    log_path = PROJECT_DIR / "output" / "api调用日志.csv"
    if not log_path.exists():
        console.print("[yellow]无调用日志[/yellow]")
        console.print("[dim]运行地理编码后再查看配额[/dim]")
        return
    _show_quota()

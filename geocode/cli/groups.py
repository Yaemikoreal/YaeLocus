"""
CLI 命令分组定义

四个 Typer 子应用：
- geocode: 地理编码操作
- map: 地图与可视化
- ai: AI 分析与路线规划
- config: 配置管理
"""

import typer

from .commands.geocode import single, batch, reverse_cmd, convert_cmd
from .commands.config import setup, check, test_api
from .commands.cache import cache_cmd
from .commands.map import list_files_cmd, create
from .commands.ai_ import chat, analyze, route

geocode_group = typer.Typer(
    name="geocode",
    help="地理编码操作：地址转坐标、逆地理编码、坐标转换",
    no_args_is_help=True,
)
geocode_group.command(name="single")(single)
geocode_group.command(name="batch")(batch)
geocode_group.command(name="reverse")(reverse_cmd)
geocode_group.command(name="convert")(convert_cmd)

map_group = typer.Typer(
    name="map",
    help="地图与可视化：列出文件、生成地图",
    no_args_is_help=True,
)
map_group.command(name="list")(list_files_cmd)
map_group.command(name="create")(create)

ai_group = typer.Typer(
    name="ai",
    help="AI 功能：对话、数据分析、路线规划",
    no_args_is_help=True,
)
ai_group.command(name="chat")(chat)
ai_group.command(name="analyze")(analyze)
ai_group.command(name="route")(route)

config_group = typer.Typer(
    name="config",
    help="配置管理：API 密钥、环境诊断、缓存管理",
    no_args_is_help=True,
)
config_group.command(name="setup")(setup)
config_group.command(name="check")(check)
config_group.command(name="test-api")(test_api)
config_group.command(name="cache")(cache_cmd)

"""
路线规划整体模块（集成向导）

交互式 CLI 向导，在 run（批量地理编码）之后可选调用。
单一入口 RouteWizard，整合数据加载、AI 流式规划、路线生成、地图输出。
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from geocode.ai import AIClient
from geocode.config import PROJECT_DIR, Config
from geocode.coords import haversine_km
from geocode.map_visualizer import create_map_with_routes

console = Console()


class RouteWizard:
    """交互式路线规划向导

    单一入口，整合全部流程：
    1. 加载批量的地址经纬度数据
    2. 交互式询问规划参数（起点、数量、出行方式）
    3. AI 流式规划路线
    4. 生成结果并绘制到地图

    Usage:
        wizard = RouteWizard("output/地址_经纬度_结果.csv")
        wizard.run()          # 完整交互流程

        # Headless 模式（通过 API 调用）
        wizard = RouteWizard("output/结果.csv", headless=True, params={...})
        wizard.run()
    """

    TRAVEL_MODES = [
        ("driving", "驾车"),
        ("transit", "公交"),
        ("walking", "步行"),
        ("bicycling", "骑行"),
    ]

    def __init__(self, csv_path: str, map_path: Optional[str] = None,
                 headless: bool = False, params: Optional[Dict] = None):
        self.csv_path = Path(csv_path)
        self.map_path = Path(map_path or str(PROJECT_DIR / "output" / "路线规划_地图.html"))
        self.locations: List[Dict] = []
        self.ai_client: Optional[AIClient] = None
        self.headless = headless
        self.headless_params = params or {}

    # ==================== 公开入口 ====================

    def run(self) -> bool:
        """执行完整交互式路线规划

        Returns:
            是否成功完成
        """
        try:
            console.print(Panel.fit("[bold cyan]路线规划向导[/bold cyan]", border_style="cyan"))

            # 1. 加载数据
            if not self._load_data():
                return False

            # 2. 交互参数
            params = self._interactive_prompt()
            if params is None:
                return False

            # 3. AI 流式规划
            routes = self._ai_plan_routes(params)
            if not routes:
                console.print("[red][FAIL] 路线规划失败，未能生成有效路线[/red]")
                return False

            # 4. 显示结果
            self._display_routes(routes)

            # 5. 输出地图
            map_path = self._output_map(routes, params.get("start_point"))
            console.print("\n[green][OK] 路线规划完成！[/green]")
            console.print(f"  [cyan]地图:[/cyan] {map_path}")
            return True

        except KeyboardInterrupt:
            console.print("\n[yellow]用户取消[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red][FAIL] 路线规划异常: {e}[/red]")
            return False
        finally:
            if self.ai_client:
                self.ai_client.close()

    # ==================== 数据加载 ====================

    def _load_data(self) -> bool:
        """加载地址经纬度数据（支持 CSV 和 JSON 格式）"""
        if not self.csv_path.exists():
            console.print(f"[red][FAIL] 文件不存在: {self.csv_path}[/red]")
            return False

        raw = None
        try:
            with open(self.csv_path, encoding="utf-8-sig") as f:
                first_char = f.read(1)
                f.seek(0)
                if first_char == "[":
                    raw = json.load(f)
        except Exception:
            pass

        if raw is not None:
            self.locations = [
                r for r in raw
                if r.get("状态") == "成功" and r.get("纬度") and r.get("经度")
            ]
        else:
            import pandas as pd
            try:
                df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
                status_col = "状态"
                if status_col in df.columns:
                    df = df[df[status_col] == "成功"]
                for _, row in df.iterrows():
                    try:
                        lat = float(row.get("纬度", 0))
                        lon = float(row.get("经度", 0))
                        if lat and lon:
                            self.locations.append({
                                "原始地址": str(row.get("原始地址", "")).strip(),
                                "标准化地址": str(row.get("标准化地址", "")).strip(),
                                "纬度": lat,
                                "经度": lon,
                            })
                    except (ValueError, TypeError):
                        continue
            except Exception as e:
                console.print(f"[red][FAIL] 读取数据失败: {e}[/red]")
                return False

        if not self.locations:
            console.print("[yellow][WARN] 未找到有效的地理编码数据[/yellow]")
            return False

        console.print(f"[green][OK][/green] 加载 [bold]{len(self.locations)}[/bold] 个地址位置")
        return True

    # ==================== 交互式参数收集 ====================

    def _interactive_prompt(self) -> Optional[Dict]:
        """交互式询问规划参数（headless 模式直接返回预设参数）"""
        if self.headless:
            return self.headless_params

        params = {}

        # ----- 总起点 -----
        console.print("\n[bold]总起点设置[/bold]")
        start_choice = typer_prompt_select(
            "是否指定总起点？",
            [("不指定（AI 自动优化）", ""), ("指定起点地址", "specify")],
            default="",
        )
        if start_choice == "specify":
            start_addr = console_input("请输入起点地址: ")
            if start_addr.strip():
                params["start_address"] = start_addr.strip()
                # 尝试解析坐标
                coord = self._resolve_address(start_addr.strip())
                if coord:
                    params["start_point"] = coord
                    console.print(f"  [green]起点坐标: {coord[0]:.4f}, {coord[1]:.4f}[/green]")
                else:
                    console.print("  [yellow]地址未识别，将交由 AI 处理[/yellow]")

        # ----- 路线数量 -----
        console.print("\n[bold]路线数量[/bold]")
        num_routes = console_input("推荐路线数量 (默认 3): ", default="3")
        try:
            params["num_routes"] = max(1, min(10, int(num_routes)))
        except ValueError:
            params["num_routes"] = 3

        # ----- 出行方式 -----
        console.print("\n[bold]出行方式[/bold]")
        mode_choice = typer_prompt_select(
            "选择出行方式",
            [(f"{name} ({key})", key) for key, name in self.TRAVEL_MODES],
            default="driving",
        )
        params["travel_mode"] = mode_choice

        return params

    def _resolve_address(self, address: str) -> Optional[Tuple[float, float]]:
        """解析地址为坐标（使用内置城市表或地理编码）"""
        # 内置城市表
        from geocode.cli.utils import _resolve_address_coords
        try:
            result = _resolve_address_coords(address)
            if result:
                return (result["lat"], result["lon"])
        except Exception:
            pass
        return None

    # ==================== AI 流式规划 ====================

    def _ai_plan_routes(self, params: Dict) -> List[Dict]:
        """AI 流式规划路线"""
        # 准备 AI 客户端
        try:
            self.ai_client = Config.get_ai_client()
        except Exception as e:
            console.print(f"[red][FAIL] AI 客户端初始化失败: {e}[/red]")
            console.print("[yellow]请运行 'config' 配置 AI 供应商[/yellow]")
            return []

        # 构造 prompt
        system_prompt = (
            "你是一个专业的地理路线规划专家。"
            "请基于用户提供的地址坐标数据，规划多条最优出行路线。"
            "返回严格的 JSON 格式，不要包含其他文字。"
        )

        csv_summary = self._build_csv_summary()
        start_constraint = "不指定总起点（AI 自动优化最优路线）"
        if params.get("start_address"):
            start_constraint = f"总起点必须为: {params['start_address']}"

        user_prompt = f"""请根据以下地址数据，规划 {params['num_routes']} 条最优出行路线。

地址数据（已完成地理编码，含经纬度坐标）：
{csv_summary}

规划要求：
1. 总起点：{start_constraint}
2. 出行方式：{params['travel_mode']}
3. 生成 {params['num_routes']} 条不同的路线方案，每条方案应显著不同
4. 每条路线为线性路线（从起点到终点，地址按访问顺序排列）
5. {params['num_routes']} 条路线应分别覆盖不同的地址子集，总体覆盖尽可能多的地址
6. 【最高优先级】路线规划必须严格保证顺路性：
	   - 同一条路线内的所有途经地址必须在**地理上靠近**（同城或同区域），禁止跨县/跨远距离区域
	   - 途经地址必须按**坐标单向排序**（例如自西向东按经度递增，或自北向南按纬度递减），相邻两点间距应均匀且合理
	   - 绝对禁止先到A地→再折返到A地附近→再去远处B地的行为
	   - 若地址分布在多个远距离区域（如不同县），应分多条路线，每条只覆盖一个区域
	   - 宁可减少每条路线的地址数量（3-5个），也绝不允许折返和绕路
	   - 【反例】XX县→YY县（跨县）→XX县（折返回来），这是严重的折返，禁止
	   - 【正例】旺苍县东河镇A→东河镇B→东河镇C，沿经度从西往东依次访问，这才是顺路
	7. 路线描述应说明该方案的优势和设计思路，以及途经顺序如何优化
	8. 途经地址必须从以上列表中精确选取，不可修改地址文本，不可捏造不存在的地址
	9. 所有 estimate 字段请基于坐标间的实际地理距离和出行方式合理估算

请以 JSON 格式返回（不要包含其他文字）：
{{
  "routes": [
    {{
      "name": "路线名称（如"东部线路"）",
      "description": "路线描述（为什么这样规划，途经顺序如何优化，有什么特点）",
      "start_address": "起点地址名称（必须精确匹配输入列表中的地址文本）",
      "end_address": "终点地址名称",
      "waypoints": ["途经地址1（必须精确匹配输入列表中的地址文本）", "途经地址2", ...],
      "estimated_distance_km": 总距离（公里）,
      "estimated_duration_minutes": 预计时间（分钟）,
      "travel_tips": "出行建议"
    }}
  ]
}}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        console.print("\n[cyan]AI 正在规划路线...[/cyan]")
        full_text = ""
        collected_tokens = 0
        stream_failed = False

        try:
            for token in self.ai_client.chat_stream(
                messages=messages,
                temperature=0.3,
                max_tokens=4000,
            ):
                full_text += token
                collected_tokens += len(token)
                if collected_tokens > 20:
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    collected_tokens = 0
        except Exception as e:
            console.print(f"\n[yellow][WARN] AI 流式输出异常: {e}[/yellow]")
            stream_failed = True

        console.print("\n")

        # 流式为空或失败时，回退到非流式调用
        if not full_text or stream_failed:
            if stream_failed:
                console.print("[dim]切换到非流式模式...[/dim]")
            else:
                console.print("[yellow]流式返回为空，尝试非流式模式...[/yellow]")
            try:
                resp = self.ai_client.chat(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4000,
                )
                full_text = resp["choices"][0]["message"]["content"].strip()
            except Exception as e2:
                console.print(f"[red][FAIL] AI 调用失败: {e2}[/red]")
                return []

        if not full_text:
            console.print("[red][FAIL] AI 返回为空[/red]")
            return []

        # 解析 JSON
        routes_data = self._parse_ai_routes(full_text)
        if not routes_data:
            return []

        return self._enrich_routes(routes_data, params)

    def _build_csv_summary(self) -> str:
        """将地址数据整理为 AI 可读的摘要"""
        lines = []
        for i, loc in enumerate(self.locations, 1):
            addr = loc.get("标准化地址") or loc.get("原始地址", "")
            lat = loc.get("纬度", 0)
            lon = loc.get("经度", 0)
            lines.append(f"{i}. {addr} ({lat:.4f}, {lon:.4f})")
        return "\n".join(lines)

    def _parse_ai_routes(self, text: str) -> Optional[Dict]:
        """从 AI 回复中提取 JSON 路线数据（三级解析）"""
        text = text.strip()

        # Level 1: Markdown 代码块
        for pattern in [r"```json\s*\n?(.*?)```", r"```\s*\n?(.*?)```"]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    continue

        # Level 2: 全文 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Level 3: 查找 {} 内容
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _enrich_routes(self, data: Dict, params: Dict) -> List[Dict]:
        """增强路线数据：匹配坐标、计算距离等"""
        routes_raw = data.get("routes", [])
        if not routes_raw:
            console.print("[red][FAIL] AI 返回的路线数据格式无效[/red]")
            return []

        # 建立地址→坐标的查找表
        addr_to_coord = {}
        for loc in self.locations:
            addr = loc.get("标准化地址") or loc.get("原始地址", "")
            addr_clean = addr.strip().lower().replace(" ", "")
            addr_to_coord[addr_clean] = {
                "lat": loc.get("纬度"),
                "lon": loc.get("经度"),
                "address": addr,
            }

        routes = []
        for raw in routes_raw:
            waypoint_addrs = raw.get("waypoints", [])
            waypoints_with_coords = []
            matched = 0

            for wp in waypoint_addrs:
                wp_clean = wp.strip().lower().replace(" ", "")
                if wp_clean in addr_to_coord:
                    waypoints_with_coords.append(addr_to_coord[wp_clean])
                    matched += 1
                else:
                    # 多级模糊匹配
                    best_match = None

                    # Level 2: 包含匹配（选最短项 = 最精确）
                    candidates = []
                    for key, val in addr_to_coord.items():
                        if wp_clean in key or key in wp_clean:
                            candidates.append((len(key), val))
                    if candidates:
                        candidates.sort(key=lambda x: x[0])
                        best_match = candidates[0][1]

                    # Level 3: 分词重叠匹配
                    if best_match is None:
                        wp_normalized = wp_clean.replace("，", ",").replace("、", ",")
                        wp_tokens = set(t for t in wp_normalized.split(",") if t)
                        # 同时也按空格分词
                        for t in list(wp_tokens):
                            for sub in t.split():
                                wp_tokens.add(sub)
                        best_overlap = 0
                        for key, val in addr_to_coord.items():
                            key_tokens = set(t for t in key.replace("，", ",").replace("、", ",").split(",") if t)
                            for t in list(key_tokens):
                                for sub in t.split():
                                    key_tokens.add(sub)
                            overlap = len(wp_tokens & key_tokens)
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_match = val

                    if best_match:
                        waypoints_with_coords.append(best_match)
                        matched += 1
                    else:
                        # 保留文字但无法匹配坐标
                        waypoints_with_coords.append({
                            "address": wp,
                            "lat": None,
                            "lon": None,
                        })

            route = {
                "name": raw.get("name", f"路线 {len(routes) + 1}"),
                "description": raw.get("description", ""),
                "start_address": raw.get("start_address", ""),
                "end_address": raw.get("end_address", ""),
                "waypoints": waypoints_with_coords,
                "matched": matched,
                "total_locations": len(waypoint_addrs),
                "estimated_distance_km": raw.get("estimated_distance_km", 0),
                "estimated_duration_minutes": raw.get("estimated_duration_minutes", 0),
                "travel_tips": raw.get("travel_tips", ""),
                "mode": params.get("travel_mode", "driving"),
            }

            # 计算实际距离
            coords = [(w["lat"], w["lon"]) for w in waypoints_with_coords if w.get("lat")]
            if coords and params.get("start_point"):
                coords.insert(0, params["start_point"])
            if len(coords) >= 2:
                total_dist = 0.0
                for i in range(len(coords) - 1):
                    total_dist += haversine_km(
                        coords[i][0], coords[i][1],
                        coords[i + 1][0], coords[i + 1][1],
                    )
                route["computed_distance_km"] = round(total_dist, 2)

            routes.append(route)

        # 按匹配率降序
        routes.sort(key=lambda r: r["matched"], reverse=True)
        return routes[:params.get("num_routes", 3)]

    # ==================== 结果展示 ====================

    def _display_routes(self, routes: List[Dict]) -> None:
        """展示路线规划结果"""
        console.print("\n" + "─" * 50)
        console.print("[bold cyan]路线规划结果[/bold cyan]")

        for i, r in enumerate(routes, 1):
            color = ["blue", "green", "yellow", "magenta"][(i - 1) % 4]
            dist = r.get("computed_distance_km") or r.get("estimated_distance_km", 0)
            duration = r.get("estimated_duration_minutes", 0)

            console.print(Panel(
                f"[bold]{r['name']}[/bold]\n"
                f"  途经: [cyan]{r['total_locations']}[/cyan] 处地址 "
                f"| 距离: [green]{dist} km[/green] "
                f"| 预计: {duration} 分钟\n"
                f"  描述: {r['description']}\n"
                f"  建议: {r['travel_tips']}",
                title=f"[bold color({color})]路线 {i}[/bold color({color})]",
                border_style=color,
            ))

            # 途经点列表
            waypoints = r.get("waypoints", [])
            if waypoints:
                wp_table = Table(show_header=True, header_style="bold cyan", box=None)
                wp_table.add_column("顺序", justify="right", style="dim")
                wp_table.add_column("地址")
                wp_table.add_column("坐标")
                for j, wp in enumerate(waypoints, 1):
                    coord_str = f"{wp.get('lat', '?'):.4f}, {wp.get('lon', '?'):.4f}" if wp.get("lat") else "未匹配"
                    wp_table.add_row(str(j), wp.get("address", ""), coord_str)
                console.print(wp_table)

    # ==================== 地图输出 ====================

    def _output_map(self, routes: List[Dict], start_point: Optional[Tuple] = None) -> str:
        """输出带路线绘制的地图"""
        # 准备地址标记数据
        markers = []
        for loc in self.locations:
            markers.append({
                "latitude": loc["纬度"],
                "longitude": loc["经度"],
                "original_address": loc.get("原始地址", ""),
                "formatted_address": loc.get("标准化地址", ""),
                "source": loc.get("数据来源", "amap"),
                "coordinate_system": loc.get("坐标系", "GCJ-02"),
            })

        # 调用增强版地图生成
        return create_map_with_routes(
            data=markers,
            routes=routes,
            start_point=start_point,
            output_file=str(self.map_path),
            title="路线规划地图",
        )

    # ==================== 工具方法 ====================



# ==================== 交互式 CLI 工具 ====================


def typer_prompt_select(question: str, options: List[Tuple[str, str]], default: str = "") -> str:
    """交互式选择菜单（数字编号选择）"""
    console.print(f"\n[bold]{question}[/bold]")
    for i, (label, value) in enumerate(options, 1):
        marker = "[green]*[/green]" if value == default else " "
        console.print(f"  {marker} {i}. {label}")

    while True:
        raw = console_input(f"请选择 (1-{len(options)})", default="1")
        try:
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(options):
                return options[idx][1]
        except ValueError:
            pass
        # 尝试匹配标签文本
        for label, value in options:
            if raw.strip().lower() in label.lower() or raw.strip() == value:
                return value
        if default:
            return default


def console_input(prompt: str, default: str = "") -> str:
    """读取用户输入"""
    try:
        if default:
            val = input(f"{prompt} [{default}]: ").strip()
            return val if val else default
        else:
            return input(f"{prompt} ").strip()
    except (EOFError, KeyboardInterrupt):
        return default or ""


__all__ = ["RouteWizard"]

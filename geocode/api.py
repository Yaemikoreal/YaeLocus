"""
Headless API Server — Ink TUI 与 Python 后端之间的桥梁

启动方式:
    python -m geocode.api --port 8765
    python -m geocode.api --port 0  # 随机端口

无 CORS（localhost only），纯 JSON 响应，无 GUI 依赖。
"""

import json
import os
import re
import shlex
import sys
import threading
import time
import uuid
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .ai.client import AIClient
from .ai.system_prompt import build_system_prompt
from .cache import CacheManager
from .config import Config, PROJECT_DIR, OutputPaths
from .geocoder import Geocoder
from .logger import APILogger
from .cli.utils import resolve_path

# ── 全局单例 ──────────────────────────────────────────────────────

_cache: Optional[CacheManager] = None
_logger: Optional[APILogger] = None
_geocoder: Optional[Geocoder] = None
_ai_client: Optional[AIClient] = None

# 后台任务追踪
_tasks: dict = {}
_tasks_lock = threading.Lock()
_cleanup_started = False


def _persist_task(task_id: str, task_data: dict) -> None:
    """将已完成任务写入 JSON 文件，服务器重启后可恢复"""
    try:
        progress_dir = OutputPaths.PROGRESS
        progress_dir.mkdir(parents=True, exist_ok=True)
        task_file = progress_dir / f"{task_id}.json"
        task_file.write_text(json.dumps(task_data, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass  # 持久化失败不影响主流程


def _start_task_cleanup() -> None:
    """启动后台清理线程，定期清理过期任务（超过 1 小时）"""
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True

    def _cleanup_loop():
        while True:
            time.sleep(600)  # 每 10 分钟
            try:
                progress_dir = OutputPaths.PROGRESS
                if not progress_dir.exists():
                    continue
                cutoff = time.time() - 3600
                for f in progress_dir.glob("*.json"):
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                with _tasks_lock:
                    stale = [tid for tid, t in _tasks.items()
                             if t.get("status") in ("done", "error")
                             and t.get("_completed_at", 0) < cutoff]
                    for tid in stale:
                        del _tasks[tid]
            except Exception:
                pass

    threading.Thread(target=_cleanup_loop, daemon=True).start()


def _get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
        # 设置恢复通知回调，写入日志文件
        def _log_recovery(event):
            try:
                recovery_log = OutputPaths.LOG / "cache_recovery.log"
                with open(recovery_log, 'a', encoding='utf-8') as f:
                    f.write(f"{event['timestamp']}: {event['message']}\n")
            except Exception:
                pass
        _cache.set_recovery_callback(_log_recovery)
    return _cache


def _get_logger() -> APILogger:
    global _logger
    if _logger is None:
        _logger = APILogger()
    return _logger


def _get_geocoder() -> Geocoder:
    global _geocoder
    if _geocoder is None:
        _geocoder = Geocoder(_get_cache(), _get_logger())
    return _geocoder


def _get_ai_client() -> Optional[AIClient]:
    global _ai_client
    if _ai_client is None:
        _ai_client = Config.get_ai_client()
    return _ai_client


# ── 应用工厂 ──────────────────────────────────────────────────────

def create_api_app() -> FastAPI:
    app = FastAPI(
        title="YaeLocus API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 健康检查 ──────────────────────────────────────────────────

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "apis": Config.get_available_apis(),
            "ai_enabled": Config.AI_ENABLED and _get_ai_client() is not None,
        }

    # ── Agent Schema 端点 ───────────────────────────────────────────

    @app.get("/api/schema")
    async def get_all_schemas():
        """返回所有命令的 JSON Schema 定义（供 Agent 理解输出格式）"""
        from .agent.schema import SCHEMA_REGISTRY
        return {"schemas": SCHEMA_REGISTRY, "count": len(SCHEMA_REGISTRY)}

    @app.get("/api/schema/{command}")
    async def get_command_schema(command: str):
        """返回指定命令的 JSON Schema"""
        from .agent.schema import get_schema
        schema = get_schema(command)
        if not schema:
            raise HTTPException(404, f"未找到命令 '{command}' 的 schema")
        return {"command": command, "schema": schema}

    @app.get("/api/errors")
    async def get_error_codes():
        """返回所有错误码定义（供 Agent 理解错误类型和恢复路径）"""
        from .agent.errors import get_all_error_definitions
        return {"errors": get_all_error_definitions()}

    # ── 配置 ──────────────────────────────────────────────────────

    @app.get("/api/config")
    async def get_config():
        cache = _get_cache()
        stats = cache.get_stats()
        return {
            "apis": Config.get_available_apis(),
            "ai_enabled": Config.AI_ENABLED,
            "ai_provider": Config.AI_PROVIDER,
            "routing_mode": Config.ROUTING_MODE,
            "cache": {
                "total_entries": stats.get("total_entries", 0),
                "hits": stats.get("hits", 0),
                "misses": stats.get("misses", 0),
                "hit_rate": stats.get("hit_rate", 0),
            },
        }

    @app.post("/api/config/save")
    async def save_config(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
        ai_enabled: str = Form("false"),
        ai_provider: str = Form("deepseek"),
        deepseek_key: str = Form(""),
        qwen_key: str = Form(""),
        glm_key: str = Form(""),
        moonshot_key: str = Form(""),
    ):
        """保存配置到 .env 文件，仅更新非空字段"""
        env_path = PROJECT_DIR / ".env"

        # 读取现有 .env
        existing = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

        # 仅更新非空值（跳过占位符和空值）
        updates = {
            "AMAP_KEY": amap_key,
            "BAIDU_AK": baidu_ak,
            "TIANDITU_TK": tianditu_tk,
            "AI_ENABLED": ai_enabled,
            "AI_PROVIDER": ai_provider,
            "DEEPSEEK_API_KEY": deepseek_key,
            "QWEN_API_KEY": qwen_key,
            "GLM_API_KEY": glm_key,
            "MOONSHOT_API_KEY": moonshot_key,
        }
        for k, v in updates.items():
            if v and v != "........":
                existing[k] = v

        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {"success": True, "message": "配置已保存"}

    @app.post("/api/config/test")
    async def test_api_key(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
    ):
        """测试 API Key 有效性"""
        import requests as req
        results: dict = {}

        if amap_key:
            try:
                r = req.get("https://restapi.amap.com/v3/geocode/geo", params={
                    "key": amap_key, "address": "北京市", "output": "JSON"
                }, timeout=10)
                data = r.json()
                results["amap"] = data.get("status") == "1"
            except Exception:
                results["amap"] = False

        if baidu_ak:
            try:
                r = req.get("https://api.map.baidu.com/geocoding/v3", params={
                    "ak": baidu_ak, "address": "北京市", "output": "json"
                }, timeout=10)
                data = r.json()
                results["baidu"] = data.get("status") == 0
            except Exception:
                results["baidu"] = False

        if tianditu_tk:
            try:
                r = req.get("https://api.tianditu.gov.cn/geocoder", params={
                    "tk": tianditu_tk, "ds": json.dumps({"keyWord": "北京市"}), "type": "geocode"
                }, timeout=10)
                data = r.json()
                results["tianditu"] = data.get("status") == "0"
            except Exception:
                results["tianditu"] = False

        return results

    @app.post("/api/config/reload")
    async def reload_config():
        """重新加载 .env 配置，无需重启服务器"""
        try:
            import importlib
            from . import config
            importlib.reload(config)
            return {"success": True, "message": "配置已重新加载"}
        except Exception as e:
            raise HTTPException(500, f"重新加载配置失败: {e}")

    # ── 缓存管理 ──────────────────────────────────────────────────

    @app.get("/api/cache/stats")
    async def cache_stats():
        cache = _get_cache()
        return cache.get_stats()

    @app.post("/api/cache/clear")
    async def cache_clear():
        cache = _get_cache()
        count = cache.clear()
        return {"cleared": count}

    @app.post("/api/cache/cleanup")
    async def cache_cleanup():
        cache = _get_cache()
        removed = cache.cleanup()
        return {"removed": removed, "message": f"清理了 {removed} 条过期记录"}

    @app.get("/api/cache/export")
    async def cache_export():
        cache = _get_cache()
        stats = cache.get_stats()
        return {"stats": stats, "exported_at": time.time()}

    # ── 文件扫描 ──────────────────────────────────────────────────

    @app.get("/api/files")
    async def list_files():
        data_dir = PROJECT_DIR / "data"
        files = []
        if data_dir.exists():
            for f in sorted(data_dir.iterdir()):
                if f.suffix.lower() in (".csv", ".xlsx", ".xls"):
                    files.append({
                        "name": f.name,
                        "path": str(f.relative_to(PROJECT_DIR)),
                        "size_kb": round(f.stat().st_size / 1024, 1),
                        "modified": f.stat().st_mtime,
                    })
        return {"files": files, "count": len(files)}

    @app.get("/api/maps")
    async def list_maps():
        map_dir = OutputPaths.MAP
        maps = []
        if map_dir.exists():
            for f in sorted(map_dir.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True):
                maps.append({
                    "name": f.name,
                    "path": str(f.absolute()),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "modified": f.stat().st_mtime,
                })
        return {"maps": maps, "count": len(maps)}

    @app.get("/api/map/view/{filename}")
    async def view_map_file(filename: str):
        """在新标签页打开地图 HTML 文件"""
        map_dir = OutputPaths.MAP
        safe_name = os.path.basename(filename)
        file_path = map_dir / safe_name
        if not file_path.exists():
            raise HTTPException(404, "文件不存在")
        if file_path.suffix.lower() != ".html":
            raise HTTPException(400, "仅支持 HTML 文件")
        return FileResponse(str(file_path), media_type="text/html")

    # ── 地理编码 ──────────────────────────────────────────────────

    @app.post("/api/geocode/single")
    async def geocode_single(req: Request):
        try:
            body = await req.json()
        except UnicodeDecodeError:
            raise HTTPException(400, "请求编码错误，请使用 UTF-8 编码")
        except json.JSONDecodeError:
            raise HTTPException(400, "JSON 格式错误")
        address = body.get("address", "").strip()
        if not address:
            raise HTTPException(400, "缺少 address 参数")
        geocoder = _get_geocoder()
        result = geocoder.geocode(address)
        return {
            "success": result.get("success", False),
            "original_address": address,
            "longitude": result.get("longitude"),
            "latitude": result.get("latitude"),
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "coordinate_system": result.get("coordinate_system", "GCJ-02"),
        }

    @app.post("/api/geocode/batch")
    async def geocode_batch(req: Request):
        body = await req.json()
        file_path = body.get("file", "")
        column = body.get("column", "地址")
        if not file_path:
            raise HTTPException(400, "缺少 file 参数")

        input_path = resolve_path(file_path)
        if not input_path.exists():
            raise HTTPException(404, f"文件不存在: {file_path}")

        task_id = str(uuid.uuid4())[:8]
        with _tasks_lock:
            _tasks[task_id] = {"status": "running", "progress": 0, "results": [], "error": None}

        def _run_batch():
            try:
                import pandas as pd
                geocoder = _get_geocoder()
                path_str = str(input_path)

                if input_path.suffix.lower() in (".xlsx", ".xls"):
                    df = pd.read_excel(path_str)
                else:
                    df = pd.read_csv(path_str)

                if column not in df.columns:
                    with _tasks_lock:
                        _tasks[task_id] = {"status": "error", "error": f"列 '{column}' 不存在", "_completed_at": time.time()}
                    return

                addresses = df[column].dropna().astype(str).tolist()
                total = len(addresses)
                results = geocoder.batch_geocode(addresses, progress=False)

                # 保存结果
                df["longitude"] = [r.get("longitude") if r else None for r in results]
                df["latitude"] = [r.get("latitude") if r else None for r in results]
                df["source"] = [r.get("source") if r else None for r in results]

                stem = input_path.stem
                csv_path = OutputPaths.CSV / f"{stem}.csv"
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")

                # 生成地图
                from .map_visualizer import create_map
                map_path = OutputPaths.MAP / f"{stem}_map.html"
                create_map(results, str(map_path))

                with _tasks_lock:
                    _tasks[task_id] = {
                        "status": "done",
                        "progress": 100,
                        "total": total,
                        "success": sum(1 for r in results if r.get("success")),
                        "csv": str(csv_path),
                        "map": str(map_path),
                        "_completed_at": time.time(),
                    }
                _persist_task(task_id, _tasks[task_id])
            except Exception as e:
                with _tasks_lock:
                    _tasks[task_id] = {"status": "error", "error": str(e), "_completed_at": time.time()}
                _persist_task(task_id, _tasks[task_id])

        threading.Thread(target=_run_batch, daemon=True).start()
        return {"task_id": task_id, "status": "running"}

    @app.get("/api/geocode/task/{task_id}")
    async def geocode_task_status(task_id: str):
        with _tasks_lock:
            task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        return task

    @app.post("/api/geocode/batch/stream")
    async def geocode_batch_stream(
        file: UploadFile = File(...),
        column: str = Form("地址"),
        workers: str = Form("auto"),
    ):
        """批量地理编码 — SSE 进度流（多步骤可视化）"""
        if not file.filename:
            raise HTTPException(400, "未选择文件")

        content = await file.read()

        async def generate_progress():
            try:
                import pandas as pd
                geocoder = _get_geocoder()
                filename = file.filename or "uploaded"

                # 步骤 1: 读取文件
                yield f"data: {json.dumps({'step': 'reading', 'label': '读取文件', 'status': 'running'}, ensure_ascii=False)}\n\n"

                ext = Path(filename).suffix.lower()
                if ext in (".xlsx", ".xls"):
                    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
                    df = pd.read_excel(BytesIO(content), engine=engine)
                else:
                    df = pd.read_csv(BytesIO(content), encoding="utf-8-sig")

                total = len(df)
                yield f"data: {json.dumps({'step': 'reading', 'label': '读取文件', 'status': 'done', 'total': total}, ensure_ascii=False)}\n\n"

                # 步骤 2: 处理地址
                if column not in df.columns:
                    error_msg = f"列 '{column}' 不存在，可用列: {list(df.columns)}"
                    yield f"data: {json.dumps({'error': error_msg, 'step': 'processing'}, ensure_ascii=False)}\n\n"
                    return

                addresses = df[column].dropna().astype(str).tolist()
                if len(addresses) == 0:
                    yield f"data: {json.dumps({'error': '未找到有效地址', 'step': 'processing'}, ensure_ascii=False)}\n\n"
                    return

                total = len(addresses)
                yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'running', 'total': total, 'current': 0}, ensure_ascii=False)}\n\n"

                results = []
                success_count = 0
                for i, addr in enumerate(addresses):
                    result = geocoder.geocode(addr)
                    results.append(result)
                    if result.get("success"):
                        success_count += 1

                    # 逐条推送 geocode 结果给前端
                    yield f"data: {json.dumps({'type': 'geocode_result', 'index': i, 'data': result}, ensure_ascii=False)}\n\n"

                    if (i + 1) % 10 == 0 or i == total - 1:
                        yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'running', 'total': total, 'current': i + 1, 'success': success_count}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'done', 'total': total, 'success': success_count}, ensure_ascii=False)}\n\n"

                # 步骤 3: 保存结果
                yield f"data: {json.dumps({'step': 'saving', 'label': '保存结果', 'status': 'running'}, ensure_ascii=False)}\n\n"

                df["longitude"] = [r.get("longitude") if r else None for r in results]
                df["latitude"] = [r.get("latitude") if r else None for r in results]
                df["source"] = [r.get("source") if r else None for r in results]

                stem = Path(filename).stem
                csv_path = OutputPaths.CSV / f"{stem}.csv"
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")

                from .map_visualizer import create_map
                valid_results = [r for r in results if r.get("success")]
                map_path = OutputPaths.MAP / f"{stem}_map.html"
                if valid_results:
                    create_map(valid_results, str(map_path))

                yield f"data: {json.dumps({'step': 'saving', 'label': '保存结果', 'status': 'done', 'csv': str(csv_path), 'map': str(map_path)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate_progress(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @app.post("/api/geocode/reverse")
    async def geocode_reverse(req: Request):
        body = await req.json()
        lat = body.get("latitude", body.get("lat"))
        lon = body.get("longitude", body.get("lon", body.get("lng")))
        if lat is None or lon is None:
            raise HTTPException(400, "缺少 latitude/longitude 参数")
        geocoder = _get_geocoder()
        result = geocoder.reverse_geocode(float(lat), float(lon))
        return {
            "success": result.get("success", False),
            "latitude": lat,
            "longitude": lon,
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
        }

    @app.post("/api/geocode/convert")
    async def geocode_convert(req: Request):
        from . import coords
        body = await req.json()
        lat = body.get("latitude", body.get("lat"))
        lon = body.get("longitude", body.get("lon", body.get("lng")))
        from_sys = body.get("from", "wgs84")
        to_sys = body.get("to", "gcj02")
        if lat is None or lon is None:
            raise HTTPException(400, "缺少 latitude/longitude 参数")

        convert_map = {
            ("wgs84", "gcj02"): coords.wgs84_to_gcj02,
            ("gcj02", "wgs84"): coords.gcj02_to_wgs84,
            ("bd09", "wgs84"): coords.bd09_to_wgs84,
            ("bd09", "gcj02"): coords.bd09_to_gcj02,
        }
        fn = convert_map.get((from_sys, to_sys))
        if not fn:
            raise HTTPException(400, f"不支持的坐标系转换: {from_sys} -> {to_sys}")

        out_lat, out_lon = fn(float(lat), float(lon))
        return {
            "input": {"latitude": lat, "longitude": lon, "system": from_sys},
            "output": {"latitude": round(out_lat, 6), "longitude": round(out_lon, 6), "system": to_sys},
        }

    # ── 命令执行 ──────────────────────────────────────────────────

    @app.post("/api/execute")
    async def execute_command(req: Request):
        """执行 CLI 命令，捕获 stdout/stderr 并返回结构化结果

        安全: CORS 已限定 localhost 来源，浏览器跨域请求会被拦截；
        仅当服务器绑定到非 localhost 且攻击者为同源时才存在风险。
        """
        body = await req.json()
        cmd = body.get("command", "").strip()
        if not cmd:
            raise HTTPException(400, "缺少 command 参数")

        from .cli.app import app as typer_app

        old_stdout, old_stderr = sys.stdout, sys.stderr
        captured_out, captured_err = StringIO(), StringIO()
        sys.stdout, sys.stderr = captured_out, captured_err

        os.environ["YAELOCUS_TUI"] = "1"

        try:
            argv = shlex.split(cmd)
            typer_app(argv, standalone_mode=False)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except Exception as e:
            exit_code = 1
            captured_err.write(str(e))
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        # 剥离 ANSI 转义序列 + Rich box-drawing 字符
        _ansi_re = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        raw_out = captured_out.getvalue()
        clean_out = _ansi_re.sub('', raw_out)
        clean_out = re.sub(r'[─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋╌╍╎╏═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰╱╲╳╴╵╶╷╸╹╺╻╼╽╾╿]', '', clean_out)

        raw_err = captured_err.getvalue()
        clean_err = _ansi_re.sub('', raw_err)

        return {
            "command": cmd,
            "exit_code": exit_code,
            "stdout": clean_out.strip(),
            "stderr": clean_err.strip(),
            "success": exit_code == 0,
        }

    # ── AI 对话 ───────────────────────────────────────────────────

    @app.post("/api/chat")
    async def chat(req: Request):
        """非流式 AI 对话"""
        body = await req.json()
        prompt = body.get("prompt", "").strip()
        context = body.get("context", [])

        if not prompt:
            raise HTTPException(400, "缺少 prompt 参数")

        client = _get_ai_client()
        if not client:
            raise HTTPException(503, "AI 未启用或未配置 API Key")

        system_prompt = build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            *context,
            {"role": "user", "content": prompt},
        ]

        try:
            resp = client.chat(messages, temperature=0.7)
            content = resp["choices"][0]["message"]["content"].strip()
            return {"content": content, "role": "assistant"}
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/chat/stream")
    async def chat_stream(req: Request):
        """流式 AI 对话 — SSE 输出"""
        body = await req.json()
        prompt = body.get("prompt", "").strip()
        context = body.get("context", [])

        if not prompt:
            raise HTTPException(400, "缺少 prompt 参数")

        client = _get_ai_client()
        if not client:
            raise HTTPException(503, "AI 未启用或未配置 API Key")

        system_prompt = build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            *context,
            {"role": "user", "content": prompt},
        ]

        async def generate():
            try:
                for token in client.chat_stream(messages, temperature=0.7):
                    yield f"data: {json.dumps({'token': token})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── 输出文件内容 ──────────────────────────────────────────────

    @app.get("/api/file/content")
    async def read_file_content(path: str = ""):
        """读取 output/ 下文件内容（用于 AI 分析上下文）"""
        if not path:
            raise HTTPException(400, "缺少 path 参数")

        full_path = PROJECT_DIR / path
        # 安全: 只允许读取 output/ 和 data/ 下的文件
        allowed = {str(OutputPaths.ROOT.resolve()), str((PROJECT_DIR / "data").resolve())}
        if not any(str(full_path.resolve()).startswith(d) for d in allowed):
            raise HTTPException(403, "不允许访问该路径")

        if not full_path.exists():
            raise HTTPException(404, f"文件不存在: {path}")

        try:
            import pandas as pd
            if full_path.suffix.lower() in (".xlsx", ".xls"):
                df = pd.read_excel(str(full_path))
            else:
                df = pd.read_csv(str(full_path))
            # 只返回前 100 行
            return {
                "path": path,
                "columns": list(df.columns),
                "rows": len(df),
                "preview": df.head(100).fillna("").to_dict(orient="records"),
            }
        except Exception:
            # 非表格文件，尝试读为文本
            content = full_path.read_text(encoding="utf-8", errors="replace")[:5000]
            return {"path": path, "content": content}

    # ── 在浏览器中打开文件 ─────────────────────────────────────────

    @app.post("/api/open")
    async def open_in_browser(req: Request):
        """在系统默认浏览器中打开文件（仅限 output/ 目录）"""
        body = await req.json()
        path = body.get("path", "").strip()
        if not path:
            raise HTTPException(400, "缺少 path 参数")

        full_path = Path(path)
        if not full_path.exists():
            raise HTTPException(404, f"文件不存在: {path}")

        allowed = str(OutputPaths.ROOT.resolve())
        if not str(full_path.resolve()).startswith(allowed):
            raise HTTPException(403, "不允许打开该路径")

        import webbrowser
        webbrowser.open(str(full_path.absolute()))
        return {"opened": str(full_path.absolute())}

    # ── 挂载 Web GUI (如果已构建) ──────────────────────────────
    web_dist = (Path(__file__).parent.parent / "web_gui" / "dist").resolve()
    if web_dist.exists() and (web_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web_gui")

    _start_task_cleanup()
    return app


# ── 服务器启动 ────────────────────────────────────────────────────


def find_free_port() -> int:
    """找到一个空闲的 TCP 端口"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_api_server(host: str = "127.0.0.1", port: int = 8765):
    """启动 API 服务器（阻塞）。port=0 时自动选择空闲端口"""
    import socket
    import uvicorn
    app = create_api_app()

    if port == 0:
        port = find_free_port()
    else:
        # 检查指定端口是否可用，不可用则回退到随机端口
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
        except OSError:
            port = find_free_port()

    # 写入端口信息供 TUI 发现
    port_file = Path.home() / ".yaelocus_port.json"
    port_file.write_text(json.dumps({"port": port, "host": host}))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YaeLocus API Server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    run_api_server(host=args.host, port=args.port)

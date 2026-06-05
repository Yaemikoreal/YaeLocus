"""
Headless API Server — Ink TUI 与 Python 后端之间的桥梁

启动方式:
    python -m geocode.api --port 8765
    python -m geocode.api --port 0  # 随机端口

所有数据库操作通过 DatabaseManager 统一管理（连接池 + PRAGMA + Schema 迁移）。
"""

import datetime as _dt
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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .ai.client import AIClient
from .ai.system_prompt import build_system_prompt
from .cache import CacheManager
from .chat import ChatManager
from .cli.utils import resolve_path
from .config import ENV_FILE, PROJECT_DIR, Config, OutputPaths
from .db import DatabaseManager
from .geocoder import Geocoder
from .logger import APILogger

# ── 全局单例 ──────────────────────────────────────────────────────

_cache: Optional[CacheManager] = None
_logger: Optional[APILogger] = None


def _find_column(df, candidates: list) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _is_imprecise(result: dict) -> bool:
    """判断地理编码结果精确度是否不足（仅到省/市/区县级）"""
    if not result or not result.get("success"):
        return False
    from .validation.confidence import is_imprecise_result
    return is_imprecise_result(result)


def _server_log(msg: str, level: str = "INFO") -> None:
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    tag = {"INFO": "●", "WARN": "▲", "ERROR": "✗"}.get(level, "●")
    print(f"[{ts}] {tag} {msg}", file=sys.stderr, flush=True)
_geocoder: Optional[Geocoder] = None
_ai_client: Optional[AIClient] = None
_chat_manager: Optional[ChatManager] = None

_tasks: dict = {}
_tasks_lock = threading.Lock()
_file_write_locks: dict = {}
_file_write_locks_lock = threading.Lock()
_cleanup_started = False


def _get_file_write_lock(path_str: str) -> threading.Lock:
    with _file_write_locks_lock:
        if path_str not in _file_write_locks:
            _file_write_locks[path_str] = threading.Lock()
        return _file_write_locks[path_str]


def _safe_write_csv(df, csv_path: Path, task_id: str = "", max_retries: int = 3, delay: float = 1.0) -> Path:
    stem = csv_path.stem
    suffix = csv_path.suffix
    if task_id:
        csv_path = csv_path.with_name(f"{stem}_{task_id}{suffix}")
    lock = _get_file_write_lock(str(csv_path))
    with lock:
        last_err = None
        for attempt in range(max_retries):
            try:
                df.to_csv(str(csv_path), index=False, encoding="utf-8-sig")
                return csv_path
            except PermissionError as e:
                last_err = e
                if attempt < max_retries - 1:
                    import time as _t
                    _t.sleep(delay * (attempt + 1))
                else:
                    fallback = csv_path.with_name(
                        f"{stem}_{task_id or 'fallback'}_{int(time.time())}{suffix}"
                    )
                    try:
                        df.to_csv(str(fallback), index=False, encoding="utf-8-sig")
                        _server_log(f"CSV 写入回退到备用路径: {fallback}", "WARN")
                        return fallback
                    except Exception:
                        _server_log(f"CSV 写入备用路径也失败: {fallback}", "ERROR")
                        raise last_err


def _get_db() -> DatabaseManager:
    return DatabaseManager.get_instance()


def _get_chat_manager() -> ChatManager:
    global _chat_manager
    if _chat_manager is None:
        _chat_manager = ChatManager()
    return _chat_manager


def _persist_task(task_id: str, task_data: dict) -> None:
    task_data["task_id"] = task_id
    try:
        _get_db().save_task(task_data)
    except Exception:
        pass


def _start_task_cleanup() -> None:
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True

    def _cleanup_loop():
        while True:
            time.sleep(600)
            try:
                _get_db().cleanup_old_tasks(30)
                with _tasks_lock:
                    cutoff = time.time() - 30 * 24 * 3600
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


def _record_api_usage(api_name: str, success: bool) -> None:
    try:
        _get_db().record_api_call(api_name, success)
    except Exception:
        pass


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

    _get_db()

    # ── 任务历史端点 ──────────────────────────────────────────────────

    @app.get("/api/tasks")
    async def get_all_tasks():
        tasks = _get_db().get_all_tasks()
        return {"tasks": tasks, "count": len(tasks)}

    @app.get("/api/tasks/{task_id}")
    async def get_task_detail(task_id: str):
        task = _get_db().get_task(task_id)
        if not task:
            with _tasks_lock:
                task = _tasks.get(task_id)
            if task:
                task["task_id"] = task_id
            else:
                raise HTTPException(404, f"任务 '{task_id}' 不存在")

        results_json_path = OutputPaths.PROGRESS / f"{task_id}_results.json"
        if results_json_path.exists():
            try:
                task["results"] = json.loads(results_json_path.read_text(encoding="utf-8"))
            except Exception:
                task["results"] = []
        else:
            task["results"] = []

        return task

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str):
        success = _get_db().delete_task(task_id)
        if not success:
            raise HTTPException(500, "删除任务失败")
        with _tasks_lock:
            if task_id in _tasks:
                del _tasks[task_id]
        return {"success": True, "message": f"任务 '{task_id}' 已删除"}

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
        from .agent.schema import SCHEMA_REGISTRY
        return {"schemas": SCHEMA_REGISTRY, "count": len(SCHEMA_REGISTRY)}

    @app.get("/api/schema/{command}")
    async def get_command_schema(command: str):
        from .agent.schema import get_schema
        schema = get_schema(command)
        if not schema:
            raise HTTPException(404, f"未找到命令 '{command}' 的 schema")
        return {"command": command, "schema": schema}

    @app.get("/api/errors")
    async def get_error_codes():
        from .agent.errors import get_all_error_definitions
        return {"errors": get_all_error_definitions()}

    # ── 配置 ──────────────────────────────────────────────────────

    @app.get("/api/config")
    async def get_config():
        db = _get_db()
        cache = _get_cache()
        stats = cache.get_stats()
        masked = db.get_all_masked_settings()

        return {
            "apis": Config.get_available_apis(),
            "amap_key_configured": bool(Config.AMAP_KEY),
            "amap_key_masked": masked.get("AMAP_KEY", ""),
            "baidu_ak_configured": bool(Config.BAIDU_AK),
            "baidu_ak_masked": masked.get("BAIDU_AK", ""),
            "tianditu_tk_configured": bool(Config.TIANDITU_TK),
            "tianditu_tk_masked": masked.get("TIANDITU_TK", ""),
            "ai_enabled": Config.AI_ENABLED,
            "ai_provider": Config.AI_PROVIDER,
            "ai_model": Config.AI_MODEL,
            "deepseek_key_configured": bool(Config.DEEPSEEK_API_KEY),
            "deepseek_key_masked": masked.get("DEEPSEEK_API_KEY", ""),
            "qwen_key_configured": bool(Config.QWEN_API_KEY),
            "qwen_key_masked": masked.get("QWEN_API_KEY", ""),
            "glm_key_configured": bool(Config.GLM_API_KEY),
            "glm_key_masked": masked.get("GLM_API_KEY", ""),
            "moonshot_key_configured": bool(Config.MOONSHOT_API_KEY),
            "moonshot_key_masked": masked.get("MOONSHOT_API_KEY", ""),
            "routing_mode": Config.ROUTING_MODE,
            "api_usage": db.get_today_usage_all(),
            "cache": stats,
        }

    @app.post("/api/config/save")
    async def save_config(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
        ai_enabled: str = Form("false"),
        ai_provider: str = Form("deepseek"),
        ai_model: str = Form(""),
        deepseek_key: str = Form(""),
        qwen_key: str = Form(""),
        glm_key: str = Form(""),
        moonshot_key: str = Form(""),
        routing_mode: str = Form("ai"),
    ):
        global _geocoder, _ai_client
        db = _get_db()

        env_path = ENV_FILE
        existing = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

        updates = {
            "AMAP_KEY": amap_key,
            "BAIDU_AK": baidu_ak,
            "TIANDITU_TK": tianditu_tk,
            "AI_ENABLED": ai_enabled,
            "AI_PROVIDER": ai_provider,
            "AI_MODEL": ai_model,
            "DEEPSEEK_API_KEY": deepseek_key,
            "QWEN_API_KEY": qwen_key,
            "GLM_API_KEY": glm_key,
            "MOONSHOT_API_KEY": moonshot_key,
            "ROUTING_MODE": routing_mode,
        }

        for k, v in updates.items():
            if v and v != "........":
                existing[k] = v
                db.set_setting(k, v, source="web_gui")

        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)
        Config.reload()

        _geocoder = None
        _ai_client = None

        return {"success": True, "message": "配置已保存并生效"}

    @app.post("/api/config/test")
    async def test_api_key(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
    ):
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

    @app.get("/api/config/history")
    async def get_config_history(key: str = "", limit: int = 50):
        db = _get_db()
        history = db.get_config_history(key=key if key else None, limit=limit)
        return {"history": history, "count": len(history)}

    @app.post("/api/config/reload")
    async def reload_config():
        global _geocoder, _ai_client
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE, override=True)
            Config.reload()
            _geocoder = None
            _ai_client = None
            return {"success": True, "message": "配置已重新加载"}
        except Exception as e:
            raise HTTPException(500, f"重新加载配置失败: {e}") from None

    # ── API 配额 ──────────────────────────────────────────────────

    @app.get("/api/usage")
    async def get_api_usage(days: int = 30):
        db = _get_db()
        usage = db.get_api_usage(days=days)
        today = db.get_today_usage_all()
        return {"usage": usage, "today": today}

    @app.get("/api/usage/{api_name}")
    async def get_api_usage_detail(api_name: str, days: int = 30):
        db = _get_db()
        return {
            "api_name": api_name,
            "today": db.get_today_usage(api_name),
            "history": db.get_api_usage(api_name=api_name, days=days),
        }

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
        entries = cache.export_entries()
        return {"stats": stats, "exported_at": time.time(), "entries": entries}

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
            raise HTTPException(400, "请求编码错误，请使用 UTF-8 编码") from None
        except json.JSONDecodeError:
            raise HTTPException(400, "JSON 格式错误") from None
        address = body.get("address", "").strip()
        if not address:
            raise HTTPException(400, "缺少 address 参数")
        geocoder = _get_geocoder()
        result = geocoder.geocode(address)

        if result.get("source"):
            _record_api_usage(result["source"], result.get("success", False))

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
            "confidence": result.get("confidence"),
            "warning": result.get("warning"),
            "error": result.get("error"),
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
                _server_log(f"批量编码开始 — 文件: {input_path.name}")
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

                address_to_result = {}
                for addr, result in zip(addresses, results):
                    addr_key = str(addr).strip()
                    address_to_result[addr_key] = result

                longitude_list = []
                latitude_list = []
                source_list = []
                formatted_address_list = []
                province_list = []
                city_list = []
                district_list = []
                precision_level_list = []
                status_list = []

                for addr in df[column]:
                    addr_str = str(addr).strip() if pd.notna(addr) else ""
                    result = address_to_result.get(addr_str)
                    if result and result.get("success"):
                        longitude_list.append(result.get("longitude"))
                        latitude_list.append(result.get("latitude"))
                        source_list.append(result.get("source"))
                        formatted_address_list.append(result.get("formatted_address") or "")
                        province_list.append(result.get("province"))
                        city_list.append(result.get("city"))
                        district_list.append(result.get("district"))
                        precision_level_list.append(result.get("precision_level"))
                        if not result.get("formatted_address"):
                            status_list.append("失败")
                        elif _is_imprecise(result):
                            status_list.append("精确度不足")
                        else:
                            status_list.append("成功")
                    elif result:
                        longitude_list.append(None)
                        latitude_list.append(None)
                        source_list.append(result.get("source"))
                        formatted_address_list.append(None)
                        province_list.append(None)
                        city_list.append(None)
                        district_list.append(None)
                        precision_level_list.append(None)
                        status_list.append("失败")
                    else:
                        longitude_list.append(None)
                        latitude_list.append(None)
                        source_list.append(None)
                        formatted_address_list.append(None)
                        province_list.append(None)
                        city_list.append(None)
                        district_list.append(None)
                        precision_level_list.append(None)
                        status_list.append("空地址" if not addr_str else "未处理")

                df["longitude"] = longitude_list
                df["latitude"] = latitude_list
                df["source"] = source_list
                df["formatted_address"] = formatted_address_list
                df["province"] = province_list
                df["city"] = city_list
                df["district"] = district_list
                df["precision_level"] = precision_level_list
                df["status"] = status_list

                rework_indices = []
                for ri, r in enumerate(results):
                    if r and r.get("success") and (
                        not r.get("formatted_address") or _is_imprecise(r)
                    ):
                        rework_indices.append(ri)

                rework_count = 0
                if rework_indices:
                    _server_log(f"非SSE批量: 发现 {len(rework_indices)} 条需返工的结果")
                    for ri in rework_indices:
                        addr = addresses[ri]
                        geocoder.cache.delete(addr)
                        rework_result = geocoder._rework_geocode(addr)
                        if rework_result and rework_result.get("success"):
                            old_r = results[ri]
                            old_had_addr = bool(old_r and old_r.get("formatted_address"))
                            new_has_addr = bool(rework_result.get("formatted_address"))
                            old_imprecise = _is_imprecise(old_r) if old_r else True
                            new_precise = not _is_imprecise(rework_result)
                            if (not old_had_addr and new_has_addr) or (old_imprecise and new_precise and new_has_addr):
                                results[ri] = rework_result
                                rework_count += 1

                    if rework_count > 0:
                        address_to_result_rework = {}
                        for addr, result in zip(addresses, results):
                            addr_key = str(addr).strip()
                            address_to_result_rework[addr_key] = result
                        for col_name, field_name in [
                            ("formatted_address", "formatted_address"),
                            ("province", "province"), ("city", "city"),
                            ("district", "district"), ("precision_level", "precision_level"),
                            ("longitude", "longitude"), ("latitude", "latitude"),
                            ("source", "source"),
                        ]:
                            if col_name in df.columns:
                                vals = []
                                for addr in df[column]:
                                    addr_str = str(addr).strip() if pd.notna(addr) else ""
                                    r = address_to_result_rework.get(addr_str)
                                    vals.append(r.get(field_name) if r else None)
                                df[col_name] = vals
                        for row_idx, addr in enumerate(df[column]):
                            addr_str = str(addr).strip() if pd.notna(addr) else ""
                            r = address_to_result_rework.get(addr_str)
                            if r and r.get("success"):
                                if not r.get("formatted_address"):
                                    df.at[row_idx, "status"] = "失败"
                                elif _is_imprecise(r):
                                    df.at[row_idx, "status"] = "精确度不足"
                                else:
                                    df.at[row_idx, "status"] = "成功"

                stem = input_path.stem
                csv_path = OutputPaths.CSV / f"{stem}.csv"
                actual_csv = _safe_write_csv(df, csv_path, task_id)

                from .map_visualizer import create_map
                valid_for_map = [r for r in results if r.get("success") and r.get("formatted_address") and not _is_imprecise(r)]
                map_path = OutputPaths.MAP / f"{stem}_map.html"
                if valid_for_map:
                    create_map(valid_for_map, str(map_path))

                with _tasks_lock:
                    success_n = sum(1 for r in results if r and r.get("success") and r.get("formatted_address") and not _is_imprecise(r))
                    _tasks[task_id] = {
                        "status": "done",
                        "progress": 100,
                        "total": total,
                        "success": success_n,
                        "csv": str(actual_csv),
                        "map": str(map_path) if valid_for_map else None,
                        "rework_count": rework_count,
                        "_completed_at": time.time(),
                    }
                _persist_task(task_id, _tasks[task_id])
                _server_log(f"批量编码完成 — {success_n}/{total} 成功, 地图: {map_path.name}")
            except Exception as e:
                with _tasks_lock:
                    _tasks[task_id] = {"status": "error", "error": str(e), "_completed_at": time.time()}
                _persist_task(task_id, _tasks[task_id])
                _server_log(f"批量编码失败 — {e}", "ERROR")

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
        city: Optional[str] = Form(None),
    ):
        if not file.filename:
            raise HTTPException(400, "未选择文件")

        content = await file.read()
        filename = file.filename or "uploaded"

        async def generate_progress():
            import asyncio as _asyncio
            task_id = str(uuid.uuid4())[:8]
            started_at = time.time()
            yield f"data: {json.dumps({'task_id': task_id}, ensure_ascii=False)}\n\n"
            await _asyncio.sleep(0)

            try:
                import pandas as pd
                _server_log(f"SSE 批量编码开始 — 文件: {filename}")
                geocoder = _get_geocoder()

                yield f"data: {json.dumps({'step': 'reading', 'label': '读取文件', 'status': 'running'}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

                ext = Path(filename).suffix.lower()
                loop = _asyncio.get_event_loop()
                if ext in (".xlsx", ".xls"):
                    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
                    df = await loop.run_in_executor(None, lambda: pd.read_excel(BytesIO(content), engine=engine))
                else:
                    df = await loop.run_in_executor(None, lambda: pd.read_csv(BytesIO(content), encoding="utf-8-sig"))

                total = len(df)
                yield f"data: {json.dumps({'step': 'reading', 'label': '读取文件', 'status': 'done', 'total': total, 'current': total}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

                if column not in df.columns:
                    error_msg = f"列 '{column}' 不存在，可用列: {list(df.columns)}"
                    yield f"data: {json.dumps({'error': error_msg, 'step': 'processing'}, ensure_ascii=False)}\n\n"
                    await _asyncio.sleep(0)
                    _persist_task(task_id, {
                        "task_id": task_id, "status": "error", "input_file": filename,
                        "column": column, "city": city, "total": 0, "success": 0,
                        "failed": 0, "started_at": started_at,
                        "completed_at": time.time(), "error": error_msg,
                    })
                    return

                addresses = df[column].dropna().astype(str).tolist()
                if len(addresses) == 0:
                    yield f"data: {json.dumps({'error': '未找到有效地址', 'step': 'processing'}, ensure_ascii=False)}\n\n"
                    await _asyncio.sleep(0)
                    _persist_task(task_id, {
                        "task_id": task_id, "status": "error", "input_file": filename,
                        "column": column, "city": city, "total": 0, "success": 0,
                        "failed": 0, "started_at": started_at,
                        "completed_at": time.time(), "error": "未找到有效地址",
                    })
                    return

                if city:
                    city_normalized = city.strip()
                    if not city_normalized.endswith("市") and not city_normalized.endswith("区") and not city_normalized.endswith("县"):
                        city_normalized = city_normalized + "市"
                    addresses_with_city = []
                    for addr in addresses:
                        if "市" in addr:
                            addresses_with_city.append(addr)
                        else:
                            addresses_with_city.append(f"{city_normalized}{addr}")
                    addresses = addresses_with_city

                total = len(addresses)
                yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'running', 'total': total, 'current': 0, 'success': 0}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

                use_parallel = workers != "1"
                num_workers = 3 if use_parallel else 1

                cached_results = await loop.run_in_executor(
                    None, lambda: geocoder.cache.get_batch_prefetch(addresses)
                )
                uncached_indices = []
                uncached_addresses = []
                for idx, addr in enumerate(addresses):
                    if cached_results.get(addr) is None:
                        uncached_indices.append(idx)
                        uncached_addresses.append(addr)

                results = [None] * total
                for idx, addr in enumerate(addresses):
                    if cached_results.get(addr) is not None:
                        results[idx] = cached_results[addr]

                success_count = sum(1 for r in results if r and r.get("success"))
                cached_count = total - len(uncached_addresses)
                if cached_count > 0:
                    yield f"data: {json.dumps({'step': 'processing', 'label': f'缓存命中 {cached_count} 条', 'status': 'running', 'total': total, 'current': cached_count, 'success': success_count}, ensure_ascii=False)}\n\n"

                geocode_func = geocoder.geocode_parallel if use_parallel else geocoder.geocode

                if uncached_addresses:
                    from concurrent.futures import ThreadPoolExecutor
                    from concurrent.futures import as_completed as _as_completed

                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        futures = {
                            executor.submit(geocode_func, addr): uncached_indices[i]
                            for i, addr in enumerate(uncached_addresses)
                        }

                        for future in _as_completed(futures):
                            idx = futures[future]
                            try:
                                result = future.result()
                                results[idx] = result
                            except Exception as e:
                                results[idx] = {
                                    "success": False,
                                    "original_address": addresses[idx],
                                    "error": str(e),
                                    "confidence": {"total": 0, "issues": [str(e)], "is_trustworthy": False}
                                }

                            if results[idx] and results[idx].get("success"):
                                success_count += 1
                                src = results[idx].get("source") or results[idx].get("sources", [""])[0] if results[idx].get("sources") else results[idx].get("source")
                                if src:
                                    _record_api_usage(src, True)

                                sources = results[idx].get("sources", [])
                                for src in sources:
                                    if src:
                                        _record_api_usage(src, True)
                            elif results[idx] and results[idx].get("source"):
                                _record_api_usage(results[idx]["source"], False)

                            i = idx
                            yield f"data: {json.dumps({'type': 'geocode_result', 'index': i, 'data': results[idx]}, ensure_ascii=False)}\n\n"
                            await _asyncio.sleep(0)

                            done = sum(1 for r in results if r is not None)
                            progress_interval = 1 if total <= 20 else 5
                            if done % progress_interval == 0 or done == total:
                                yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'running', 'total': total, 'current': done, 'success': success_count}, ensure_ascii=False)}\n\n"
                                await _asyncio.sleep(0)

                yield f"data: {json.dumps({'step': 'processing', 'label': '处理地址', 'status': 'done', 'total': total, 'current': total, 'success': success_count}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

                yield f"data: {json.dumps({'step': 'saving', 'label': '保存结果', 'status': 'running'}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

                address_to_result = {}
                for addr, result in zip(addresses, results):
                    addr_key = str(addr).strip()
                    address_to_result[addr_key] = result

                longitude_list = []
                latitude_list = []
                source_list = []
                formatted_address_list = []
                province_list = []
                city_list = []
                district_list = []
                precision_level_list = []
                status_list = []

                for addr in df[column]:
                    addr_str = str(addr).strip() if pd.notna(addr) else ""
                    result = address_to_result.get(addr_str)
                    if result and result.get("success"):
                        longitude_list.append(result.get("longitude"))
                        latitude_list.append(result.get("latitude"))
                        source_list.append(result.get("source"))
                        formatted_address_list.append(result.get("formatted_address") or "")
                        province_list.append(result.get("province"))
                        city_list.append(result.get("city"))
                        district_list.append(result.get("district"))
                        precision_level_list.append(result.get("precision_level"))
                        if not result.get("formatted_address"):
                            status_list.append("失败")
                        elif _is_imprecise(result):
                            status_list.append("精确度不足")
                        else:
                            status_list.append("成功")
                    elif result:
                        longitude_list.append(None)
                        latitude_list.append(None)
                        source_list.append(result.get("source"))
                        formatted_address_list.append(None)
                        province_list.append(None)
                        city_list.append(None)
                        district_list.append(None)
                        precision_level_list.append(None)
                        status_list.append("失败")
                    else:
                        longitude_list.append(None)
                        latitude_list.append(None)
                        source_list.append(None)
                        formatted_address_list.append(None)
                        province_list.append(None)
                        city_list.append(None)
                        district_list.append(None)
                        precision_level_list.append(None)
                        status_list.append("空地址" if not addr_str else "未处理")

                df["longitude"] = longitude_list
                df["latitude"] = latitude_list
                df["source"] = source_list
                df["formatted_address"] = formatted_address_list
                df["province"] = province_list
                df["city"] = city_list
                df["district"] = district_list
                df["precision_level"] = precision_level_list
                df["status"] = status_list

                stem = Path(filename).stem
                csv_path = OutputPaths.CSV / f"{stem}.csv"
                actual_csv = _safe_write_csv(df, csv_path, task_id)

                results_json_path = OutputPaths.PROGRESS / f"{task_id}_results.json"
                try:
                    results_json_path.write_text(
                        json.dumps(results, ensure_ascii=False, default=str),
                        encoding="utf-8"
                    )
                except Exception:
                    pass

                rework_indices = []
                for ri, r in enumerate(results):
                    if r and r.get("success") and (
                        not r.get("formatted_address") or _is_imprecise(r)
                    ):
                        rework_indices.append(ri)

                rework_count = 0
                imprecise_fixed_count = 0
                if rework_indices:
                    _server_log(f"发现 {len(rework_indices)} 条需返工的结果（空地址或精确度不足），开始返工")
                    yield f"data: {json.dumps({'step': 'rework', 'label': '返工不精确结果', 'status': 'running', 'total': len(rework_indices), 'current': 0}, ensure_ascii=False)}\n\n"
                    await _asyncio.sleep(0)
                    loop = _asyncio.get_event_loop()
                    for ri_idx, ri in enumerate(rework_indices):
                        addr = addresses[ri]
                        await loop.run_in_executor(None, geocoder.cache.delete, addr)
                        rework_result = await loop.run_in_executor(None, geocoder._rework_geocode, addr)
                        improved = False
                        if rework_result and rework_result.get("success"):
                            old_r = results[ri]
                            old_had_addr = bool(old_r and old_r.get("formatted_address"))
                            new_has_addr = bool(rework_result.get("formatted_address"))
                            old_imprecise = _is_imprecise(old_r) if old_r else True
                            new_precise = not _is_imprecise(rework_result)
                            if not old_had_addr and new_has_addr:
                                improved = True
                            elif old_imprecise and new_precise and new_has_addr:
                                improved = True
                                imprecise_fixed_count += 1
                            if improved:
                                results[ri] = rework_result
                                rework_count += 1
                        if (ri_idx + 1) % 3 == 0 or ri_idx + 1 == len(rework_indices):
                            yield f"data: {json.dumps({'step': 'rework', 'label': '返工不精确结果', 'status': 'running', 'total': len(rework_indices), 'current': ri_idx + 1, 'success': rework_count}, ensure_ascii=False)}\n\n"
                            await _asyncio.sleep(0)

                    if rework_count > 0:
                        _server_log(f"返工完成 — {rework_count}/{len(rework_indices)} 条改善成功（含 {imprecise_fixed_count} 条精度提升）")
                        address_to_result_rework = {}
                        for addr, result in zip(addresses, results):
                            addr_key = str(addr).strip()
                            address_to_result_rework[addr_key] = result
                        for col_name, field_name in [
                            ("formatted_address", "formatted_address"),
                            ("province", "province"), ("city", "city"),
                            ("district", "district"), ("precision_level", "precision_level"),
                            ("longitude", "longitude"), ("latitude", "latitude"),
                            ("source", "source"),
                        ]:
                            if col_name in df.columns:
                                vals = []
                                for addr in df[column]:
                                    addr_str = str(addr).strip() if pd.notna(addr) else ""
                                    r = address_to_result_rework.get(addr_str)
                                    vals.append(r.get(field_name) if r else None)
                                df[col_name] = vals
                        for row_idx, addr in enumerate(df[column]):
                            addr_str = str(addr).strip() if pd.notna(addr) else ""
                            r = address_to_result_rework.get(addr_str)
                            if r and r.get("success"):
                                if not r.get("formatted_address"):
                                    df.at[row_idx, "status"] = "失败"
                                elif _is_imprecise(r):
                                    df.at[row_idx, "status"] = "精确度不足"
                                else:
                                    df.at[row_idx, "status"] = "成功"
                        actual_csv = _safe_write_csv(df, csv_path, task_id)
                        yield f"data: {json.dumps({'step': 'saving', 'label': '返工结果已保存', 'status': 'done', 'csv': str(actual_csv), 'rework_count': rework_count}, ensure_ascii=False)}\n\n"
                        await _asyncio.sleep(0)

                from .map_visualizer import create_map
                valid_for_map = [r for r in results if r.get("success") and r.get("formatted_address") and not _is_imprecise(r)]
                map_path = OutputPaths.MAP / f"{stem}_map.html"
                if valid_for_map:
                    create_map(valid_for_map, str(map_path))

                completed_at = time.time()
                success_count = sum(1 for r in results if r and r.get("success") and r.get("formatted_address") and not _is_imprecise(r))
                _persist_task(task_id, {
                    "task_id": task_id, "status": "done", "input_file": filename,
                    "column": column, "city": city, "total": total,
                    "success": success_count, "failed": total - success_count,
                    "csv_output": str(actual_csv),
                    "map_output": str(map_path) if valid_for_map else None,
                    "started_at": started_at, "completed_at": completed_at,
                    "duration_sec": round(completed_at - started_at, 1),
                    "rework_count": rework_count,
                    "error": None,
                })

                yield f"data: {json.dumps({'step': 'saving', 'label': '保存结果', 'status': 'done', 'csv': str(actual_csv), 'map': str(map_path) if valid_for_map else None}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)
                _server_log(f"SSE 批量编码完成 — {success_count}/{total} 成功, 耗时 {completed_at - started_at:.1f}s")
                yield "data: [DONE]\n\n"

            except Exception as e:
                _server_log(f"SSE 批量编码失败 — {e}", "ERROR")
                _persist_task(task_id, {
                    "task_id": task_id, "status": "error", "input_file": filename,
                    "column": column, "city": city, "total": 0, "success": 0,
                    "failed": 0, "started_at": started_at,
                    "completed_at": time.time(), "error": str(e),
                })
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                await _asyncio.sleep(0)

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

        if result.get("source"):
            _record_api_usage(result["source"], result.get("success", False))

        return {
            "success": result.get("success", False),
            "latitude": lat,
            "longitude": lon,
            "formatted_address": result.get("formatted_address"),
            "province": result.get("province"),
            "city": result.get("city"),
            "district": result.get("district"),
            "source": result.get("source"),
            "coordinate_system": result.get("coordinate_system"),
            "confidence": result.get("confidence"),
            "warning": result.get("warning"),
            "error": result.get("error"),
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

    INTERACTIVE_COMMAND_PREFIXES = [
        "ai route ",
        "yaelocus ai route ",
        "config setup",
        "yaelocus config setup",
    ]

    @app.post("/api/execute")
    async def execute_command(req: Request):
        body = await req.json()
        cmd = body.get("command", "").strip()
        if not cmd:
            raise HTTPException(400, "缺少 command 参数")

        cmd_lower = cmd.lower()
        for prefix in INTERACTIVE_COMMAND_PREFIXES:
            if cmd_lower.startswith(prefix) and "--headless" not in cmd_lower:
                return {
                    "command": cmd,
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": f"命令 '{cmd.split()[0]} {cmd.split()[1] if len(cmd.split()) > 1 else ''}' 需要交互式输入，请使用对应的 Web API。路线规划请使用 /api/ai/route，数据分析请使用 /api/ai/analyze/stream。",
                    "success": False,
                }

        import asyncio

        from .cli.app import app as typer_app

        def _run_cmd():
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
            return exit_code, captured_out.getvalue(), captured_err.getvalue()

        try:
            exit_code, raw_out, raw_err = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _run_cmd),
                timeout=120,
            )
        except asyncio.TimeoutError:
            return {
                "command": cmd,
                "exit_code": 124,
                "stdout": "",
                "stderr": "命令执行超时 (120秒)。如果命令需要交互式输入，请使用对应的 Web API。",
                "success": False,
            }

        _ansi_re = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        clean_out = _ansi_re.sub('', raw_out)
        clean_out = re.sub(r'[─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯╰╱╲╳╴┵┶┷╸╹╺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋╌╍╎╏═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰]', '', clean_out)
        clean_err = _ansi_re.sub('', raw_err)

        return {
            "command": cmd,
            "exit_code": exit_code,
            "stdout": clean_out.strip(),
            "stderr": clean_err.strip(),
            "success": exit_code == 0,
        }

    # ── AI 对话 ───────────────────────────────────────────────────

    def _validate_context(context: list) -> list:
        if not isinstance(context, list):
            return []
        validated = []
        for msg in context:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            validated.append({"role": role, "content": content})
        return validated

    @app.post("/api/chat")
    async def chat(req: Request):
        body = await req.json()
        prompt = body.get("prompt", "").strip()
        context = _validate_context(body.get("context", []))

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
            from .ai.client import AIClientError
            resp = client.chat(messages, temperature=0.7)
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not content:
                return {"content": "(AI 返回了空内容)", "role": "assistant"}
            return {"content": content, "role": "assistant"}
        except AIClientError as e:
            _server_log(f"AI chat 错误 [{e.code}]: {e}", "ERROR")
            raise HTTPException(500, f"AI 调用失败: {e}") from None
        except Exception as e:
            _server_log(f"AI chat 未知错误: {e}", "ERROR")
            raise HTTPException(500, f"AI 调用异常: {e}") from None

    @app.post("/api/chat/stream")
    async def chat_stream(req: Request):
        body = await req.json()
        prompt = body.get("prompt", "").strip()
        context = _validate_context(body.get("context", []))
        session_id = body.get("session_id")

        if not prompt:
            raise HTTPException(400, "缺少 prompt 参数")

        client = _get_ai_client()
        if not client:
            raise HTTPException(503, "AI 未启用或未配置 API Key")

        if session_id:
            cm = _get_chat_manager()
            cm.add_message(session_id, "user", prompt)

        if session_id:
            context = _get_chat_manager().build_context(session_id)
        elif not context:
            context = []

        system_prompt = build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            *context,
            {"role": "user", "content": prompt},
        ]

        async def generate():
            try:
                for chunk in client.chat_stream(messages, temperature=0.7):
                    if isinstance(chunk, dict):
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    elif isinstance(chunk, str):
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                from .ai.client import AIClientError
                if isinstance(e, AIClientError):
                    yield f"data: {json.dumps({'error': str(e), 'code': getattr(e, 'code', 'unknown')})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': str(e), 'code': 'unknown'})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── AI 对话会话管理 ──────────────────────────────────────────

    @app.get("/api/chat/sessions")
    async def list_sessions():
        cm = _get_chat_manager()
        sessions = cm.list_sessions(limit=20)
        return {"sessions": sessions, "count": len(sessions)}

    @app.post("/api/chat/sessions")
    async def create_session(req: Request):
        body = await req.json()
        title = body.get("title", "")
        cm = _get_chat_manager()
        return cm.create_session(title=title)

    @app.get("/api/chat/sessions/{session_id}")
    async def get_session(session_id: str):
        cm = _get_chat_manager()
        session = cm.get_session(session_id)
        if not session:
            raise HTTPException(404, "会话不存在")
        messages = cm.get_messages(session_id)
        return {"session": session, "messages": messages}

    @app.delete("/api/chat/sessions/{session_id}")
    async def delete_session(session_id: str):
        cm = _get_chat_manager()
        cm.delete_session(session_id)
        return {"status": "ok"}

    @app.post("/api/chat/sessions/{session_id}/messages")
    async def add_message(session_id: str, req: Request):
        body = await req.json()
        role = body.get("role", "user")
        content = body.get("content", "")
        reasoning = body.get("reasoning", "")
        if role not in ("user", "assistant", "system"):
            raise HTTPException(400, f"无效的 role: {role}")
        if not content and not reasoning:
            raise HTTPException(400, "消息内容不能为空")
        cm = _get_chat_manager()
        session = cm.get_session(session_id)
        if not session:
            raise HTTPException(404, "会话不存在")
        return cm.add_message(session_id, role, content, reasoning)

    @app.post("/api/chat/sessions/{session_id}/compact")
    async def compact_session(session_id: str, req: Request):
        body = await req.json()
        summary = body.get("summary", "")
        if not summary:
            client = _get_ai_client()
            if client:
                cm = _get_chat_manager()
                messages = cm.get_all_messages(session_id)
                context_parts = []
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if content:
                        context_parts.append(f"{role}: {content[:300]}")
                prompt = "请用中文简要总结以下对话的关键信息，保留重要上下文：\n\n" + "\n".join(context_parts)
                try:
                    resp = client.chat([
                        {"role": "system", "content": "你是对话摘要助手。请用2-3句话概括对话要点。"},
                        {"role": "user", "content": prompt},
                    ], temperature=0.3)
                    summary = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                except Exception as e:
                    _server_log(f"AI 摘要生成失败: {e}", "WARN")
                    summary = f"[对话摘要生成失败] 原始对话共 {len(messages)} 条消息"
        cm = _get_chat_manager()
        cm.compact_session(session_id, summary)
        return {"status": "ok", "summary": summary}

    @app.get("/api/chat/sessions/{session_id}/context")
    async def get_session_context(session_id: str, max_messages: int = 30):
        cm = _get_chat_manager()
        context = cm.build_context(session_id, max_messages=max_messages)
        return {"context": context}

    # ── AI Agent 循环 (统一后端) ──────────────────────────────────────

    @app.post("/api/chat/agent")
    async def chat_agent_stream(req: Request):
        """统一 Agent Loop 端点 — 后端执行 AI 调用 + 工具执行 + 错误恢复

        请求体: { prompt, context?, session_id?, use_tools? }
        响应: SSE 流, 事件类型:
          content / reasoning / tool_use / tool_use_delta / tool_result / tool_error / tool_recovery / round_start / done / error
        """
        body = await req.json()
        prompt = body.get("prompt", "").strip()
        context_raw = body.get("context", [])
        session_id = body.get("session_id")
        use_tools = body.get("use_tools", True)

        if not prompt:
            raise HTTPException(400, "缺少 prompt 参数")

        client = _get_ai_client()
        if not client:
            raise HTTPException(503, "AI 未启用或未配置 API Key")

        context = _validate_context(context_raw) if context_raw else []
        cm = _get_chat_manager() if session_id else None

        from .ai.agent_loop import AgentLoop

        loop = AgentLoop(
            client=client,
            chat_manager=cm,
            use_tools=use_tools,
        )

        async def generate():
            from .ai.client import AIClientError
            try:
                for event in loop.run(
                    prompt=prompt,
                    context=context,
                    session_id=session_id,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except AIClientError as e:
                yield f"data: {json.dumps({'type': 'error', 'code': getattr(e, 'code', 'unknown'), 'message': str(e)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                _server_log(f"Agent loop error: {e}", "ERROR")
                yield f"data: {json.dumps({'type': 'error', 'code': 'unknown', 'message': str(e)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── AI 路线规划 (非交互式) ──────────────────────────────────────

    @app.post("/api/ai/route")
    async def ai_route(req: Request):
        body = await req.json()
        input_file = body.get("input_file", "").strip()
        if not input_file:
            raise HTTPException(400, "缺少 input_file 参数")

        input_path = resolve_path(input_file)
        if not input_path.exists():
            raise HTTPException(404, f"文件不存在: {input_file}")

        from .router import RouteWizard

        params = {
            "start_address": body.get("start_address", ""),
            "start_point": body.get("start_point"),
            "num_routes": min(10, max(1, int(body.get("num_routes", 3)))),
            "travel_mode": body.get("travel_mode", "driving"),
        }

        wizard = RouteWizard(
            csv_path=str(input_path),
            map_path=str(OutputPaths.MAP / "路线规划_地图.html"),
            headless=True,
            params=params,
        )
        result = wizard.run()

        return {"success": result, "message": "路线规划完成" if result else "路线规划失败"}

    # ── AI 数据分析 (SSE 流式) ──────────────────────────────────────

    @app.post("/api/ai/analyze/stream")
    async def ai_analyze_stream(req: Request):
        body = await req.json()
        input_file = body.get("input_file", "").strip()
        if not input_file:
            raise HTTPException(400, "缺少 input_file 参数")

        input_path = resolve_path(input_file)
        if not input_path.exists():
            raise HTTPException(404, f"文件不存在: {input_file}")

        client = _get_ai_client()
        if not client:
            raise HTTPException(503, "AI 未启用或未配置 API Key")

        import pandas as pd
        try:
            if str(input_path).endswith((".xlsx", ".xls")):
                df = pd.read_excel(str(input_path))
            else:
                df = pd.read_csv(str(input_path), encoding="utf-8-sig")
        except Exception as e:
            raise HTTPException(400, f"读取文件失败: {e}") from None

        status_col = _find_column(df, ["状态", "status", "State"])
        if status_col and status_col in df.columns:
            df = df[df[status_col] == "成功"]

        if len(df) < 2:
            raise HTTPException(400, "有效地址不足（至少需要2个）")

        addr_col = _find_column(df, ["原始地址", "标准化地址", "original_address", "formatted_address"])
        lat_col = _find_column(df, ["纬度", "latitude", "lat"])
        lon_col = _find_column(df, ["经度", "longitude", "lng", "lon"])

        addresses_summary = []
        for _, row in df.head(50).iterrows():
            addr = str(row.get(addr_col, "")) if addr_col else ""
            lat = row.get(lat_col, "") if lat_col else ""
            lon = row.get(lon_col, "") if lon_col else ""
            addresses_summary.append(f"- {addr}: ({lat}, {lon})")

        prompt = (
            f"请分析以下 {len(addresses_summary)} 个地址的地理分布特征:\n\n"
            + "\n".join(addresses_summary)
            + "\n\n请从以下维度分析:\n"
            "1. 地理分布概况（城市/区域分布）\n"
            "2. 密度特征（集中/分散）\n"
            "3. 出行建议（如何分组访问效率最高）\n"
            "4. 异常点识别（位置明显偏离的点）\n"
        )

        messages = [
            {"role": "system", "content": "你是地理数据分析专家。请用中文回答。"},
            {"role": "user", "content": prompt},
        ]

        async def generate():
            try:
                for chunk in client.chat_stream(messages, temperature=0.7):
                    if isinstance(chunk, dict):
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    elif isinstance(chunk, str):
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                from .ai.client import AIClientError
                if isinstance(e, AIClientError):
                    yield f"data: {json.dumps({'error': str(e), 'code': getattr(e, 'code', 'unknown')})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': str(e), 'code': 'unknown'})}\n\n"
                yield "data: [DONE]\n\n"

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
        if not path:
            raise HTTPException(400, "缺少 path 参数")

        full_path = PROJECT_DIR / path
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
            return {
                "path": path,
                "columns": list(df.columns),
                "rows": len(df),
                "preview": df.head(100).fillna("").to_dict(orient="records"),
            }
        except Exception:
            content = full_path.read_text(encoding="utf-8", errors="replace")[:5000]
            return {"path": path, "content": content}

    # ── 在浏览器中打开文件 ─────────────────────────────────────────

    @app.post("/api/open")
    async def open_in_browser(req: Request):
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

    @app.post("/api/open/directory")
    async def open_directory(req: Request):
        import subprocess
        import sys

        body = await req.json()
        dir_type = body.get("type", "").strip()

        directories = {
            "output/map": OutputPaths.MAP,
            "output/csv": OutputPaths.CSV,
            "data": PROJECT_DIR / "data",
        }

        target = directories.get(dir_type)
        if not target:
            raise HTTPException(400, f"不支持的目录类型: {dir_type}，可选: {', '.join(directories.keys())}")

        target.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform == "win32":
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return {"opened": str(target.resolve()), "type": dir_type}
        except Exception as e:
            raise HTTPException(500, f"无法打开目录: {e}")

    # ── 挂载 Web GUI (如果已构建) ──────────────────────────────
    web_dist = (Path(__file__).parent.parent / "web_gui" / "dist").resolve()
    if web_dist.exists() and (web_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web_gui")

    _start_task_cleanup()
    return app


# ── 服务器启动 ────────────────────────────────────────────────────


def find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_api_server(host: str = "127.0.0.1", port: int = 8765):
    import socket

    import uvicorn
    app = create_api_app()

    if port == 0:
        port = find_free_port()
    else:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
        except OSError:
            port = find_free_port()

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

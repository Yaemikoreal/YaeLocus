"""Web GUI — FastAPI 应用"""
import io
import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..cache import CacheManager
from ..config import Config, PROJECT_DIR
from ..geocoder import Geocoder
from ..logger import APILogger
from ..map_visualizer import create_map

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"

# 任务存储: {task_id: {"status": "running"|"done"|"error", "results": [...], "progress": 0-100}}
_tasks: dict = {}
_tasks_lock = threading.Lock()

_OUTPUT_DIR = PROJECT_DIR / "output"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _create_app() -> FastAPI:
    app = FastAPI(title="YaeLocus Web", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _render_index()

    @app.get("/map", response_class=HTMLResponse)
    async def map_page():
        return _render_map_viewer()

    @app.get("/config", response_class=HTMLResponse)
    async def config_page():
        return _render_config()

    @app.post("/api/geocode/file")
    async def geocode_file(
        file: UploadFile = File(...),
        column: str = Form("地址"),
        workers: str = Form("1"),
        use_cache: bool = Form(True),
        province: str = Form(""),
        city: str = Form(""),
    ):
        """上传文件并开始地理编码"""
        if not Config.validate():
            return JSONResponse({"error": "请先配置 API 密钥"}, status_code=400)

        # 处理 workers 参数（支持 auto）
        if workers == "auto":
            # 根据已配置的 API 数量自动选择线程数
            apis = Config.get_available_apis()
            num_workers = min(len(apis) * 2 + 1, 5) if apis else 1
        else:
            num_workers = int(workers)

        task_id = uuid.uuid4().hex[:12]
        content = await file.read()

        ext = Path(file.filename).suffix.lower() if file.filename else ".csv"
        try:
            if ext in (".xlsx", ".xls"):
                engine = "openpyxl" if ext == ".xlsx" else "xlrd"
                df = pd.read_excel(io.BytesIO(content), engine=engine)
            else:
                df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        except Exception as e:
            return JSONResponse({"error": f"文件解析失败: {str(e)}"}, status_code=400)

        if column not in df.columns:
            return JSONResponse(
                {"error": f"列 '{column}' 不存在，可用列: {list(df.columns)}"}, status_code=400
            )

        addresses = df[column].dropna().astype(str).tolist()
        if len(addresses) == 0:
            return JSONResponse({"error": "未找到有效地址"}, status_code=400)

        # 如果指定了省市，添加前缀
        location_prefix = ""
        if province and city:
            location_prefix = f"{province}{city}"
        elif province:
            location_prefix = province

        with _tasks_lock:
            _tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total": len(addresses),
                "results": [],
                "error": None,
                "filename": file.filename or "uploaded",
                "location_prefix": location_prefix,
            }

        thread = threading.Thread(
            target=_run_geocode,
            args=(task_id, addresses, column, num_workers, bool(use_cache), location_prefix),
            daemon=True
        )
        thread.start()

        return JSONResponse({"task_id": task_id, "total": len(addresses), "workers": num_workers})

    @app.post("/api/geocode/single")
    async def geocode_single(address: str = Form(...)):
        """单个地址地理编码"""
        if not Config.validate():
            return JSONResponse({"error": "请先配置 API 密钥"}, status_code=400)

        cache = CacheManager(str(_OUTPUT_DIR / "geocache.db"))
        logger = APILogger(str(_OUTPUT_DIR / "api调用日志.csv"))
        geocoder = Geocoder(cache, logger)
        try:
            result = geocoder.geocode(address)
            return JSONResponse(result)
        finally:
            geocoder.close()

    @app.get("/api/geocode/status/{task_id}")
    async def geocode_status(task_id: str):
        """查询地理编码任务进度"""
        with _tasks_lock:
            task = _tasks.get(task_id)
        if task is None:
            return JSONResponse({"error": "任务不存在"}, status_code=404)
        return JSONResponse({
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "total": task["total"],
            "error": task["error"],
        })

    @app.get("/api/geocode/result/{task_id}")
    async def geocode_result(task_id: str):
        """获取地理编码完成后的结果"""
        with _tasks_lock:
            task = _tasks.get(task_id)
        if task is None:
            return JSONResponse({"error": "任务不存在"}, status_code=404)
        if task["status"] == "running":
            return JSONResponse({"error": "任务尚未完成"}, status_code=400)
        # 返回全部结果
        results = task["results"]
        success_results = [r for r in results if r.get("success")]
        return JSONResponse({
            "task_id": task_id,
            "status": task["status"],
            "total": task["total"],
            "success": len(success_results),
            "failed": len(results) - len(success_results),
            "results": success_results,
        })

    @app.get("/api/map/{task_id}")
    async def task_map(task_id: str):
        """为指定任务生成地图 HTML"""
        with _tasks_lock:
            task = _tasks.get(task_id)
        if task is None:
            return JSONResponse({"error": "任务不存在"}, status_code=404)

        valid = [r for r in task["results"] if r.get("success")]
        if not valid:
            return JSONResponse({"error": "没有成功的地理编码结果"}, status_code=400)

        try:
            task_filename = task.get("filename", "")
            stem = Path(task_filename).stem if task_filename else task_id
            map_path = str(_OUTPUT_DIR / f"{stem}_map.html")
            create_map(data=valid, output_file=map_path, title="地址分布地图")
            with open(map_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        except Exception as e:
            return JSONResponse({"error": f"地图生成失败: {str(e)}"}, status_code=500)

    @app.get("/api/map/view/{filename}")
    async def view_map_file(filename: str):
        """在新标签页打开地图 HTML 文件"""
        from ..config import OutputPaths
        map_dir = OutputPaths.MAP
        safe_name = Path(filename).name
        file_path = map_dir / safe_name
        if not file_path.exists():
            return JSONResponse({"error": "文件不存在"}, status_code=404)
        if file_path.suffix.lower() != ".html":
            return JSONResponse({"error": "仅支持 HTML 文件"}, status_code=400)
        return FileResponse(str(file_path), media_type="text/html")

    @app.post("/api/config/test")
    async def test_api_key(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
    ):
        """测试 API Key 有效性"""
        import requests as req
        results = {}

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

        return JSONResponse(results)

    @app.post("/api/config/save")
    async def save_config(
        amap_key: str = Form(""),
        baidu_ak: str = Form(""),
        tianditu_tk: str = Form(""),
        ai_enabled: str = Form("false"),
        ai_provider: str = Form("deepseek"),
        deepseek_key: str = Form(""),
    ):
        """保存配置到 .env 文件"""
        env_path = PROJECT_DIR / ".env"

        # 读取现有 .env（如果存在）
        existing = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

        # 更新
        updates = {
            "AMAP_KEY": amap_key,
            "BAIDU_AK": baidu_ak,
            "TIANDITU_TK": tianditu_tk,
            "AI_ENABLED": ai_enabled,
            "AI_PROVIDER": ai_provider,
            "DEEPSEEK_API_KEY": deepseek_key,
        }
        for k, v in updates.items():
            if v:
                existing[k] = v
            elif k in existing:
                del existing[k]

        # 写回
        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return JSONResponse({"success": True, "message": "配置已保存，请重启 Web 服务以生效"})

    @app.get("/api/quota")
    async def quota():
        """获取 API 配额使用情况"""
        log_path = _OUTPUT_DIR / "api调用日志.csv"
        if not log_path.exists():
            return JSONResponse({"api_usage": {}, "cache_stats": {}})

        logger = APILogger(str(log_path))
        api_stats = logger.get_stats()

        cache = CacheManager(str(_OUTPUT_DIR / "geocache.db"))
        cache_stats = cache.get_stats()
        cache.close()

        return JSONResponse({
            "api_usage": api_stats.get("api_usage", {}),
            "total_calls": api_stats.get("total", 0),
            "cache_hits": cache_stats["hits"],
            "cache_total": cache_stats["total_entries"],
        })

    @app.get("/api/maps")
    async def list_maps():
        """列出 output/map 目录下的地图文件"""
        from ..config import OutputPaths
        map_dir = OutputPaths.MAP
        if not map_dir.exists():
            return JSONResponse([])
        files = []
        for f in sorted(map_dir.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True):
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "mtime": f.stat().st_mtime,
            })
        return JSONResponse(files)

    return app


def _run_geocode(task_id: str, addresses: list, column: str, workers: int, use_cache: bool, location_prefix: str = ""):
    """后台执行地理编码任务"""
    try:
        cache = CacheManager(str(_OUTPUT_DIR / "geocache.db"))
        cache.start_watchdog(interval=30.0)
        logger = APILogger(str(_OUTPUT_DIR / "api调用日志.csv"))
        geocoder = Geocoder(cache, logger)

        results = []
        processed = 0
        total = len(addresses)

        # 如果有 location_prefix，添加到地址前
        def process_address(addr: str) -> str:
            if location_prefix and not addr.startswith(location_prefix):
                return f"{location_prefix}{addr}"
            return addr

        if workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            max_workers = min(workers, 10)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(geocoder.geocode, process_address(addr)): addr for addr in addresses}
                for future in as_completed(futures):
                    addr = futures[future]
                    result = future.result()
                    # 保留原始地址
                    if result and "original_address" not in result:
                        result["original_address"] = addr
                    results.append(result)
                    processed += 1
                    with _tasks_lock:
                        _tasks[task_id]["progress"] = processed
                        _tasks[task_id]["results"] = results
        else:
            for addr in addresses:
                result = geocoder.geocode(process_address(addr))
                if result and "original_address" not in result:
                    result["original_address"] = addr
                results.append(result)
                processed += 1
                with _tasks_lock:
                    _tasks[task_id]["progress"] = processed
                    _tasks[task_id]["results"] = results

        geocoder.close()

        with _tasks_lock:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["results"] = results
            _tasks[task_id]["progress"] = total
    except Exception as e:
        with _tasks_lock:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = _create_app()
    return app


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """启动 Web 服务器"""
    import webbrowser
    app = _create_app()

    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


# --- HTML 模板 (内联) ---

def _base_html(title: str, content: str, active: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — YaeLocus v{__version__}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f5f7fa; color:#333; min-height:100vh; }}
nav {{ background:#1a73e8; color:#fff; padding:0 24px; display:flex; align-items:center; height:56px; gap:0; }}
nav a {{ color:rgba(255,255,255,0.85); text-decoration:none; padding:16px 20px; font-size:14px; transition:all 0.2s; border-bottom:2px solid transparent; }}
nav a:hover, nav a.active {{ color:#fff; background:rgba(255,255,255,0.1); border-bottom-color:#fff; }}
nav .brand {{ font-size:18px; font-weight:700; color:#fff; margin-right:auto; }}
.container {{ max-width:900px; margin:32px auto; padding:0 24px; }}
.card {{ background:#fff; border-radius:12px; padding:28px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
.card h2 {{ font-size:20px; margin-bottom:16px; color:#1a73e8; }}
.btn {{ display:inline-flex; align-items:center; justify-content:center; padding:10px 24px; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; transition:all 0.2s; gap:8px; }}
.btn-primary {{ background:#1a73e8; color:#fff; }}
.btn-primary:hover {{ background:#1557b0; }}
.btn-primary:disabled {{ background:#ccc; cursor:not-allowed; }}
.btn-secondary {{ background:#e8eaed; color:#333; }}
.btn-secondary:hover {{ background:#d2d5d9; }}
input, select {{ width:100%; padding:10px 14px; border:1.5px solid #ddd; border-radius:8px; font-size:14px; transition:border-color 0.2s; }}
input:focus, select:focus {{ outline:none; border-color:#1a73e8; }}
label {{ display:block; font-size:13px; font-weight:600; margin-bottom:6px; color:#555; }}
.form-group {{ margin-bottom:16px; }}
.form-row {{ display:flex; gap:16px; }}
.form-row .form-group {{ flex:1; }}
.upload-zone {{ border:2px dashed #ccc; border-radius:12px; padding:48px; text-align:center; cursor:pointer; transition:all 0.2s; }}
.upload-zone:hover, .upload-zone.dragover {{ border-color:#1a73e8; background:#f0f5ff; }}
.upload-zone p {{ color:#888; margin-top:8px; font-size:14px; }}
.progress-bar {{ height:8px; background:#e8eaed; border-radius:4px; overflow:hidden; margin:12px 0; }}
.progress-fill {{ height:100%; background:#1a73e8; border-radius:4px; transition:width 0.3s; width:0%; }}
.result-item {{ padding:10px 14px; border-bottom:1px solid #f0f0f0; font-size:14px; }}
.result-item:last-child {{ border-bottom:none; }}
.result-success {{ color:#1e8e3e; }}
.result-fail {{ color:#d93025; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }}
.tag-success {{ background:#e6f4ea; color:#1e8e3e; }}
.tag-fail {{ background:#fce8e6; color:#d93025; }}
.tag-info {{ background:#e8f0fe; color:#1a73e8; }}
#map-container {{ width:100%; height:500px; border-radius:12px; overflow:hidden; }}
footer {{ text-align:center; padding:32px; color:#999; font-size:13px; }}
@media (max-width:600px) {{ .container {{ padding:0 12px; }} .form-row {{ flex-direction:column; }} .card {{ padding:20px; }} }}
</style>
</head>
<body>
<nav>
<span class="brand">YaeLocus</span>
<a href="/" class="{'active' if active=='index' else ''}">地理编码</a>
<a href="/map" class="{'active' if active=='map' else ''}">地图浏览</a>
<a href="/config" class="{'active' if active=='config' else ''}">配置</a>
</nav>
<div class="container">{content}</div>
<footer>YaeLocus v{__version__} · Web GUI</footer>
</body>
</html>"""


def _render_index() -> str:
    content = """
<div class="card">
  <h2>批量地理编码</h2>
  <p style="color:#888;margin-bottom:16px">上传包含地址列的 CSV/XLSX 文件，自动转换为经纬度坐标</p>

  <div class="upload-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <div style="font-size:48px;margin-bottom:8px">&#128194;</div>
    <strong>点击选择文件 或 拖拽到此处</strong>
    <p>支持 CSV / XLSX / XLS 格式</p>
  </div>
  <input type="file" id="fileInput" accept=".csv,.xlsx,.xls" style="display:none">

  <div id="fileInfo" style="margin-top:12px;display:none">
    <span class="tag tag-info" id="fileName"></span>
  </div>

  <div class="form-row" style="margin-top:16px">
    <div class="form-group">
      <label>地址列名</label>
      <input type="text" id="colName" value="地址" placeholder="CSV/XLSX 中的列名">
    </div>
    <div class="form-group">
      <label>并行线程数</label>
      <select id="workers"><option value="auto">auto（自动）</option><option value="1">1 (串行)</option><option value="2">2</option><option value="3">3</option><option value="5">5</option></select>
    </div>
  </div>

  <div class="form-row">
    <div class="form-group">
      <label>省/直辖市（可选）</label>
      <select id="province" onchange="updateCities()">
        <option value="">-- 不指定 --</option>
        <option value="北京市">北京市</option>
        <option value="天津市">天津市</option>
        <option value="河北省">河北省</option>
        <option value="山西省">山西省</option>
        <option value="内蒙古自治区">内蒙古自治区</option>
        <option value="辽宁省">辽宁省</option>
        <option value="吉林省">吉林省</option>
        <option value="黑龙江省">黑龙江省</option>
        <option value="上海市">上海市</option>
        <option value="江苏省">江苏省</option>
        <option value="浙江省">浙江省</option>
        <option value="安徽省">安徽省</option>
        <option value="福建省">福建省</option>
        <option value="江西省">江西省</option>
        <option value="山东省">山东省</option>
        <option value="河南省">河南省</option>
        <option value="湖北省">湖北省</option>
        <option value="湖南省">湖南省</option>
        <option value="广东省">广东省</option>
        <option value="广西壮族自治区">广西壮族自治区</option>
        <option value="海南省">海南省</option>
        <option value="重庆市">重庆市</option>
        <option value="四川省">四川省</option>
        <option value="贵州省">贵州省</option>
        <option value="云南省">云南省</option>
        <option value="西藏自治区">西藏自治区</option>
        <option value="陕西省">陕西省</option>
        <option value="甘肃省">甘肃省</option>
        <option value="青海省">青海省</option>
        <option value="宁夏回族自治区">宁夏回族自治区</option>
        <option value="新疆维吾尔自治区">新疆维吾尔自治区</option>
        <option value="台湾省">台湾省</option>
        <option value="香港特别行政区">香港特别行政区</option>
        <option value="澳门特别行政区">澳门特别行政区</option>
      </select>
    </div>
    <div class="form-group">
      <label>地/市（可选）</label>
      <select id="city"><option value="">-- 不指定 --</option></select>
    </div>
  </div>

  <button class="btn btn-primary" id="startBtn" disabled onclick="startGeocode()">开始地理编码</button>

  <div id="progressArea" style="display:none;margin-top:20px">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px">
      <span id="progressText">处理中...</span>
      <span id="progressPercent">0%</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div id="progressETA" style="font-size:12px;color:#888;margin-top:4px"></div>
  </div>

  <div id="resultArea" style="margin-top:16px"></div>
</div>

<div class="card">
  <h2>已完成任务</h2>
  <p style="color:#888;margin-bottom:12px">历史地理编码任务，常驻显示（最多保存 20 个）</p>
  <div id="taskList" style="max-height:500px;overflow-y:auto"></div>
</div>

<div class="card" id="taskDetailCard" style="display:none">
  <h2>任务明细</h2>
  <button class="btn btn-secondary" style="margin-bottom:12px" onclick="closeTaskDetail()">关闭</button>
  <div id="taskDetailContent" style="max-height:500px;overflow-y:auto"></div>
</div>

<script>
let taskId = null;
let pollTimer = null;
let startTime = null;

// 页面加载时恢复任务列表，自动轮询运行中的任务
function loadRecentTasks() {
  const tasks = JSON.parse(localStorage.getItem('geocodeTasks') || '[]');
  renderTaskList(tasks);
  // 自动轮询运行中的任务
  tasks.forEach(function(t) {
    if (t.status === 'running') {
      pollRunningTask(t.id);
    }
  });
}

function saveTask(tid, total, filename, status) {
  status = status || 'running';
  const tasks = JSON.parse(localStorage.getItem('geocodeTasks') || '[]');
  // 如果已存在则更新
  const existing = tasks.findIndex(function(t) { return t.id === tid; });
  const entry = {id: tid, total: total, filename: filename || '', status: status, success: 0, failed: 0, progress: 0, time: Date.now()};
  if (existing >= 0) {
    tasks[existing] = entry;
  } else {
    tasks.unshift(entry);
  }
  localStorage.setItem('geocodeTasks', JSON.stringify(tasks.slice(0, 20)));
  renderTaskList(tasks.slice(0, 20));
}

function updateTaskStatus(tid, status, success, failed) {
  const tasks = JSON.parse(localStorage.getItem('geocodeTasks') || '[]');
  const idx = tasks.findIndex(function(t) { return t.id === tid; });
  if (idx >= 0) {
    tasks[idx].status = status;
    tasks[idx].success = success || 0;
    tasks[idx].failed = failed || 0;
    tasks[idx].time = Date.now();
    localStorage.setItem('geocodeTasks', JSON.stringify(tasks.slice(0, 20)));
    renderTaskList(tasks.slice(0, 20));
  }
}

function pollRunningTask(tid) {
  fetch('/api/geocode/status/' + tid)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) return;
      if (data.status === 'done') {
        fetch('/api/geocode/result/' + tid)
          .then(function(r) { return r.json(); })
          .then(function(d) {
            updateTaskStatus(tid, 'done', d.success, d.failed);
          });
      } else if (data.status === 'error') {
        updateTaskStatus(tid, 'error', 0, data.total || 0);
      } else {
        // 更新进度
        const tasks = JSON.parse(localStorage.getItem('geocodeTasks') || '[]');
        const idx = tasks.findIndex(function(t) { return t.id === tid; });
        if (idx >= 0) {
          tasks[idx].progress = data.progress || 0;
          localStorage.setItem('geocodeTasks', JSON.stringify(tasks));
        }
        renderTaskList(JSON.parse(localStorage.getItem('geocodeTasks') || '[]'));
        setTimeout(function() { pollRunningTask(tid); }, 3000);
      }
    });
}

function renderTaskList(tasks) {
  let html = '';
  if (tasks.length === 0) {
    html = '<div style="padding:32px;text-align:center;color:#999;font-size:14px">暂无已完成任务<br><span style="font-size:12px">上传文件并点击"开始地理编码"后将在此显示</span></div>';
  } else {
    html += '<table style="width:100%;border-collapse:collapse;font-size:13px">';
    html += '<thead><tr style="background:#f5f7fa;border-bottom:2px solid #e0e0e0">';
    html += '<th style="padding:8px 10px;text-align:left;font-size:12px">任务ID</th>';
    html += '<th style="padding:8px 10px;text-align:left;font-size:12px">文件</th>';
    html += '<th style="padding:8px 10px;text-align:center;font-size:12px">总数</th>';
    html += '<th style="padding:8px 10px;text-align:center;font-size:12px">成功</th>';
    html += '<th style="padding:8px 10px;text-align:center;font-size:12px">失败</th>';
    html += '<th style="padding:8px 10px;text-align:center;font-size:12px">状态</th>';
    html += '<th style="padding:8px 10px;text-align:left;font-size:12px">时间</th>';
    html += '<th style="padding:8px 10px;text-align:center;font-size:12px">操作</th>';
    html += '</tr></thead><tbody>';
    tasks.forEach(function(t) {
      const timeStr = new Date(t.time).toLocaleString();
      let statusClass, statusText;
      if (t.status === 'done') { statusClass = 'tag-success'; statusText = '已完成'; }
      else if (t.status === 'error') { statusClass = 'tag-fail'; statusText = '失败'; }
      else { statusClass = 'tag-info'; statusText = '处理中 (' + (t.progress || 0) + '/' + (t.total || '?') + ')'; }
      html += '<tr style="border-bottom:1px solid #f0f0f0">';
      html += '<td style="padding:8px 10px;font-family:monospace;font-size:11px">' + t.id + '</td>';
      html += '<td style="padding:8px 10px;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (t.filename || '') + '">' + (t.filename || '-') + '</td>';
      html += '<td style="padding:8px 10px;text-align:center">' + (t.total || '-') + '</td>';
      html += '<td style="padding:8px 10px;text-align:center;color:#1e8e3e;font-weight:600">' + (t.status === 'done' ? t.success : '-') + '</td>';
      html += '<td style="padding:8px 10px;text-align:center;color:#d93025;font-weight:600">' + (t.status === 'done' ? t.failed : '-') + '</td>';
      html += '<td style="padding:8px 10px;text-align:center"><span class="tag ' + statusClass + '">' + statusText + '</span></td>';
      html += '<td style="padding:8px 10px;color:#888;font-size:11px">' + timeStr + '</td>';
      html += '<td style="padding:8px 10px;text-align:center">';
      if (t.status === 'done') {
        html += '<button class="btn btn-primary" style="padding:4px 12px;font-size:12px" onclick="viewTaskDetail(\'' + t.id + '\')">查看明细</button>';
      } else if (t.status === 'running') {
        html += '<button class="btn btn-secondary" style="padding:4px 12px;font-size:12px" onclick="pollRunningTask(\'' + t.id + '\')">刷新</button>';
      } else {
        html += '<span style="color:#d93025;font-size:11px">任务失败</span>';
      }
      html += '</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
  }
  document.getElementById('taskList').innerHTML = html;
}

function viewTaskDetail(tid) {
  fetch('/api/geocode/result/' + tid)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.error) {
        document.getElementById('taskDetailContent').innerHTML = '<p style="color:#d93025;padding:20px">' + d.error + '</p>';
      } else {
        let html = '<div style="margin-bottom:12px;padding:12px;background:#f5f7fa;border-radius:8px">';
        html += '<strong>' + tid + '</strong> | 成功 <span style="color:#1e8e3e;font-weight:600">' + d.success + '</span> 条';
        html += ' | 失败 <span style="color:#d93025;font-weight:600">' + d.failed + '</span> 条';
        html += ' | 共 ' + (d.total || '?') + ' 条</div>';
        html += '<div style="max-height:400px;overflow-y:auto;border:1px solid #eee;border-radius:8px">';
        if (d.results && d.results.length > 0) {
          d.results.forEach(function(r) {
            html += '<div class="result-item">';
            html += '<div style="font-weight:600">' + (r.original_address || '?') + '</div>';
            html += '<div style="color:#1e8e3e;font-size:13px">' + (r.latitude||'?') + ', ' + (r.longitude||'?') + ' <span class="tag tag-info">' + (r.source || '') + '</span></div>';
            if (r.formatted_address) html += '<div style="color:#888;font-size:12px">标准化: ' + r.formatted_address + '</div>';
            html += '</div>';
          });
        } else {
          html += '<p style="padding:20px;text-align:center;color:#888">无成功结果</p>';
        }
        html += '</div>';
        document.getElementById('taskDetailContent').innerHTML = html;
      }
      document.getElementById('taskDetailCard').style.display = 'block';
    })
    .catch(function(e) {
      document.getElementById('taskDetailContent').innerHTML = '<p style="color:#d93025;padding:20px">加载失败: ' + e.message + '</p>';
      document.getElementById('taskDetailCard').style.display = 'block';
    });
}

function closeTaskDetail() {
  document.getElementById('taskDetailCard').style.display = 'none';
}

// 城市数据（部分主要城市）
const cityData = {
  '北京市': ['东城区', '西城区', '朝阳区', '海淀区', '丰台区', '石景山区', '门头沟区', '房山区', '通州区', '顺义区', '昌平区', '大兴区', '怀柔区', '平谷区', '密云区', '延庆区'],
  '上海市': ['黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '闵行区', '宝山区', '嘉定区', '浦东新区', '金山区', '松江区', '青浦区', '奉贤区', '崇明区'],
  '天津市': ['和平区', '河东区', '河西区', '南开区', '河北区', '红桥区', '东丽区', '西青区', '津南区', '北辰区', '武清区', '宝坻区', '滨海新区', '宁河区', '静海区', '蓟州区'],
  '重庆市': ['渝中区', '大渡口区', '江北区', '沙坪坝区', '九龙坡区', '南岸区', '北碚区', '渝北区', '巴南区', '万州区', '涪陵区', '永川区', '合川区', '江津区', '长寿区', '璧山区'],
  '广东省': ['广州市', '深圳市', '珠海市', '汕头市', '佛山市', '韶关市', '湛江市', '肇庆市', '江门市', '茂名市', '惠州市', '梅州市', '汕尾市', '河源市', '阳江市', '清远市', '东莞市', '中山市', '潮州市', '揭阳市', '云浮市'],
  '江苏省': ['南京市', '苏州市', '无锡市', '常州市', '镇江市', '南通市', '泰州市', '扬州市', '盐城市', '连云港市', '徐州市', '淮安市', '宿迁市'],
  '浙江省': ['杭州市', '宁波市', '温州市', '嘉兴市', '湖州市', '绍兴市', '金华市', '衢州市', '舟山市', '台州市', '丽水市'],
  '山东省': ['济南市', '青岛市', '淄博市', '枣庄市', '东营市', '烟台市', '潍坊市', '济宁市', '泰安市', '威海市', '日照市', '临沂市', '德州市', '聊城市', '滨州市', '菏泽市'],
  '河南省': ['郑州市', '开封市', '洛阳市', '平顶山市', '安阳市', '鹤壁市', '新乡市', '焦作市', '濮阳市', '许昌市', '漯河市', '三门峡市', '南阳市', '商丘市', '信阳市', '周口市', '驻马店市'],
  '湖北省': ['武汉市', '黄石市', '十堰市', '宜昌市', '襄阳市', '鄂州市', '荆门市', '孝感市', '荆州市', '黄冈市', '咸宁市', '随州市', '恩施州'],
  '湖南省': ['长沙市', '株洲市', '湘潭市', '衡阳市', '邵阳市', '岳阳市', '常德市', '张家界市', '益阳市', '郴州市', '永州市', '怀化市', '娄底市', '湘西州'],
  '四川省': ['成都市', '自贡市', '攀枝花市', '泸州市', '德阳市', '绵阳市', '广元市', '遂宁市', '内江市', '乐山市', '南充市', '眉山市', '宜宾市', '广安市', '达州市', '雅安市', '巴中市', '资阳市', '阿坝州', '甘孜州', '凉山州'],
  '河北省': ['石家庄市', '唐山市', '秦皇岛市', '邯郸市', '邢台市', '保定市', '张家口市', '承德市', '沧州市', '廊坊市', '衡水市'],
  '福建省': ['福州市', '厦门市', '漳州市', '泉州市', '三明市', '莆田市', '南平市', '龙岩市', '宁德市'],
  '辽宁省': ['沈阳市', '大连市', '鞍山市', '抚顺市', '本溪市', '丹东市', '锦州市', '营口市', '阜新市', '辽阳市', '盘锦市', '铁岭市', '朝阳市', '葫芦岛市'],
  '吉林省': ['长春市', '吉林市', '四平市', '辽源市', '通化市', '白山市', '松原市', '白城市', '延边州'],
  '黑龙江省': ['哈尔滨市', '齐齐哈尔市', '鸡西市', '鹤岗市', '双鸭山市', '大庆市', '伊春市', '佳木斯市', '七台河市', '牡丹江市', '黑河市', '绥化市', '大兴安岭地区'],
  '安徽省': ['合肥市', '芜湖市', '蚌埠市', '淮南市', '马鞍山市', '淮北市', '铜陵市', '安庆市', '黄山市', '滁州市', '阜阳市', '宿州市', '六安市', '亳州市', '池州市', '宣城市'],
  '江西省': ['南昌市', '景德镇市', '萍乡市', '九江市', '新余市', '鹰潭市', '赣州市', '吉安市', '宜春市', '抚州市', '上饶市'],
  '陕西省': ['西安市', '铜川市', '宝鸡市', '咸阳市', '渭南市', '延安市', '汉中市', '榆林市', '安康市', '商洛市'],
  '甘肃省': ['兰州市', '嘉峪关市', '金昌市', '白银市', '天水市', '武威市', '张掖市', '平凉市', '酒泉市', '庆阳市', '定西市', '陇南市', '甘南州', '临夏州'],
  '云南省': ['昆明市', '曲靖市', '玉溪市', '保山市', '昭通市', '丽江市', '普洱市', '临沧市', '楚雄州', '红河州', '文山州', '西双版纳州', '大理州', '德宏州', '怒江州', '迪庆州'],
  '贵州省': ['贵阳市', '六盘水市', '遵义市', '安顺市', '毕节市', '铜仁市', '黔西南州', '黔东南州', '黔南州'],
  '广西壮族自治区': ['南宁市', '柳州市', '桂林市', '梧州市', '北海市', '防城港市', '钦州市', '贵港市', '玉林市', '百色市', '贺州市', '河池市', '来宾市', '崇左市'],
  '海南省': ['海口市', '三亚市', '三沙市', '儋州市', '琼海市', '文昌市', '万宁市', '东方市'],
  '内蒙古自治区': ['呼和浩特市', '包头市', '乌海市', '赤峰市', '通辽市', '鄂尔多斯市', '呼伦贝尔市', '巴彦淖尔市', '乌兰察布市', '兴安盟', '锡林郭勒盟', '阿拉善盟'],
  '新疆维吾尔自治区': ['乌鲁木齐市', '克拉玛依市', '吐鲁番市', '哈密市', '昌吉州', '博尔塔拉州', '巴音郭楞州', '阿克苏地区', '克孜勒苏州', '喀什地区', '和田地区', '伊犁州', '塔城地区', '阿勒泰地区'],
  '西藏自治区': ['拉萨市', '日喀则市', '昌都市', '林芝市', '山南市', '那曲市', '阿里地区'],
  '宁夏回族自治区': ['银川市', '石嘴山市', '吴忠市', '固原市', '中卫市'],
  '青海省': ['西宁市', '海东市', '海北州', '黄南州', '海南州', '果洛州', '玉树州', '海西州'],
};

function updateCities() {
  const prov = document.getElementById('province').value;
  const citySel = document.getElementById('city');
  citySel.innerHTML = '<option value="">-- 不指定 --</option>';
  if (prov && cityData[prov]) {
    cityData[prov].forEach(function(c) {
      citySel.innerHTML += '<option value="' + c + '">' + c + '</option>';
    });
  }
}

function formatTime(seconds) {
  if (seconds < 0 || !isFinite(seconds)) return '计算中...';
  if (seconds < 60) return Math.round(seconds) + '秒';
  return Math.round(seconds / 60) + '分钟';
}

document.getElementById('fileInput').addEventListener('change', function(e) {
  const f = e.target.files[0];
  if (f) {
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('fileName').textContent = f.name + ' (' + (f.size/1024).toFixed(1) + ' KB)';
    document.getElementById('startBtn').disabled = false;
  }
});

const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) {
    document.getElementById('fileInput').files = e.dataTransfer.files;
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('fileName').textContent = f.name + ' (' + (f.size/1024).toFixed(1) + ' KB)';
    document.getElementById('startBtn').disabled = false;
  }
});

function startGeocode() {
  const file = document.getElementById('fileInput').files[0];
  if (!file) return;

  const form = new FormData();
  form.append('file', file);
  form.append('column', document.getElementById('colName').value);
  form.append('workers', document.getElementById('workers').value);
  form.append('province', document.getElementById('province').value);
  form.append('city', document.getElementById('city').value);

  startTime = Date.now();
  document.getElementById('startBtn').disabled = true;
  document.getElementById('startBtn').textContent = '处理中...';
  document.getElementById('progressArea').style.display = 'block';
  document.getElementById('resultArea').innerHTML = '';

  fetch('/api/geocode/file', {method:'POST', body:form})
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        document.getElementById('resultArea').innerHTML = '<p style="color:#d93025">' + data.error + '</p>';
        document.getElementById('startBtn').disabled = false;
        document.getElementById('startBtn').textContent = '开始地理编码';
        return;
      }
      taskId = data.task_id;
      // 立即保存任务到 localStorage（任务创建时即持久化）
      saveTask(taskId, data.total, file.name, 'running');
      pollTask();
    });
}

function pollTask() {
  if (!taskId) return;
  fetch('/api/geocode/status/' + taskId)
    .then(r => r.json())
    .then(data => {
      const processed = data.progress || 0;
      const total = data.total || 0;
      const pct = total > 0 ? Math.round(processed / total * 100) : 0;
      document.getElementById('progressFill').style.width = pct + '%';
      document.getElementById('progressPercent').textContent = pct + '%';
      document.getElementById('progressText').textContent = '已处理 ' + processed + '/' + total;

      // 计算预计用时
      if (startTime && processed > 0 && total > 0) {
        const elapsed = (Date.now() - startTime) / 1000;
        const speed = processed / elapsed;
        const remaining = (total - processed) / speed;
        document.getElementById('progressETA').textContent = '预计剩余: ' + formatTime(remaining) + ' (速度: ' + speed.toFixed(1) + ' 条/秒)';
      }

      if (data.status === 'done') {
        document.getElementById('startBtn').disabled = false;
        document.getElementById('startBtn').textContent = '开始地理编码';
        clearInterval(pollTimer);
        pollTimer = null;
        fetch('/api/geocode/result/' + taskId)
          .then(function(r) { return r.json(); })
          .then(function(d) {
            // 更新已完成任务状态
            updateTaskStatus(taskId, 'done', d.success, d.failed);
            if (d.results) {
              let html = '<h3 style="margin-bottom:12px">结果 (' + d.success + ' 成功, ' + d.failed + ' 失败)</h3>';
              html += '<div style="max-height:400px;overflow-y:auto;border:1px solid #eee;border-radius:8px">';
              d.results.forEach(function(r) {
                html += '<div class="result-item">';
                html += '<div style="font-weight:600">' + (r.original_address || '?') + '</div>';
                html += '<div style="color:#1e8e3e;font-size:13px">' + (r.latitude||'?') + ', ' + (r.longitude||'?') + ' <span class="tag tag-info">' + (r.source || '') + '</span></div>';
                if (r.formatted_address) html += '<div style="color:#888;font-size:12px">标准化: ' + r.formatted_address + '</div>';
                html += '</div>';
              });
              html += '</div>';
              document.getElementById('resultArea').innerHTML = html;
            }
          });
      } else if (data.status === 'error') {
        document.getElementById('resultArea').innerHTML = '<p style="color:#d93025">错误: ' + (data.error || '未知') + '</p>';
        updateTaskStatus(taskId, 'error', 0, data.total || 0);
        clearInterval(pollTimer);
        pollTimer = null;
        document.getElementById('startBtn').disabled = false;
        document.getElementById('startBtn').textContent = '开始地理编码';
      }
    });
  if (!pollTimer) pollTimer = setInterval(pollTask, 2000);
}

// 页面加载时恢复任务列表
loadRecentTasks();
</script>"""
    return _base_html("地理编码", content, active="index")


def _render_map_viewer() -> str:
    content = """
<div class="card">
  <h2>地图浏览</h2>
  <p style="color:#888;margin-bottom:16px">浏览 output/map 目录中的地图 HTML 文件，点击阅览按钮在新标签页打开</p>

  <div style="margin-bottom:12px">
    <button class="btn btn-primary" onclick="loadDefaultMaps()">刷新地图列表</button>
  </div>

  <div id="mapInfo" style="font-size:13px;color:#888;margin-bottom:8px">加载中...</div>
</div>

<div class="card" id="mapListCard">
  <h3 style="font-size:16px;margin-bottom:12px;color:#555">地图文件列表</h3>
  <div id="mapFileList" style="border:1px solid #eee;border-radius:8px;max-height:500px;overflow-y:auto"></div>
</div>

<script>
function jsEsc(str) {
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').replace(/\r/g, '\\r');
}
function htmlEsc(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function loadDefaultMaps() {
  document.getElementById('mapInfo').textContent = '加载中...';
  fetch('/api/maps')
    .then(function(r) { return r.json(); })
    .then(function(files) {
      const listEl = document.getElementById('mapFileList');
      const infoEl = document.getElementById('mapInfo');

      if (!files || files.length === 0) {
        listEl.innerHTML = '<div style="padding:32px;text-align:center;color:#999">output/map 目录暂无地图文件</div>';
        infoEl.textContent = 'output/map 目录为空';
        return;
      }

      infoEl.textContent = '共 ' + files.length + ' 个地图文件（按修改时间排序）';
      var html = '<table style="width:100%;border-collapse:collapse;font-size:13px">';
      html += '<thead><tr style="background:#f5f7fa;border-bottom:2px solid #e0e0e0">';
      html += '<th style="padding:8px 10px;text-align:left;font-size:12px">文件名</th>';
      html += '<th style="padding:8px 10px;text-align:center;font-size:12px">大小</th>';
      html += '<th style="padding:8px 10px;text-align:left;font-size:12px">修改时间</th>';
      html += '<th style="padding:8px 10px;text-align:center;font-size:12px">操作</th>';
      html += '</tr></thead><tbody>';
      files.forEach(function(f) {
        var sizeKB = (f.size / 1024).toFixed(1);
        var mtimeStr = new Date(f.mtime * 1000).toLocaleString();
        var escName = jsEsc(f.name);
        var escNameHtml = htmlEsc(f.name);
        html += '<tr style="border-bottom:1px solid #f0f0f0">';
        html += '<td style="padding:8px 10px;font-family:monospace;font-size:12px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + escNameHtml + '">' + escNameHtml + '</td>';
        html += '<td style="padding:8px 10px;text-align:center;color:#888;font-size:12px">' + sizeKB + ' KB</td>';
        html += '<td style="padding:8px 10px;color:#888;font-size:11px">' + mtimeStr + '</td>';
        html += '<td style="padding:8px 10px;text-align:center"><button class="btn btn-primary map-view-btn" style="padding:4px 16px;font-size:12px" data-file="' + escNameHtml + '">阅览</button></td>';
        html += '</tr>';
      });
      html += '</tbody></table>';
      listEl.innerHTML = html;
      // 用事件委托绑定阅览按钮
      var buttons = listEl.querySelectorAll('.map-view-btn');
      for (var i = 0; i < buttons.length; i++) {
        buttons[i].addEventListener('click', function() {
          openMapFile(this.getAttribute('data-file'));
        });
      }
    })
    .catch(function(e) {
      document.getElementById('mapInfo').textContent = '加载失败: ' + e.message;
      document.getElementById('mapFileList').innerHTML = '<div style="padding:32px;text-align:center;color:#d93025">加载失败: ' + e.message + '</div>';
    });
}

function openMapFile(filename) {
  window.open('/api/map/view/' + encodeURIComponent(filename), '_blank');
}

loadDefaultMaps();
</script>"""
    return _base_html("地图浏览", content, active="map")


def _render_config() -> str:
    env = {}
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    amap_key = env.get("AMAP_KEY", "")
    baidu_ak = env.get("BAIDU_AK", "")
    tianditu_tk = env.get("TIANDITU_TK", "")
    ai_enabled = env.get("AI_ENABLED", "false")
    ai_provider = env.get("AI_PROVIDER", "")
    deepseek_key = env.get("DEEPSEEK_API_KEY", "")

    def sel(val: str, target: str) -> str:
        return "selected" if val == target else ""

    content = """
<div class="card">
  <h2>API 密钥配置</h2>
  <p style="color:#888;margin-bottom:16px">至少配置一个地图 API 密钥即可使用。保存后将写入项目 .env 文件。</p>

  <div class="form-group">
    <label>高德地图 API Key (AMAP_KEY) <span class="tag tag-info">推荐</span></label>
    <div class="form-row">
      <input type="text" id="amapKey" value="%s" placeholder="32位 Key，免费申请">
      <button class="btn btn-secondary" style="width:auto" onclick="testKey('amap')">测试</button>
    </div>
    <span id="amapStatus"></span>
  </div>

  <div class="form-group">
    <label>百度地图 AK (BAIDU_AK)</label>
    <div class="form-row">
      <input type="text" id="baiduAk" value="%s" placeholder="百度地图 AK">
      <button class="btn btn-secondary" style="width:auto" onclick="testKey('baidu')">测试</button>
    </div>
    <span id="baiduStatus"></span>
  </div>

  <div class="form-group">
    <label>天地图 TK (TIANDITU_TK)</label>
    <div class="form-row">
      <input type="text" id="tiandituTk" value="%s" placeholder="天地图 Key">
      <button class="btn btn-secondary" style="width:auto" onclick="testKey('tianditu')">测试</button>
    </div>
    <span id="tiandituStatus"></span>
  </div>

  <hr style="margin:20px 0;border:0;border-top:1px solid #eee">

  <h3 style="font-size:16px;margin-bottom:12px;color:#555">AI 配置 (可选)</h3>

  <div class="form-group">
    <label>启用 AI</label>
    <select id="aiEnabled">
      <option value="false" %s>关闭</option>
      <option value="true" %s>开启</option>
    </select>
  </div>

  <div class="form-row">
    <div class="form-group">
      <label>AI 供应商</label>
      <select id="aiProvider">
        <option value="deepseek" %s>DeepSeek</option>
        <option value="qwen" %s>通义千问</option>
        <option value="glm" %s>智谱 GLM</option>
        <option value="moonshot" %s>Moonshot</option>
      </select>
    </div>
    <div class="form-group">
      <label>API Key</label>
      <input type="password" id="deepseekKey" value="%s" placeholder="sk-...">
    </div>
  </div>

  <button class="btn btn-primary" onclick="saveConfig()">保存配置</button>
  <span id="saveStatus" style="margin-left:12px;font-size:14px"></span>
</div>

<div class="card">
  <h2>API 使用统计</h2>
  <div id="quotaInfo">加载中...</div>
</div>

<script>
function testKey(provider) {
  var statusEl = document.getElementById(provider + 'Status');
  statusEl.innerHTML = '<span class="tag tag-info">测试中...</span>';
  var form = new FormData();
  form.append('amap_key', document.getElementById('amapKey').value);
  form.append('baidu_ak', document.getElementById('baiduAk').value);
  form.append('tianditu_tk', document.getElementById('tiandituTk').value);
  fetch('/api/config/test', {method:'POST', body:form})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d[provider]) statusEl.innerHTML = '<span class="tag tag-success">有效</span>';
      else statusEl.innerHTML = '<span class="tag tag-fail">无效</span>';
    })
    .catch(function() { statusEl.innerHTML = '<span class="tag tag-fail">网络错误</span>'; });
}

function saveConfig() {
  var form = new FormData();
  form.append('amap_key', document.getElementById('amapKey').value);
  form.append('baidu_ak', document.getElementById('baiduAk').value);
  form.append('tianditu_tk', document.getElementById('tiandituTk').value);
  form.append('ai_enabled', document.getElementById('aiEnabled').value);
  form.append('ai_provider', document.getElementById('aiProvider').value);
  form.append('deepseek_key', document.getElementById('deepseekKey').value);
  document.getElementById('saveStatus').innerHTML = '<span class="tag tag-info">保存中...</span>';
  fetch('/api/config/save', {method:'POST', body:form})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      document.getElementById('saveStatus').innerHTML = '<span class="tag tag-success">已保存</span>';
      setTimeout(function() { document.getElementById('saveStatus').innerHTML = ''; }, 3000);
    });
}

fetch('/api/quota').then(function(r) { return r.json(); }).then(function(d) {
  var html = '<p>总 API 调用: ' + (d.total_calls || 0) + '</p>';
  html += '<p>缓存命中: ' + (d.cache_hits || 0) + '</p>';
  html += '<p>缓存条目: ' + (d.cache_total || 0) + '</p>';
  document.getElementById('quotaInfo').innerHTML = html;
});
</script>""" % (
        amap_key, baidu_ak, tianditu_tk,
        sel(ai_enabled, "false"), sel(ai_enabled, "true"),
        sel(ai_provider, "deepseek"), sel(ai_provider, "qwen"),
        sel(ai_provider, "glm"), sel(ai_provider, "moonshot"),
        deepseek_key,
    )
    return _base_html("配置", content, active="config")

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
        workers: int = Form(1),
        use_cache: bool = Form(True),
    ):
        """上传文件并开始地理编码"""
        if not Config.validate():
            return JSONResponse({"error": "请先配置 API 密钥"}, status_code=400)

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

        with _tasks_lock:
            _tasks[task_id] = {"status": "running", "progress": 0, "total": len(addresses), "results": [], "error": None}

        thread = threading.Thread(target=_run_geocode, args=(task_id, addresses, column, int(workers), bool(use_cache)), daemon=True)
        thread.start()

        return JSONResponse({"task_id": task_id, "total": len(addresses)})

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
        # 返回精简结果（仅成功项的前200条）
        results = task["results"]
        success_results = [r for r in results if r.get("success")]
        return JSONResponse({
            "task_id": task_id,
            "status": task["status"],
            "total": task["total"],
            "success": len(success_results),
            "failed": len(results) - len(success_results),
            "results": success_results[:200],
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

    return app


def _run_geocode(task_id: str, addresses: list, column: str, workers: int, use_cache: bool):
    """后台执行地理编码任务"""
    try:
        cache = CacheManager(str(_OUTPUT_DIR / "geocache.db"))
        cache.start_watchdog(interval=30.0)
        logger = APILogger(str(_OUTPUT_DIR / "api调用日志.csv"))
        geocoder = Geocoder(cache, logger)

        results = []
        processed = 0
        total = len(addresses)

        if workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            max_workers = min(workers, 10)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(geocoder.geocode, addr): addr for addr in addresses}
                for future in as_completed(futures):
                    addr = futures[future]
                    results.append(future.result())
                    processed += 1
                    with _tasks_lock:
                        _tasks[task_id]["progress"] = int(processed / total * 100)
                        _tasks[task_id]["results"] = results
        else:
            for addr in addresses:
                result = geocoder.geocode(addr)
                results.append(result)
                processed += 1
                with _tasks_lock:
                    _tasks[task_id]["progress"] = int(processed / total * 100)
                    _tasks[task_id]["results"] = results

        geocoder.close()

        with _tasks_lock:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["results"] = results
            _tasks[task_id]["progress"] = 100
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
      <select id="workers"><option value="1">1 (串行)</option><option value="2">2</option><option value="3">3</option><option value="5">5</option></select>
    </div>
  </div>

  <button class="btn btn-primary" id="startBtn" disabled onclick="startGeocode()">开始地理编码</button>

  <div id="progressArea" style="display:none;margin-top:20px">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px">
      <span id="progressText">处理中...</span>
      <span id="progressPercent">0%</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
  </div>

  <div id="resultArea" style="margin-top:16px"></div>
</div>

<div class="card" style="display:none" id="mapCard">
  <h2>地图预览</h2>
  <button class="btn btn-secondary" style="margin-bottom:12px" onclick="loadMap()">加载地图</button>
  <div id="mapContainer"></div>
</div>

<script>
let taskId = null;
let pollTimer = null;

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
      document.getElementById('mapCard').style.display = 'block';
      pollTask();
    });
}

function pollTask() {
  if (!taskId) return;
  fetch('/api/geocode/status/' + taskId)
    .then(r => r.json())
    .then(data => {
      const pct = data.progress || 0;
      document.getElementById('progressFill').style.width = pct + '%';
      document.getElementById('progressPercent').textContent = pct + '%';
      document.getElementById('progressText').textContent = '已处理 ' + data.progress + '/' + data.total;

      if (data.status === 'done') {
        document.getElementById('startBtn').disabled = false;
        document.getElementById('startBtn').textContent = '开始地理编码';
        fetch('/api/geocode/result/' + taskId)
          .then(r => r.json())
          .then(d => {
            if (d.results) {
              let html = '<h3 style="margin-bottom:12px">结果 (' + d.success + ' 成功, ' + d.failed + ' 失败)</h3>';
              d.results.slice(0, 50).forEach(r => {
                html += '<div class="result-item"><span class="' + (r.success ? 'result-success' : 'result-fail') + '">'
                  + (r.original_address || '?') + ' → ' + (r.latitude||'?') + ', ' + (r.longitude||'?')
                  + '</span> <span class="tag tag-info">' + (r.source || '') + '</span></div>';
              });
              if (d.results.length > 50) html += '<p style="color:#888;margin-top:8px">仅显示前 50 条结果</p>';
              document.getElementById('resultArea').innerHTML = html;
            }
          });
        clearInterval(pollTimer);
      } else if (data.status === 'error') {
        document.getElementById('resultArea').innerHTML = '<p style="color:#d93025">错误: ' + (data.error || '未知') + '</p>';
        clearInterval(pollTimer);
      }
    });
  if (!pollTimer) pollTimer = setInterval(pollTask, 2000);
}

function loadMap() {
  if (!taskId) return;
  fetch('/api/map/' + taskId)
    .then(r => r.text())
    .then(html => { document.getElementById('mapContainer').innerHTML = html; });
}
</script>"""
    return _base_html("地理编码", content, active="index")


def _render_map_viewer() -> str:
    content = """
<div class="card">
  <h2>地图浏览</h2>
  <p style="color:#888;margin-bottom:16px">完成地理编码任务后可在此查看地图</p>
  <div class="form-group">
    <label>任务 ID</label>
    <div class="form-row">
      <input type="text" id="mapTaskId" placeholder="输入任务 ID">
      <button class="btn btn-primary" onclick="viewMap()" style="width:auto">加载地图</button>
    </div>
  </div>
  <div id="mapContainer"></div>
</div>

<div class="card">
  <h2>最近输出文件</h2>
  <ul id="fileList" style="list-style:none;font-size:14px;color:#888">加载中...</ul>
</div>

<script>
function viewMap() {
  const tid = document.getElementById('mapTaskId').value.trim();
  if (!tid) return;
  fetch('/api/map/' + tid)
    .then(r => r.text())
    .then(html => { document.getElementById('mapContainer').innerHTML = html; })
    .catch(() => { document.getElementById('mapContainer').innerHTML = '<p style="color:#d93025">地图加载失败</p>'; });
}

fetch('/api/quota').then(r => r.json()).then(d => {
  let html = '';
  if (d.api_usage) {
    for (const [k, v] of Object.entries(d.api_usage)) {
      html += '<li>&#8226; ' + k + ': ' + v + ' 次调用</li>';
    }
  }
  html += '<li>&#8226; 缓存: ' + (d.cache_total || 0) + ' 条记录</li>';
  document.getElementById('fileList').innerHTML = html || '<li>暂无数据</li>';
});
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

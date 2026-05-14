import { API_BASE } from './constants';
import type {
  GeocodeResult,
  MapFile,
  DataFile,
  CacheStats,
  APIConfig,
  ConvertResult,
  CoordSystem,
  HealthInfo,
  ChatMessage,
  ConfigSaveRequest,
  ConfigTestResponse,
  BatchStatusResponse,
  CompletedTask,
  TasksResponse,
} from './types';

// ── Fetch 封装 ──
class ApiError extends Error {
  code: number;
  constructor(message: string, code: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.error || body.detail || `请求失败 (HTTP ${res.status})`,
      res.status
    );
  }

  return res.json();
}

// ── 健康检查 (F14) ──
export async function fetchHealth(signal?: AbortSignal): Promise<HealthInfo> {
  return request<HealthInfo>('/api/health', {}, signal);
}

// ── 单地址地理编码 (F1) ──
export async function geocodeSingle(
  address: string,
  signal?: AbortSignal
): Promise<GeocodeResult> {
  return request<GeocodeResult>(
    '/api/geocode/single',
    {
      method: 'POST',
      body: JSON.stringify({ address }),
    },
    signal
  );
}

// ── 逆地理编码 (F4) ──
export async function reverseGeocode(
  lat: number,
  lon: number,
  signal?: AbortSignal
): Promise<GeocodeResult> {
  return request<GeocodeResult>(
    '/api/geocode/reverse',
    {
      method: 'POST',
      body: JSON.stringify({ latitude: lat, longitude: lon }),
    },
    signal
  );
}

// ── 坐标转换 (F5) ──
export async function convertCoords(
  lat: number,
  lon: number,
  from: CoordSystem,
  to: CoordSystem,
  signal?: AbortSignal
): Promise<ConvertResult> {
  return request<ConvertResult>(
    '/api/geocode/convert',
    {
      method: 'POST',
      body: JSON.stringify({ latitude: lat, longitude: lon, from, to }),
    },
    signal
  );
}

// ── 批量地理编码 SSE 流式 (F2-F3) ──
export function batchGeocodeStream(
  file: File,
  column: string,
  workers: string,
  city: string | null,
  onProgress: (event: {
    step: string;
    label: string;
    status: string;
    total: number;
    current: number;
    success: number;
  }) => void,
  onResult: (result: GeocodeResult) => void,
  onComplete: (taskId: string, results: GeocodeResult[]) => void,
  onError: (error: string) => void,
  signal?: AbortSignal
): void {
  const form = new FormData();
  form.append('file', file);
  form.append('column', column);
  form.append('workers', workers);
  if (city && city.trim()) {
    form.append('city', city.trim());
  }

  const url = `${API_BASE}/api/geocode/batch/stream`;

  fetch(url, { method: 'POST', body: form, signal })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        onError(body.error || `请求失败 (HTTP ${res.status})`);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        onError('浏览器不支持流式读取');
        return;
      }
      const decoder = new TextDecoder();
      let buffer = '';
      let taskId = '';
      const results: GeocodeResult[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') {
            onComplete(taskId, results);
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              onError(parsed.error);
              return;
            }
            if (parsed.task_id) {
              taskId = parsed.task_id;
            }
            // 逐条 geocode 结果
            if (parsed.type === 'geocode_result' && parsed.data) {
              results.push(parsed.data);
              onResult(parsed.data);
            }
            // 任何包含 current 和 total 字段的事件都作为进度推送
            if (parsed.current !== undefined && parsed.total !== undefined) {
              console.log('[api.ts] onProgress 触发:', { current: parsed.current, total: parsed.total, success: parsed.success })
              onProgress(parsed);
            }
          } catch {
            // skip non-JSON lines
          }
        }
      }
      onComplete(taskId, results);
    })
    .catch((e) => {
      if (e.name === 'AbortError') return;
      onError(e.message || '网络错误');
    });
}

// ── 轮询批量任务状态 (F3) ──
export async function fetchTaskStatus(
  taskId: string,
  signal?: AbortSignal
): Promise<BatchStatusResponse> {
  return request<BatchStatusResponse>(
    `/api/geocode/task/${taskId}`,
    {},
    signal
  );
}

// ── 地图文件列表 (F7) ──
export async function fetchMapFiles(signal?: AbortSignal): Promise<MapFile[]> {
  const data = await request<{ maps: MapFile[]; count: number }>(
    '/api/maps',
    {},
    signal
  );
  return data.maps || [];
}

// ── 地图文件阅览 URL ──
export function getMapViewUrl(filename: string): string {
  return `${API_BASE}/api/map/view/${encodeURIComponent(filename)}`;
}

// ── 数据文件列表 (F8) ──
export async function fetchDataFiles(
  signal?: AbortSignal
): Promise<DataFile[]> {
  const data = await request<{ files: DataFile[]; count: number }>(
    '/api/files',
    {},
    signal
  );
  return data.files || [];
}

// ── AI 聊天 (SSE 流式) (F9) ──
export function chatStream(
  prompt: string,
  context: ChatMessage[],
  onToken: (token: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal
): void {
  const url = `${API_BASE}/api/chat/stream`;
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, context }),
    signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        onError(body.error || '请求失败');
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        onError('浏览器不支持流式读取');
        return;
      }
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') {
            onComplete();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              onError(parsed.error);
              return;
            }
            if (parsed.token) onToken(parsed.token);
          } catch {
            // skip
          }
        }
      }
      onComplete();
    })
    .catch((e) => {
      if (e.name === 'AbortError') return;
      onError(e.message || '网络错误');
    });
}

// ── AI 命令执行 (F10, F11) ──
export async function executeCommand(
  command: string,
  signal?: AbortSignal
): Promise<{ command: string; exit_code: number; stdout: string; stderr: string; success: boolean }> {
  return request('/api/execute', {
    method: 'POST',
    body: JSON.stringify({ command }),
  }, signal);
}

// ── 配置获取 (F12) ──
export async function fetchConfig(signal?: AbortSignal): Promise<APIConfig> {
  return request<APIConfig>('/api/config', {}, signal);
}

// ── 配置保存 (F12) ──
export async function saveConfig(
  config: ConfigSaveRequest,
  signal?: AbortSignal
): Promise<{ success: boolean; message: string }> {
  const form = new FormData();
  form.append('amap_key', config.amap_key);
  form.append('baidu_ak', config.baidu_ak);
  form.append('tianditu_tk', config.tianditu_tk);
  form.append('ai_enabled', config.ai_enabled);
  form.append('ai_provider', config.ai_provider);
  form.append('deepseek_key', config.deepseek_key);

  const url = `${API_BASE}/api/config/save`;
  const res = await fetch(url, { method: 'POST', body: form, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.error || '保存失败', res.status);
  }
  return res.json();
}

// ── API Key 测试 (F12) ──
export async function testAPIKeys(
  keys: { amap_key?: string; baidu_ak?: string; tianditu_tk?: string },
  signal?: AbortSignal
): Promise<ConfigTestResponse> {
  const form = new FormData();
  if (keys.amap_key) form.append('amap_key', keys.amap_key);
  if (keys.baidu_ak) form.append('baidu_ak', keys.baidu_ak);
  if (keys.tianditu_tk) form.append('tianditu_tk', keys.tianditu_tk);
  const url = `${API_BASE}/api/config/test`;
  const res = await fetch(url, { method: 'POST', body: form, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.error || '测试失败', res.status);
  }
  return res.json();
}

// ── 缓存管理 (F13) ──
export async function fetchCacheStats(
  signal?: AbortSignal
): Promise<CacheStats> {
  return request<CacheStats>('/api/cache/stats', {}, signal);
}

export async function clearCache(
  signal?: AbortSignal
): Promise<{ cleared: number }> {
  return request('/api/cache/clear', { method: 'POST' }, signal);
}

export async function cleanupCache(
  signal?: AbortSignal
): Promise<{ removed: number }> {
  return request('/api/cache/cleanup', { method: 'POST' }, signal);
}

export async function exportCache(
  signal?: AbortSignal
): Promise<{ stats: CacheStats; exported_at: number }> {
  return request('/api/cache/export', {}, signal);
}

// ── 任务历史 (已完成任务) ──
export async function fetchCompletedTasks(
  signal?: AbortSignal
): Promise<CompletedTask[]> {
  const data = await request<TasksResponse>('/api/tasks', {}, signal);
  return data.tasks || [];
}

export async function fetchTaskDetail(
  taskId: string,
  signal?: AbortSignal
): Promise<CompletedTask> {
  return request<CompletedTask>(`/api/tasks/${taskId}`, {}, signal);
}

export async function deleteTask(
  taskId: string,
  signal?: AbortSignal
): Promise<{ success: boolean; message: string }> {
  return request(`/api/tasks/${taskId}`, { method: 'DELETE' }, signal);
}

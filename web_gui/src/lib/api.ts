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
  ConfigHistoryEntry,
} from './types';

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

// ── 健康检查 ──
export async function fetchHealth(signal?: AbortSignal): Promise<HealthInfo> {
  return request<HealthInfo>('/api/health', {}, signal);
}

// ── 单地址地理编码 ──
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

// ── 逆地理编码 ──
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

// ── 坐标转换 ──
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

// ── 批量地理编码 SSE 流式 ──
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
            if (parsed.type === 'geocode_result' && parsed.data) {
              results.push(parsed.data);
              onResult(parsed.data);
            }
            if (parsed.current !== undefined && parsed.total !== undefined) {
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

// ── 轮询批量任务状态 ──
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

// ── 地图文件列表 ──
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

// ── 数据文件列表 ──
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

// ── AI 聊天 (SSE 流式) ──
const SSE_CHUNK_TIMEOUT_MS = 30_000

export function chatStream(
  prompt: string,
  context: { role: string; content: string }[],
  onToken: (token: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
  onReasoning?: (token: string) => void,
  sessionId?: string
): void {
  const url = `${API_BASE}/api/chat/stream`
  const controller = signal ? undefined : new AbortController()
  const abortSignal = signal || controller?.signal

  let lastChunkTime = Date.now()
  let chunkTimer: ReturnType<typeof setInterval> | null = null

  if (!signal) {
    chunkTimer = setInterval(() => {
      if (Date.now() - lastChunkTime > SSE_CHUNK_TIMEOUT_MS) {
        onError('AI 响应超时，请检查网络连接后重试')
        if (controller) controller.abort()
        if (chunkTimer) clearInterval(chunkTimer)
      }
    }, 5000)
  }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, context, session_id: sessionId }),
    signal: abortSignal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        onError(body.error || body.detail || `请求失败 (HTTP ${res.status})`)
        return
      }
      const reader = res.body?.getReader()
      if (!reader) {
        onError('浏览器不支持流式读取')
        return
      }
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        lastChunkTime = Date.now()
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') {
            if (chunkTimer) clearInterval(chunkTimer)
            onComplete()
            return
          }
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) {
              if (chunkTimer) clearInterval(chunkTimer)
              onError(parsed.error)
              return
            }
            if (parsed.type === 'reasoning' && onReasoning) {
              onReasoning(parsed.content || '')
            } else if (parsed.type === 'content') {
              onToken(parsed.content || '')
            } else if (parsed.token) {
              onToken(parsed.token)
            }
          } catch {
            // skip
          }
        }
      }
      if (chunkTimer) clearInterval(chunkTimer)
      onComplete()
    })
    .catch((e) => {
      if (chunkTimer) clearInterval(chunkTimer)
      if (e.name === 'AbortError') return
      onError(e.message || '网络错误')
    })
}

// ── AI Agent 循环 (SSE 流式 — 统一后端) ──

export interface AgentStreamCallbacks {
  onContent: (token: string) => void
  onReasoning: (token: string) => void
  onToolUse: (tool: { id: string; name: string; arguments: string }) => void
  onToolUseDelta: (delta: { id: string; name: string; arguments_delta: string }) => void
  onToolResult: (result: { command: string; result: string; success: boolean }) => void
  onToolError: (error: { command: string; error: { code: string; message: string; recoverable: boolean; autoFixAction?: string }; recoverable: boolean; autoFixAction?: string }) => void
  onToolRecovery: (info: { original_command: string; fix_command?: string; wait_seconds?: number }) => void
  onRoundStart: (info: { round: number; max_rounds: number }) => void
  onDone: () => void
  onError: (error: { code: string; message: string }) => void
}

export function agentStream(
  prompt: string,
  callbacks: AgentStreamCallbacks,
  options?: { context?: { role: string; content: string }[]; sessionId?: string; useTools?: boolean; signal?: AbortSignal }
): void {
  const url = `${API_BASE}/api/chat/agent`
  const abortSignal = options?.signal

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      context: options?.context || [],
      session_id: options?.sessionId,
      use_tools: options?.useTools !== false,
    }),
    signal: abortSignal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        callbacks.onError({ code: String(res.status), message: body.error || body.detail || `请求失败 (HTTP ${res.status})` })
        return
      }
      const reader = res.body?.getReader()
      if (!reader) {
        callbacks.onError({ code: 'network', message: '浏览器不支持流式读取' })
        return
      }
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        if (abortSignal?.aborted) break
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') {
            callbacks.onDone()
            return
          }
          try {
            const event = JSON.parse(data)
            switch (event.type) {
              case 'content':
                callbacks.onContent(event.content || '')
                break
              case 'reasoning':
                callbacks.onReasoning(event.content || '')
                break
              case 'tool_use':
                callbacks.onToolUse({ id: event.id || '', name: event.name || '', arguments: event.arguments || '' })
                break
              case 'tool_use_delta':
                callbacks.onToolUseDelta({ id: event.id || '', name: event.name || '', arguments_delta: event.arguments_delta || '' })
                break
              case 'tool_result':
                callbacks.onToolResult({
                  command: event.command || '',
                  result: event.result || '',
                  success: event.success !== false,
                })
                break
              case 'tool_error':
                callbacks.onToolError({
                  command: event.command || '',
                  error: event.error || { code: 'unknown', message: '未知错误', recoverable: false },
                  recoverable: event.recoverable || false,
                  autoFixAction: event.auto_fix_action,
                })
                break
              case 'tool_recovery':
                callbacks.onToolRecovery({
                  original_command: event.original_command || '',
                  fix_command: event.fix_command,
                  wait_seconds: event.wait_seconds,
                })
                break
              case 'round_start':
                callbacks.onRoundStart({ round: event.round || 1, max_rounds: event.max_rounds || 4 })
                break
              case 'done':
                callbacks.onDone()
                return
              case 'error':
                callbacks.onError({ code: event.code || 'unknown', message: event.message || '未知错误' })
                break
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
      callbacks.onDone()
    })
    .catch((e) => {
      if (e.name === 'AbortError') return
      callbacks.onError({ code: 'network', message: e.message || '网络错误' })
    })
}

// ── AI 命令执行 ──
export async function executeCommand(
  command: string,
  signal?: AbortSignal
): Promise<{ command: string; exit_code: number; stdout: string; stderr: string; success: boolean }> {
  return request('/api/execute', {
    method: 'POST',
    body: JSON.stringify({ command }),
  }, signal);
}

// ── 打开目录 ──
export async function openDirectory(
  type: 'output/map' | 'output/csv' | 'data'
): Promise<{ opened: string; type: string }> {
  return request('/api/open/directory', {
    method: 'POST',
    body: JSON.stringify({ type }),
  });
}

// ── 配置获取 ──
export async function fetchConfig(signal?: AbortSignal): Promise<APIConfig> {
  return request<APIConfig>('/api/config', {}, signal);
}

// ── 配置保存 ──
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
  form.append('ai_model', config.ai_model || '');
  form.append('deepseek_key', config.deepseek_key);
  form.append('qwen_key', config.qwen_key);
  form.append('glm_key', config.glm_key);
  form.append('moonshot_key', config.moonshot_key);
  form.append('routing_mode', config.routing_mode || 'ai');

  const url = `${API_BASE}/api/config/save`;
  const res = await fetch(url, { method: 'POST', body: form, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.error || '保存失败', res.status);
  }
  return res.json();
}

// ── API Key 测试 ──
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

// ── 配置变更历史 ──
export async function fetchConfigHistory(
  key?: string,
  limit: number = 50,
  signal?: AbortSignal
): Promise<{ history: ConfigHistoryEntry[]; count: number }> {
  const params = new URLSearchParams();
  if (key) params.set('key', key);
  params.set('limit', String(limit));
  return request(`/api/config/history?${params.toString()}`, {}, signal);
}

// ── API 配额使用 ──
export async function fetchApiUsage(
  days: number = 30,
  signal?: AbortSignal
): Promise<{ usage: any[]; today: Record<string, any> }> {
  return request(`/api/usage?days=${days}`, {}, signal);
}

export async function fetchApiUsageDetail(
  apiName: string,
  days: number = 30,
  signal?: AbortSignal
): Promise<{ api_name: string; today: any; history: any[] }> {
  return request(`/api/usage/${apiName}?days=${days}`, {}, signal);
}

// ── 缓存管理 ──
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
): Promise<{ stats: CacheStats; exported_at: number; entries: any[] }> {
  return request('/api/cache/export', {}, signal);
}

// ── 任务历史 ──
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

// ── AI 路线规划 (非交互式) ──
export async function aiRoute(
  params: {
    input_file: string;
    num_routes?: number;
    travel_mode?: string;
    start_address?: string;
    start_point?: { lat: number; lon: number };
  },
  signal?: AbortSignal
): Promise<{ success: boolean; message: string }> {
  return request('/api/ai/route', {
    method: 'POST',
    body: JSON.stringify(params),
  }, signal);
}

// ── AI 数据分析 (SSE 流式) ──
export function aiAnalyzeStream(
  inputFile: string,
  onToken: (token: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal
): void {
  const url = `${API_BASE}/api/ai/analyze/stream`
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_file: inputFile }),
    signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        onError(body.error || body.detail || `请求失败 (HTTP ${res.status})`)
        return
      }
      const reader = res.body?.getReader()
      if (!reader) {
        onError('浏览器不支持流式读取')
        return
      }
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') {
            onComplete()
            return
          }
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) {
              onError(parsed.error)
              return
            }
            if (parsed.token) onToken(parsed.token)
          } catch {
            // skip
          }
        }
      }
      onComplete()
    })
    .catch((e) => {
      if (e.name === 'AbortError') return
      onError(e.message || '网络错误')
    })
}

// ── AI 对话会话管理 ──

export interface ChatSessionInfo {
  id: string
  title: string
  created_at: number
  updated_at: number
}

export async function listSessions(signal?: AbortSignal): Promise<{ sessions: ChatSessionInfo[]; count: number }> {
  return request('/api/chat/sessions', {}, signal)
}

export async function createSession(title: string = '', signal?: AbortSignal): Promise<ChatSessionInfo> {
  return request('/api/chat/sessions', { method: 'POST', body: JSON.stringify({ title }) }, signal)
}

export async function getSession(sessionId: string, signal?: AbortSignal): Promise<{ session: ChatSessionInfo; messages: ChatMessage[] }> {
  return request(`/api/chat/sessions/${sessionId}`, {}, signal)
}

export async function deleteSession(sessionId: string, signal?: AbortSignal): Promise<{ status: string }> {
  return request(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' }, signal)
}

export async function addMessage(sessionId: string, role: string, content: string, reasoning: string = '', signal?: AbortSignal): Promise<ChatMessage> {
  return request(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ role, content, reasoning }),
  }, signal)
}

export async function compactSession(sessionId: string, summary?: string, signal?: AbortSignal): Promise<{ status: string; summary: string }> {
  return request(`/api/chat/sessions/${sessionId}/compact`, {
    method: 'POST',
    body: JSON.stringify(summary ? { summary } : {}),
  }, signal)
}

export async function getSessionContext(sessionId: string, maxMessages: number = 30, signal?: AbortSignal): Promise<{ context: ChatMessage[] }> {
  return request(`/api/chat/sessions/${sessionId}/context?max_messages=${maxMessages}`, {}, signal)
}

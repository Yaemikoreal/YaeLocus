/**
 * HTTP 通信层 — 调用 Python API server
 */

const PORT = process.env.YAELOCUS_PORT || '8765';
const BASE = `http://127.0.0.1:${PORT}`;

export interface HealthStatus {
  status: string;
  version: string;
  apis: string[];
  ai_enabled: boolean;
}

export interface ConfigStatus {
  apis: string[];
  ai_enabled: boolean;
  ai_provider: string;
  routing_mode: string;
  cache: { total_entries: number; hits: number; misses: number; hit_rate: number };
}

export interface CacheStats {
  total_entries: number;
  hits: number;
  misses: number;
  hit_rate: number;
  [key: string]: unknown;
}

export interface FileEntry {
  name: string;
  path: string;
  size_kb: number;
  modified: number;
}

export interface MapEntry {
  name: string;
  path: string;
  size_kb: number;
  modified: number;
}

export interface GeocodeResult {
  success: boolean;
  address: string;
  longitude: number;
  latitude: number;
  formatted_address: string;
  province: string;
  city: string;
  district: string;
  source: string;
}

export interface CommandResult {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  success: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export function useAPI() {
  return {
    /** 健康检查 */
    async health(): Promise<HealthStatus> {
      return fetchJSON(`${BASE}/api/health`);
    },

    /** 获取配置状态 */
    async getConfig(): Promise<ConfigStatus> {
      return fetchJSON(`${BASE}/api/config`);
    },

    /** 获取缓存统计 */
    async getCacheStats(): Promise<CacheStats> {
      return fetchJSON(`${BASE}/api/cache/stats`);
    },

    /** 清空缓存 */
    async clearCache(): Promise<{ cleared: number }> {
      return fetchJSON(`${BASE}/api/cache/clear`, { method: 'POST' });
    },

    /** 清理过期缓存 */
    async cleanupCache(): Promise<{ removed: number; message: string }> {
      return fetchJSON(`${BASE}/api/cache/cleanup`, { method: 'POST' });
    },

    /** 列出可处理文件 */
    async listFiles(): Promise<{ files: FileEntry[]; count: number }> {
      return fetchJSON(`${BASE}/api/files`);
    },

    /** 列出地图文件 */
    async listMaps(): Promise<{ maps: MapEntry[]; count: number }> {
      return fetchJSON(`${BASE}/api/maps`);
    },

    /** 单地址编码 */
    async geocodeSingle(address: string): Promise<GeocodeResult> {
      return fetchJSON(`${BASE}/api/geocode/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address }),
      });
    },

    /** 批量编码（异步，返回 task_id） */
    async geocodeBatch(file: string, column?: string): Promise<{ task_id: string; status: string }> {
      return fetchJSON(`${BASE}/api/geocode/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file, column: column || '地址' }),
      });
    },

    /** 查询批量任务状态 */
    async getTaskStatus(taskId: string): Promise<Record<string, unknown>> {
      return fetchJSON(`${BASE}/api/geocode/task/${taskId}`);
    },

    /** 逆地理编码 */
    async geocodeReverse(lat: number, lon: number): Promise<GeocodeResult> {
      return fetchJSON(`${BASE}/api/geocode/reverse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: lat, longitude: lon }),
      });
    },

    /** 坐标转换 */
    async geocodeConvert(lat: number, lon: number, from: string, to: string): Promise<Record<string, unknown>> {
      return fetchJSON(`${BASE}/api/geocode/convert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: lat, longitude: lon, from, to }),
      });
    },

    /** 执行 CLI 命令 */
    async execute(command: string): Promise<CommandResult> {
      return fetchJSON(`${BASE}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      });
    },

    /** 非流式 AI 对话 */
    async chat(prompt: string, context: ChatMessage[] = []): Promise<{ content: string; role: string }> {
      return fetchJSON(`${BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, context }),
      });
    },

    /** 读取文件内容 */
    async readFile(path: string): Promise<Record<string, unknown>> {
      return fetchJSON(`${BASE}/api/file/content?path=${encodeURIComponent(path)}`);
    },

    /** 在系统默认浏览器中打开文件 */
    async openFile(path: string): Promise<{ opened: string }> {
      return fetchJSON(`${BASE}/api/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
    },

    /** 流式 AI 对话 — 返回 ReadableStream */
    async chatStream(prompt: string, context: ChatMessage[] = []): Promise<Response> {
      return fetch(`${BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, context }),
      });
    },

    /** 流式 Agent Loop — 返回 ReadableStream (统一后端) */
    async agentStream(prompt: string, context: ChatMessage[] = [], sessionId?: string): Promise<Response> {
      return fetch(`${BASE}/api/chat/agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, context, session_id: sessionId, use_tools: true }),
      });
    },
  };
}

// ── 地理编码结果 ──
export interface GeocodeResult {
  success: boolean;
  latitude: number;
  longitude: number;
  original_address: string;
  formatted_address?: string | null;
  province?: string | null;
  city?: string | null;
  district?: string | null;
  source: 'amap' | 'tianditu' | 'baidu';
  coordinate_system: 'GCJ-02' | 'BD-09' | 'CGCS2000';
  confidence?: ConfidenceScore | null;
  warning?: string | null;
}

export interface ConfidenceScore {
  total: number;
  address_match: number;
  province_match: number;
  completeness: number;
  coord_valid: number;
  issues: string[];
  is_trustworthy: boolean;
}

export type TaskStatus = 'running' | 'done' | 'error';

export interface TaskInfo {
  task_id: string;
  status: TaskStatus;
  progress: number;
  total: number;
  results: GeocodeResult[];
  error?: string | null;
}

// ── 地图文件 ──
export interface MapFile {
  name: string;
  path: string;
  size_kb: number;
  modified: number;
}

// ── 数据文件 ──
export interface DataFile {
  name: string;
  path: string;
  size_kb: number;
  modified: number;
}

// ── 缓存统计 ──
export interface CacheStats {
  hits: number;
  misses: number;
  hit_rate: number;
  total_entries: number;
  expired_entries: number;
  pending_writes: number;
}

// ── API 配置 ──
export interface APIConfig {
  apis: string[];
  ai_enabled: boolean;
  ai_provider: string;
  routing_mode: string;
  cache: CacheStats;
}

// ── 坐标转换 ──
export interface ConvertInput {
  latitude: number;
  longitude: number;
  system: string;
}

export interface ConvertResult {
  input: ConvertInput;
  output: ConvertInput;
}

export type CoordSystem = 'wgs84' | 'gcj02' | 'bd09';

// ── 健康检查 ──
export interface HealthInfo {
  status: string;
  version: string;
  apis: string[];
  ai_enabled: boolean;
}

// ── 文件列表响应 ──
export interface FilesResponse {
  files: DataFile[];
  count: number;
}

export interface MapsResponse {
  maps: MapFile[];
  count: number;
}

// ── 批量任务响应 ──
export interface BatchStartResponse {
  task_id: string;
  status: string;
  total?: number;
}

export interface BatchStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: number;
  total: number;
  error?: string | null;
  results?: GeocodeResult[];
}

// ── AI 消息 ──
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  prompt: string;
  context: ChatMessage[];
}

// ── SSE 事件 ──
export interface SSEProgressEvent {
  step: string;
  label: string;
  status: string;
  total: number;
  current: number;
  success: number;
}

export interface SSETokenEvent {
  token: string;
}

// ── 配置保存 ──
export interface ConfigSaveRequest {
  amap_key: string;
  baidu_ak: string;
  tianditu_tk: string;
  ai_enabled: string;
  ai_provider: string;
  deepseek_key: string;
}

export interface ConfigTestResponse {
  amap?: boolean;
  baidu?: boolean;
  tianditu?: boolean;
}

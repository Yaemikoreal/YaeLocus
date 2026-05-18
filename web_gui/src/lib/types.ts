// ── 地理编码结果 ──
export interface GeocodeResult {
  success: boolean;
  latitude: number;
  longitude: number;
  original_address?: string;
  formatted_address?: string | null;
  province?: string | null;
  city?: string | null;
  district?: string | null;
  source?: 'amap' | 'tianditu' | 'baidu' | string;
  coordinate_system?: 'GCJ-02' | 'BD-09' | 'CGCS2000' | string;
  confidence?: ConfidenceScore | null;
  warning?: string | null;
  error?: string | null;
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
  mem_entries?: number;
  mem_max?: number;
  expired_entries?: number;
  queue_size?: number;
  pending_writes?: number;
  evictions?: number;
}

// ── API 配额使用 ──
export interface ApiUsageToday {
  api_name: string;
  call_date: string;
  call_count: number;
  success_count: number;
  fail_count: number;
  daily_limit: number;
  remaining: number;
  last_called: number | null;
}

// ── API 配置 ──
export interface APIConfig {
  apis: string[];
  amap_key_configured?: boolean;
  amap_key_masked?: string;
  baidu_ak_configured?: boolean;
  baidu_ak_masked?: string;
  tianditu_tk_configured?: boolean;
  tianditu_tk_masked?: string;
  ai_enabled: boolean;
  ai_provider: string;
  ai_model?: string;
  deepseek_key_configured?: boolean;
  deepseek_key_masked?: string;
  qwen_key_configured?: boolean;
  qwen_key_masked?: string;
  glm_key_configured?: boolean;
  glm_key_masked?: string;
  moonshot_key_configured?: boolean;
  moonshot_key_masked?: string;
  routing_mode?: string;
  api_usage?: Record<string, ApiUsageToday>;
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

// ── 批量任务响应 ──
export interface BatchStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: number;
  total: number;
  error?: string | null;
  results?: GeocodeResult[];
}

// ── 已完成任务历史 ──
export interface CompletedTask {
  task_id: string;
  status: 'running' | 'done' | 'error';
  input_file: string;
  column: string;
  city?: string | null;
  workers?: number;
  total: number;
  success: number;
  failed: number;
  csv_output?: string | null;
  map_output?: string | null;
  started_at: number;
  completed_at?: number | null;
  duration_sec?: number | null;
  error?: string | null;
  results?: GeocodeResult[];
}

export interface TasksResponse {
  tasks: CompletedTask[];
  count: number;
}

// ── AI 消息 ──
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

// ── 配置保存 ──
export interface ConfigSaveRequest {
  amap_key: string;
  baidu_ak: string;
  tianditu_tk: string;
  ai_enabled: string;
  ai_provider: string;
  ai_model: string;
  deepseek_key: string;
  qwen_key: string;
  glm_key: string;
  moonshot_key: string;
  routing_mode: string;
}

export interface ConfigTestResponse {
  amap?: boolean | null;
  baidu?: boolean | null;
  tianditu?: boolean | null;
}

// ── 配置变更历史 ──
export interface ConfigHistoryEntry {
  id: number;
  key: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: number;
  changed_via: string;
}

// ── 缓存导出条目 ──
export interface CacheExportEntry {
  key: string;
  address: string;
  source: string | null;
  formatted_address: string | null;
  province: string | null;
  city: string | null;
  district: string | null;
  latitude: number | null;
  longitude: number | null;
  confidence: number | null;
  created_at: number | null;
  expires_at: number | null;
  access_count: number | null;
  last_accessed: number | null;
}

// 开发时通过 Vite proxy 代理到 localhost:8765
// 生产时由 FastAPI 同源提供
export const API_BASE = '';

export const COORD_SYSTEMS = {
  wgs84: { label: 'WGS-84', description: 'GPS 原始坐标（国际标准）' },
  gcj02: { label: 'GCJ-02', description: '中国国测局加密坐标（高德/腾讯）' },
  bd09: { label: 'BD-09', description: '百度加密坐标' },
} as const;

export const API_SOURCES = {
  amap: { label: '高德地图', color: '#1a73e8' },
  tianditu: { label: '天地图', color: '#1e8e3e' },
  baidu: { label: '百度地图', color: '#d93025' },
} as const;

export const COORD_LIMITS = {
  lat: { min: -90, max: 90 },
  lon: { min: -180, max: 180 },
} as const;

export const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
export const ALLOWED_FILE_TYPES = ['.csv', '.xlsx', '.xls'];

export const WORKER_OPTIONS = ['auto', '1', '2', '3', '5'] as const;

export const AI_PROVIDERS = {
  deepseek: 'DeepSeek',
  qwen: '通义千问',
  glm: '智谱 GLM',
  moonshot: 'Moonshot',
} as const;

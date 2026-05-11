import { COORD_LIMITS, ALLOWED_FILE_TYPES, MAX_FILE_SIZE } from './constants';

// ── 坐标校验 ──
export function isValidLat(lat: number): boolean {
  return !isNaN(lat) && lat >= COORD_LIMITS.lat.min && lat <= COORD_LIMITS.lat.max;
}

export function isValidLon(lon: number): boolean {
  return !isNaN(lon) && lon >= COORD_LIMITS.lon.min && lon <= COORD_LIMITS.lon.max;
}

export function parseCoordinate(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const num = Number(trimmed);
  return isNaN(num) ? null : num;
}

// ── 文件校验 ──
export function validateFile(file: File): string | null {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!ALLOWED_FILE_TYPES.includes(ext)) {
    return `不支持的文件格式（${ext}），请上传 CSV / XLSX / XLS 文件`;
  }
  if (file.size > MAX_FILE_SIZE) {
    return `文件过大（${(file.size / 1024 / 1024).toFixed(1)} MB），请上传小于 100 MB 的文件`;
  }
  if (file.size === 0) {
    return '文件为空，请重新选择';
  }
  return null;
}

// ── 格式化 ──
export function formatCoords(lat: number, lon: number, decimals = 6): string {
  return `${lat.toFixed(decimals)}, ${lon.toFixed(decimals)}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '计算中...';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  return `${(seconds / 3600).toFixed(1)} 小时`;
}

export function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString('zh-CN');
}

// ── API Source 信息 ──
export function getSourceLabel(source: string): string {
  const map: Record<string, string> = {
    amap: '高德地图',
    tianditu: '天地图',
    baidu: '百度地图',
  };
  return map[source] || source;
}

export function getSourceColor(source: string): string {
  const map: Record<string, string> = {
    amap: '#1a73e8',
    tianditu: '#1e8e3e',
    baidu: '#d93025',
  };
  return map[source] || '#888';
}

// ── 剪贴板 ──
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch {
      return false;
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

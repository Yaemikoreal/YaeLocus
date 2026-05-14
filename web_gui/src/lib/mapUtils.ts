// 坐标转换参数（与 Python coords.py 保持一致）
const A = 6378245.0;
const EE = 0.00669342162296594323;

function transformLat(x: number, y: number): number {
  let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  ret += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin(y / 3.0 * Math.PI)) * 2.0 / 3.0;
  ret += (160.0 * Math.sin(y / 12.0 * Math.PI) + 320 * Math.sin(y * Math.PI / 30.0)) * 2.0 / 3.0;
  return ret;
}

function transformLon(x: number, y: number): number {
  let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  ret += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin(x / 3.0 * Math.PI)) * 2.0 / 3.0;
  ret += (150.0 * Math.sin(x / 12.0 * Math.PI) + 300.0 * Math.sin(x / 30.0 * Math.PI)) * 2.0 / 3.0;
  return ret;
}

// GCJ-02 转 WGS-84
export function gcj02ToWgs84(gcjLat: number, gcjLon: number): [number, number] {
  const dLat = transformLat(gcjLon - 105.0, gcjLat - 35.0);
  const dLon = transformLon(gcjLon - 105.0, gcjLat - 35.0);
  const radLat = gcjLat / 180.0 * Math.PI;
  const magic = Math.sin(radLat);
  const sqrtMagic = Math.sqrt(1 - EE * magic * magic);
  const dLatFinal = (dLat * 180.0) / ((A * (1 - EE)) / (sqrtMagic * (1 - EE * magic * magic)) * Math.PI);
  const dLonFinal = (dLon * 180.0) / (A / sqrtMagic * Math.cos(radLat) * Math.PI);
  return [gcjLat - dLatFinal, gcjLon - dLonFinal];
}

// Haversine 距离计算（返回 km）
export function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// WGS-84 转 GCJ-02（用于在高德地图上显示）
export function wgs84ToGcj02(wgsLat: number, wgsLon: number): [number, number] {
  const dLat = transformLat(wgsLon - 105.0, wgsLat - 35.0);
  const dLon = transformLon(wgsLon - 105.0, wgsLat - 35.0);
  const radLat = wgsLat / 180.0 * Math.PI;
  const magic = Math.sin(radLat);
  const sqrtMagic = Math.sqrt(1 - EE * magic * magic);
  const dLatFinal = (dLat * 180.0) / ((A * (1 - EE)) / (sqrtMagic * (1 - EE * magic * magic)) * Math.PI);
  const dLonFinal = (dLon * 180.0) / (A / sqrtMagic * Math.cos(radLat) * Math.PI);
  return [wgsLat + dLatFinal, wgsLon + dLonFinal];
}
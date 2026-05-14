import { useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import { Route, X } from 'lucide-react';
import { haversineDistance, wgs84ToGcj02 } from '../../lib/mapUtils';
import { API_SOURCES } from '../../lib/constants';
import type { GeocodeResult } from '../../lib/types';
import 'leaflet/dist/leaflet.css';

// 解决 Leaflet 默认图标问题
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// 数据来源颜色映射（与 constants.ts 保持一致）
const sourceColors: Record<string, string> = {
  amap: API_SOURCES.amap.color,
  tianditu: API_SOURCES.tianditu.color,
  baidu: API_SOURCES.baidu.color,
  unknown: '#9E9E9E',
};

interface MapViewProps {
  data?: GeocodeResult[];  // 直接传入数据
  center?: [number, number];
  zoom?: number;
}

export default function MapView({ data = [], center = [35, 105], zoom = 5 }: MapViewProps) {
  const [showPanel, setShowPanel] = useState(false);
  const [mode, setMode] = useState<'two-point' | 'route'>('two-point');

  // 两点测距状态
  const [startPoint, setStartPoint] = useState<GeocodeResult | null>(null);
  const [endPoint, setEndPoint] = useState<GeocodeResult | null>(null);

  // 多点路径状态
  const [routePoints, setRoutePoints] = useState<GeocodeResult[]>([]);

  // 转换数据坐标（WGS-84 -> GCJ-02 用于高德瓦片显示）
  const gcjData = useMemo(() => {
    return data.map(item => {
      // 如果数据已标记为 GCJ-02 则无需转换
      if (item.coordinate_system === 'GCJ-02') {
        return { ...item, gcjLat: item.latitude, gcjLon: item.longitude }
      }
      const [gcjLon, gcjLat] = wgs84ToGcj02(item.longitude, item.latitude)
      return { ...item, gcjLat, gcjLon }
    });
  }, [data]);

  // 计算两点距离
  const distance = startPoint && endPoint
    ? haversineDistance(startPoint.latitude, startPoint.longitude, endPoint.latitude, endPoint.longitude)
    : null;

  // 计算路径总距离
  const routeDistance = useMemo(() => {
    if (routePoints.length < 2) return 0;
    let total = 0;
    for (let i = 1; i < routePoints.length; i++) {
      total += haversineDistance(
        routePoints[i - 1].latitude, routePoints[i - 1].longitude,
        routePoints[i].latitude, routePoints[i].longitude
      );
    }
    return total;
  }, [routePoints]);

  // 清除两点测距
  const clearDistance = () => {
    setStartPoint(null);
    setEndPoint(null);
  };

  // 清除路径
  const clearRoute = () => {
    setRoutePoints([]);
  };

  return (
    <div style={{ height: 500, position: 'relative', borderRadius: 8, overflow: 'hidden', border: '1px solid #e0e0e0' }}>
      {/* 测距面板开关按钮 */}
      <button
        onClick={() => setShowPanel(!showPanel)}
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 1000,
          width: 40,
          height: 40,
          borderRadius: 8,
          background: showPanel ? '#4a90d9' : 'white',
          border: '1px solid #dee2e6',
          boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s',
        }}
        title="距离测算"
      >
        {showPanel ? <X size={18} color="white" /> : <Route size={18} color="#4a90d9" />}
      </button>

      {/* 测距面板 */}
      {showPanel && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            right: 55,
            zIndex: 1000,
            background: 'white',
            padding: 12,
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            minWidth: 200,
            maxWidth: 280,
            fontSize: 13,
          }}
        >
          {/* 模式切换 */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
            <button
              onClick={() => setMode('two-point')}
              style={{
                flex: 1,
                padding: '4px 8px',
                fontSize: 12,
                background: mode === 'two-point' ? '#4a90d9' : '#f8f9fa',
                color: mode === 'two-point' ? 'white' : '#333',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            >
              两点测距
            </button>
            <button
              onClick={() => setMode('route')}
              style={{
                flex: 1,
                padding: '4px 8px',
                fontSize: 12,
                background: mode === 'route' ? '#4a90d9' : '#f8f9fa',
                color: mode === 'route' ? 'white' : '#333',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            >
              多点路径
            </button>
          </div>

          {/* 两点测距面板 */}
          {mode === 'two-point' && (
            <div>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
                点击标记点选择起点和终点
              </div>
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2ecc71' }} />
                  <span style={{ color: '#666' }}>起点:</span>
                  <span style={{ color: '#2ecc71', fontWeight: 500 }}>
                    {startPoint?.original_address?.slice(0, 15) || '未选择'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#e74c3c' }} />
                  <span style={{ color: '#666' }}>终点:</span>
                  <span style={{ color: '#e74c3c', fontWeight: 500 }}>
                    {endPoint?.original_address?.slice(0, 15) || '未选择'}
                  </span>
                </div>
              </div>
              {distance !== null && (
                <div
                  style={{
                    padding: 6,
                    background: '#f8f9fa',
                    borderRadius: 4,
                    marginBottom: 8,
                    fontWeight: 500,
                  }}
                >
                  距离: {distance.toFixed(2)} km ({Math.round(distance * 1000)} 米)
                </div>
              )}
              <button
                onClick={clearDistance}
                style={{
                  width: '100%',
                  padding: '4px 8px',
                  fontSize: 12,
                  background: '#f8f9fa',
                  color: '#333',
                  border: '1px solid #dee2e6',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                清除选择
              </button>
            </div>
          )}

          {/* 多点路径面板 */}
          {mode === 'route' && (
            <div>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
                点击标记点的"记录点"按钮添加
              </div>
              <div
                style={{
                  maxHeight: 80,
                  overflow: 'auto',
                  marginBottom: 8,
                  padding: 4,
                  background: '#f8f9fa',
                  borderRadius: 4,
                }}
              >
                {routePoints.length === 0 ? (
                  <div style={{ color: '#999', textAlign: 'center' }}>暂无记录点</div>
                ) : (
                  routePoints.map((p, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 2,
                      }}
                    >
                      <span style={{ color: '#4a90d9', fontWeight: 500 }}>{i + 1}.</span>
                      <span style={{ flex: 1, marginLeft: 4, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {p.original_address?.slice(0, 12)}
                      </span>
                      <button
                        onClick={() => setRoutePoints(routePoints.filter((_, j) => j !== i))}
                        style={{
                          fontSize: 10,
                          padding: '2px 4px',
                          background: '#fce8e6',
                          color: '#d93025',
                          border: 'none',
                          borderRadius: 2,
                          cursor: 'pointer',
                        }}
                      >
                        删除
                      </button>
                    </div>
                  ))
                )}
              </div>
              {routeDistance > 0 && (
                <div
                  style={{
                    padding: 6,
                    background: '#f8f9fa',
                    borderRadius: 4,
                    marginBottom: 8,
                    fontWeight: 500,
                  }}
                >
                  总距离: {routeDistance.toFixed(2)} km ({Math.round(routeDistance * 1000)} 米)
                </div>
              )}
              <button
                onClick={clearRoute}
                style={{
                  width: '100%',
                  padding: '4px 8px',
                  fontSize: 12,
                  background: '#f8f9fa',
                  color: '#333',
                  border: '1px solid #dee2e6',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                清除路径
              </button>
            </div>
          )}

          <div
            style={{
              marginTop: 10,
              fontSize: 10,
              color: '#999',
              borderTop: '1px solid #eee',
              paddingTop: 6,
            }}
          >
            基于 WGS-84 坐标系计算
          </div>
        </div>
      )}

      {/* Leaflet 地图 */}
      <MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }}>
        {/* 高德底图 */}
        <TileLayer
          url="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
          subdomains={['1', '2', '3', '4']}
          attribution="高德地图"
          maxZoom={18}
        />

        {/* 渲染标记点 */}
        {gcjData.map((point, idx) => {
          const color = sourceColors[point.source || 'unknown'];
          return (
            <Marker
              key={idx}
              position={[point.gcjLat, point.gcjLon]}
              icon={L.divIcon({
                className: 'custom-marker',
                html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>`,
                iconSize: [12, 12],
                iconAnchor: [6, 6],
              })}
            >
              <Popup minWidth={200}>
                <div style={{ fontSize: 13 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>
                    {point.original_address?.slice(0, 30) || '未知地址'}
                  </div>
                  <div style={{ color: '#666', fontSize: 11, marginBottom: 4 }}>
                    坐标: {point.latitude.toFixed(4)}, {point.longitude.toFixed(4)}
                  </div>
                  <div style={{ color: '#666', fontSize: 11, marginBottom: 8 }}>
                    来源: {point.source || 'unknown'}
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      onClick={() => setStartPoint(point)}
                      style={{
                        padding: '3px 8px',
                        fontSize: 11,
                        background: '#2ecc71',
                        color: 'white',
                        border: 'none',
                        borderRadius: 4,
                        cursor: 'pointer',
                      }}
                    >
                      设为起点
                    </button>
                    <button
                      onClick={() => setEndPoint(point)}
                      style={{
                        padding: '3px 8px',
                        fontSize: 11,
                        background: '#e74c3c',
                        color: 'white',
                        border: 'none',
                        borderRadius: 4,
                        cursor: 'pointer',
                      }}
                    >
                      设为终点
                    </button>
                    {mode === 'route' && (
                      <button
                        onClick={() => setRoutePoints([...routePoints, point])}
                        style={{
                          padding: '3px 8px',
                          fontSize: 11,
                          background: '#4a90d9',
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          cursor: 'pointer',
                        }}
                      >
                        记录点
                      </button>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* 两点测距连线（使用 GCJ-02 坐标匹配高德底图） */}
        {startPoint && endPoint && (() => {
          const [sLon, sLat] = startPoint.coordinate_system === 'GCJ-02' ? [startPoint.longitude, startPoint.latitude] : wgs84ToGcj02(startPoint.longitude, startPoint.latitude)
          const [eLon, eLat] = endPoint.coordinate_system === 'GCJ-02' ? [endPoint.longitude, endPoint.latitude] : wgs84ToGcj02(endPoint.longitude, endPoint.latitude)
          return (
            <Polyline
              positions={[[sLat, sLon], [eLat, eLon]]}
              color="#FF6600"
              weight={4}
              opacity={0.8}
            />
          )
        })()}

        {/* 起点终点标记 */}
        {startPoint && (() => {
          const [sLon, sLat] = startPoint.coordinate_system === 'GCJ-02' ? [startPoint.longitude, startPoint.latitude] : wgs84ToGcj02(startPoint.longitude, startPoint.latitude)
          return (
            <CircleMarker
              center={[sLat, sLon]}
              radius={10}
              pathOptions={{ color: '#2ecc71', fillColor: '#2ecc71', fillOpacity: 0.9, weight: 3 }}
            >
              <Popup>起点: {startPoint.original_address}</Popup>
            </CircleMarker>
          )
        })()}
        {endPoint && (() => {
          const [eLon, eLat] = endPoint.coordinate_system === 'GCJ-02' ? [endPoint.longitude, endPoint.latitude] : wgs84ToGcj02(endPoint.longitude, endPoint.latitude)
          return (
            <CircleMarker
              center={[eLat, eLon]}
              radius={10}
              pathOptions={{ color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.9, weight: 3 }}
            >
              <Popup>终点: {endPoint.original_address}</Popup>
            </CircleMarker>
          )
        })()}

        {/* 多点路径连线 */}
        {routePoints.length >= 2 && (
          <Polyline
            positions={routePoints.map(p => {
              const [lon, lat] = p.coordinate_system === 'GCJ-02' ? [p.longitude, p.latitude] : wgs84ToGcj02(p.longitude, p.latitude)
              return [lat, lon]
            })}
            color="#4a90d9"
            weight={4}
            opacity={0.8}
          />
        )}

        {/* 路径点标记 */}
        {routePoints.map((point, idx) => {
          const [lon, lat] = point.coordinate_system === 'GCJ-02' ? [point.longitude, point.latitude] : wgs84ToGcj02(point.longitude, point.latitude)
          return (
            <CircleMarker
              key={`route-${idx}`}
              center={[lat, lon]}
              radius={8}
              pathOptions={{ color: '#4a90d9', fillColor: '#4a90d9', fillOpacity: 0.7, weight: 2 }}
            >
              <Popup>{idx + 1}. {point.original_address}</Popup>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  );
}
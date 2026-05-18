import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig, fetchCacheStats } from '../lib/api'
import SingleGeocode from '../components/geocode/SingleGeocode'
import TaskHistory from '../components/geocode/TaskHistory'
import { AlertTriangle, ServerOff, MapPin, Target, Bolt, Server } from 'lucide-react'

export default function GeocodePage() {
  const { data: config, isError } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
    retry: 1,
  })

  const { data: cacheStats } = useQuery({
    queryKey: ['cacheStats'],
    queryFn: ({ signal }) => fetchCacheStats(signal),
    refetchInterval: 30_000,
  })

  const hasApiKey = (config?.apis?.length ?? 0) > 0

  return (
    <div className="page">
      {isError && (
        <div className="alert alert-error">
          <ServerOff size={16} />
          无法连接到 API 服务器，请确认已启动 yaelocus serve
        </div>
      )}

      {!isError && !hasApiKey && (
        <div className="alert alert-warning">
          <AlertTriangle size={16} />
          尚未配置 API 密钥，请先前往
          <a href="/config" style={{ color: '#ff9d4d', fontWeight: 600, marginLeft: 4 }}>
            配置页面
          </a>
          设置后再使用地理编码功能
        </div>
      )}

      <SingleGeocode disabled={!hasApiKey} />

      <div className="geocode-modes">
        <span className="mode-btn active">
          <i className="fa-solid fa-location-dot" /> 正向编码
        </span>
        <Link to="/reverse" className="mode-btn">
          <i className="fa-solid fa-location-crosshairs" /> 逆地理编码
        </Link>
        <Link to="/convert" className="mode-btn">
          <i className="fa-solid fa-arrows-rotate" /> 坐标转换
        </Link>
      </div>

      <div className="grid-4" style={{ marginTop: 24 }}>
        <div className="stat-card">
          <div className="stat-icon orange"><MapPin size={16} /></div>
          <div className="stat-value">{cacheStats?.total_entries?.toLocaleString() ?? '-'}</div>
          <div className="stat-label">缓存条目</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green"><Target size={16} /></div>
          <div className="stat-value">{cacheStats ? `${cacheStats.hit_rate.toFixed(1)}%` : '-'}</div>
          <div className="stat-label">缓存命中率</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon amber"><Bolt size={16} /></div>
          <div className="stat-value">{cacheStats?.hits?.toLocaleString() ?? '-'}</div>
          <div className="stat-label">命中次数</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue"><Server size={16} /></div>
          <div className="stat-value">{config?.apis?.length ?? 0}</div>
          <div className="stat-label">API 已配置</div>
        </div>
      </div>

      <div style={{ marginTop: 40 }}>
        <TaskHistory />
      </div>
    </div>
  )
}

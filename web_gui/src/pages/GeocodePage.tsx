import { useState } from 'react'
import SingleGeocode from '../components/geocode/SingleGeocode'
import BatchGeocode from '../components/geocode/BatchGeocode'
import ReverseGeocode from '../components/geocode/ReverseGeocode'
import CoordConvert from '../components/geocode/CoordConvert'
import TaskHistory from '../components/geocode/TaskHistory'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../lib/api'
import { AlertTriangle, ServerOff } from 'lucide-react'

export default function GeocodePage() {
  const [tab, setTab] = useState<'single' | 'batch' | 'reverse' | 'convert'>('single')

  const { data: config, isError } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
    retry: 1,
  })

  const hasApiKey = (config?.apis?.length ?? 0) > 0

  const tabs = [
    { key: 'single' as const, label: '单地址编码' },
    { key: 'batch' as const, label: '批量编码' },
    { key: 'reverse' as const, label: '逆地理编码' },
    { key: 'convert' as const, label: '坐标转换' },
  ]

  return (
    <div>
      <h1
        style={{
          fontSize: 36,
          fontWeight: 600,
          color: 'rgba(20,20,19,0.88)',
          lineHeight: 1.3,
          marginBottom: 8,
        }}
      >
        地理编码
      </h1>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 16, marginBottom: 32 }}>
        将地址转换为经纬度坐标，支持批量处理和多种坐标系统
      </p>

      {isError && (
        <div
          style={{
            background: '#fce8e6',
            border: '1px solid #d93025',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 24,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 14,
            color: '#d93025',
          }}
        >
          <ServerOff size={16} />
          无法连接到 API 服务器，请确认已启动 yaelocus serve
        </div>
      )}

      {!isError && !hasApiKey && (
        <div
          style={{
            background: '#fef3c7',
            border: '1px solid #f59e0b',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 24,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 14,
            color: '#92400e',
          }}
        >
          <AlertTriangle size={16} />
          尚未配置 API 密钥，请先前往
          <a href="/config" style={{ color: '#ff9d4d', fontWeight: 600 }}>
            配置页面
          </a>
          设置后再使用地理编码功能
        </div>
      )}

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          marginBottom: 24,
          borderBottom: '1px solid #eae8e7',
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: tab === t.key ? 600 : 400,
              color: tab === t.key ? '#ff9d4d' : '#6b6b6b',
              background: 'none',
              border: 'none',
              borderBottom: tab === t.key ? '2px solid #ff9d4d' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'single' && <SingleGeocode disabled={!hasApiKey} />}
      {tab === 'batch' && <BatchGeocode disabled={!hasApiKey} />}
      {tab === 'reverse' && <ReverseGeocode disabled={!hasApiKey} />}
      {tab === 'convert' && <CoordConvert />}

      {/* Task History */}
      <div style={{ marginTop: 48 }}>
        <TaskHistory />
      </div>
    </div>
  )
}

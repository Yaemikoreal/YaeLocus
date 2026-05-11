import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../lib/api'
import APIKeyForm from '../components/config/APIKeyForm'
import CachePanel from '../components/config/CachePanel'
import { Settings, Database, Activity, Key } from 'lucide-react'

export default function ConfigPage() {
  const [tab, setTab] = useState<'keys' | 'cache'>('keys')

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
  })

  return (
    <div>
      <h1 style={{ fontSize: 36, fontWeight: 600, color: 'rgba(20,20,19,0.88)', lineHeight: 1.3, marginBottom: 8 }}>
        配置
      </h1>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 16, marginBottom: 32 }}>
        管理 API 密钥、AI 设置和缓存数据
      </p>

      {/* Status overview */}
      {config && (
        <div style={{
          background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: '16px 20px',
          marginBottom: 24, display: 'flex', gap: 32, flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Key size={16} style={{ color: (config.apis?.length ?? 0) > 0 ? '#1e8e3e' : '#d93025' }} />
            <span style={{ fontSize: 14, color: '#6b6b6b' }}>
              API: {(config.apis?.length ?? 0) > 0 ? config.apis.join(', ') : '未配置'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Activity size={16} style={{ color: config.ai_enabled ? '#1e8e3e' : '#d93025' }} />
            <span style={{ fontSize: 14, color: '#6b6b6b' }}>
              AI: {config.ai_enabled ? `${config.ai_provider} (已开启)` : '未开启'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={16} style={{ color: '#1a73e8' }} />
            <span style={{ fontSize: 14, color: '#6b6b6b' }}>
              缓存: {config.cache?.total_entries ?? 0} 条
            </span>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid #eae8e7' }}>
        <button
          onClick={() => setTab('keys')}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: tab === 'keys' ? 600 : 400,
            color: tab === 'keys' ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
            borderBottom: tab === 'keys' ? '2px solid #ff9d4d' : '2px solid transparent',
            cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Settings size={16} /> API 密钥
        </button>
        <button
          onClick={() => setTab('cache')}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: tab === 'cache' ? 600 : 400,
            color: tab === 'cache' ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
            borderBottom: tab === 'cache' ? '2px solid #ff9d4d' : '2px solid transparent',
            cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Database size={16} /> 缓存管理
        </button>
      </div>

      {tab === 'keys' && <APIKeyForm />}
      {tab === 'cache' && <CachePanel />}
    </div>
  )
}

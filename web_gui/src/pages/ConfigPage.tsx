import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../lib/api'
import APIKeyForm from '../components/config/APIKeyForm'
import { Database, Activity, Key, ServerOff, Route, Zap } from 'lucide-react'

export default function ConfigPage() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
    retry: 1,
  })

  const apiUsage = config?.api_usage

  return (
    <div className="page">
      {isLoading && (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>正在连接 API 服务器...</div>
      )}

      {isError && (
        <div className="alert alert-error">
          <ServerOff size={20} />
          <span>无法连接到 API 服务器，请确认已执行 yaelocus serve 并检查端口</span>
        </div>
      )}

      {config && (
        <div className="status-overview">
          <div className="status-item">
            <Key size={16} style={{ color: (config.apis?.length ?? 0) > 0 ? 'var(--success)' : 'var(--error)' }} />
            <span>API: {(config.apis?.length ?? 0) > 0 ? config.apis.join(', ') : '未配置'}</span>
          </div>
          <div className="status-item">
            <Activity size={16} style={{ color: config.ai_enabled ? 'var(--success)' : 'var(--error)' }} />
            <span>AI: {config.ai_enabled ? `${config.ai_provider} (已开启)` : '未开启'}</span>
          </div>
          <div className="status-item">
            <Database size={16} style={{ color: 'var(--info)' }} />
            <span>缓存: {config.cache?.total_entries ?? 0} 条 (命中率 {config.cache?.hit_rate?.toFixed(1) ?? 0}%)</span>
          </div>
          <div className="status-item">
            <Route size={16} style={{ color: 'var(--color-primary)' }} />
            <span>路线: {config.routing_mode === 'ai' ? 'AI 模式' : 'API 模式'}</span>
          </div>
          {apiUsage && Object.entries(apiUsage).map(([name, usage]: [string, any]) => (
            <div className="status-item" key={name}>
              <Zap size={14} style={{ color: (usage.remaining ?? 0) > 0 ? 'var(--success)' : 'var(--warning)' }} />
              <span style={{ fontSize: 12 }}>{name}: {usage.call_count ?? 0}/{usage.daily_limit ?? 0} ({usage.remaining ?? 0} 剩余)</span>
            </div>
          ))}
        </div>
      )}

      <APIKeyForm />
    </div>
  )
}

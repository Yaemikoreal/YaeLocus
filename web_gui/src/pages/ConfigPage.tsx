import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../lib/api'
import APIKeyForm from '../components/config/APIKeyForm'
import { Database, Activity, ServerOff, Route, Zap, Wifi, WifiOff } from 'lucide-react'

export default function ConfigPage() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
    retry: 1,
  })

  const apiUsage = config?.api_usage
  const apisOk = config?.apis?.length ?? 0

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
          <div className="status-overview-title">
            <Activity size={15} />
            API 状态
          </div>
          <div className="status-cards">
            <div className="status-card">
              <div className="status-card-icon" style={{ color: apisOk > 0 ? 'var(--success)' : 'var(--error)' }}>
                {apisOk > 0 ? <Wifi size={18} /> : <WifiOff size={18} />}
              </div>
              <div className="status-card-info">
                <div className="status-card-label">API 服务</div>
                <div className="status-card-value">{apisOk > 0 ? config.apis.join(', ') : '未配置'}</div>
              </div>
            </div>
            <div className="status-card">
              <div className="status-card-icon" style={{ color: config.ai_enabled ? 'var(--success)' : 'var(--text-muted)' }}>
                <Activity size={18} />
              </div>
              <div className="status-card-info">
                <div className="status-card-label">AI 模型</div>
                <div className="status-card-value">{config.ai_enabled ? `${config.ai_provider} (已开启)` : '未开启'}</div>
              </div>
            </div>
            <div className="status-card">
              <div className="status-card-icon" style={{ color: 'var(--info)' }}>
                <Database size={18} />
              </div>
              <div className="status-card-info">
                <div className="status-card-label">缓存</div>
                <div className="status-card-value">{config.cache?.total_entries ?? 0} 条 (命中率 {config.cache?.hit_rate?.toFixed(1) ?? 0}%)</div>
              </div>
            </div>
            <div className="status-card">
              <div className="status-card-icon" style={{ color: 'var(--color-primary)' }}>
                <Route size={18} />
              </div>
              <div className="status-card-info">
                <div className="status-card-label">路线模式</div>
                <div className="status-card-value">{config.routing_mode === 'ai' ? 'AI 模式' : 'API 模式'}</div>
              </div>
            </div>
            {apiUsage && Object.entries(apiUsage).map(([name, usage]: [string, any]) => (
              <div className="status-card" key={name}>
                <div className="status-card-icon" style={{ color: (usage.remaining ?? 0) > 0 ? 'var(--success)' : 'var(--warning)' }}>
                  <Zap size={18} />
                </div>
                <div className="status-card-info">
                  <div className="status-card-label">{name} 配额</div>
                  <div className="status-card-value">{usage.call_count ?? 0}/{usage.daily_limit ?? 0} ({usage.remaining ?? 0} 剩余)</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <APIKeyForm />
    </div>
  )
}

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchConfig, saveConfig, testAPIKeys } from '../../lib/api'
import type { ConfigTestResponse } from '../../lib/types'
import { Loader2, Check, X, Save, Plug, Route } from 'lucide-react'
import { toast } from 'sonner'
import { AI_PROVIDERS } from '../../lib/constants'

export default function APIKeyForm() {
  const queryClient = useQueryClient()

  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
  })

  const [amapKey, setAmapKey] = useState('')
  const [baiduAk, setBaiduAk] = useState('')
  const [tiandituTk, setTiandituTk] = useState('')
  const [aiEnabledOverride, setAiEnabledOverride] = useState<string | null>(null)
  const [aiProviderOverride, setAiProviderOverride] = useState<string | null>(null)
  const [aiModel, setAiModel] = useState('')
  const [deepseekKey, setDeepseekKey] = useState('')
  const [qwenKey, setQwenKey] = useState('')
  const [glmKey, setGlmKey] = useState('')
  const [moonshotKey, setMoonshotKey] = useState('')
  const [routingModeOverride, setRoutingModeOverride] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<ConfigTestResponse>({})

  const aiEnabled = aiEnabledOverride ?? (config?.ai_enabled ? 'true' : 'false')
  const aiProvider = aiProviderOverride ?? (config?.ai_provider || 'deepseek')
  const routingMode = routingModeOverride ?? (config?.routing_mode || 'ai')

  const saveMutation = useMutation({
    mutationFn: () => saveConfig({
      amap_key: amapKey,
      baidu_ak: baiduAk,
      tianditu_tk: tiandituTk,
      ai_enabled: aiEnabled,
      ai_provider: aiProvider,
      ai_model: aiModel,
      deepseek_key: deepseekKey,
      qwen_key: qwenKey,
      glm_key: glmKey,
      moonshot_key: moonshotKey,
      routing_mode: routingMode,
    }),
    onSuccess: (data) => {
      toast.success(data.message || '配置已保存')
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const handleTest = async (provider: keyof ConfigTestResponse) => {
    setTestResults((prev) => ({ ...prev, [provider]: null }))
    try {
      const keys: Record<string, string> = {}
      if (provider === 'amap') keys.amap_key = amapKey
      if (provider === 'baidu') keys.baidu_ak = baiduAk
      if (provider === 'tianditu') keys.tianditu_tk = tiandituTk
      const data = await testAPIKeys(keys)
      setTestResults((prev) => ({ ...prev, ...data }))
    } catch {
      setTestResults((prev) => ({ ...prev, [provider]: false }))
      toast.error('测试失败')
    }
  }

  const testBadge = (key: keyof ConfigTestResponse) => {
    if (testResults[key] === undefined) return null
    if (testResults[key] === null) return <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>测试中...</span>
    if (testResults[key]) return <span style={{ fontSize: 11, color: 'var(--success)', display: 'inline-flex', alignItems: 'center', gap: 3 }}><Check size={13} /> 有效</span>
    return <span style={{ fontSize: 11, color: 'var(--error)', display: 'inline-flex', alignItems: 'center', gap: 3 }}><X size={13} /> 无效</span>
  }

  if (isLoading) {
    return <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</div>
  }

  return (
    <>
      <div className="config-card">
        <div className="config-card-header">
          <div className="config-card-title"><i className="fa-solid fa-key" /> API 密钥</div>
        </div>

        <div className="api-key-row">
          <div className="api-key-name"><i className="fa-solid fa-map-location-dot" style={{ color: 'var(--color-primary)' }} /> 高德</div>
          <input type="password" className="api-key-input" value={amapKey} onChange={(e) => setAmapKey(e.target.value)} placeholder={config?.amap_key_masked || (config?.amap_key_configured ? '已配置，留空则不修改' : '32位 Key')} />
          <div className="api-key-status" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <i className={config?.amap_key_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.amap_key_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 14 }} />
            <button className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', fontSize: 11 }} onClick={() => handleTest('amap')} title="测试高德 Key"><Plug size={12} /> 测试</button>
            {testBadge('amap')}
          </div>
        </div>

        <div className="api-key-row">
          <div className="api-key-name"><i className="fa-solid fa-globe" style={{ color: 'var(--success)' }} /> 天地图</div>
          <input type="password" className="api-key-input" value={tiandituTk} onChange={(e) => setTiandituTk(e.target.value)} placeholder={config?.tianditu_tk_masked || (config?.tianditu_tk_configured ? '已配置，留空则不修改' : '天地图 Key')} />
          <div className="api-key-status" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <i className={config?.tianditu_tk_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.tianditu_tk_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 14 }} />
            <button className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', fontSize: 11 }} onClick={() => handleTest('tianditu')} title="测试天地图 Key"><Plug size={12} /> 测试</button>
            {testBadge('tianditu')}
          </div>
        </div>

        <div className="api-key-row">
          <div className="api-key-name"><i className="fa-solid fa-location-crosshairs" style={{ color: 'var(--info)' }} /> 百度</div>
          <input type="password" className="api-key-input" value={baiduAk} onChange={(e) => setBaiduAk(e.target.value)} placeholder={config?.baidu_ak_masked || (config?.baidu_ak_configured ? '已配置，留空则不修改' : '百度 AK')} />
          <div className="api-key-status" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <i className={config?.baidu_ak_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.baidu_ak_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 14 }} />
            <button className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', fontSize: 11 }} onClick={() => handleTest('baidu')} title="测试百度 Key"><Plug size={12} /> 测试</button>
            {testBadge('baidu')}
          </div>
        </div>
      </div>

      <div className="config-card">
        <div className="config-card-header">
          <div className="config-card-title"><i className="fa-solid fa-robot" /> AI 配置</div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 1, minWidth: 140 }}>
            <label className="form-label">启用 AI</label>
            <select value={aiEnabled} onChange={(e) => setAiEnabledOverride(e.target.value)} className="form-input">
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: 140 }}>
            <label className="form-label">AI 供应商</label>
            <select value={aiProvider} onChange={(e) => setAiProviderOverride(e.target.value)} className="form-input">
              {Object.entries(AI_PROVIDERS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: 140 }}>
            <label className="form-label">AI 模型</label>
            <input type="text" className="form-input" value={aiModel} onChange={(e) => setAiModel(e.target.value)} placeholder={config?.ai_model || '默认'} />
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div className="form-label" style={{ marginBottom: 8, fontSize: 12, color: 'var(--text-muted)' }}>供应商 API Key</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
            <div className="api-key-row" style={{ padding: '6px 8px', borderRadius: 6, background: 'var(--bg-secondary)' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 60 }}>DeepSeek</div>
              <input type="password" className="api-key-input" style={{ flex: 1 }} value={deepseekKey} onChange={(e) => setDeepseekKey(e.target.value)} placeholder={config?.deepseek_key_masked || (config?.deepseek_key_configured ? '已配置' : 'sk-...')} />
              <i className={config?.deepseek_key_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.deepseek_key_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 12 }} />
            </div>
            <div className="api-key-row" style={{ padding: '6px 8px', borderRadius: 6, background: 'var(--bg-secondary)' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 60 }}>通义千问</div>
              <input type="password" className="api-key-input" style={{ flex: 1 }} value={qwenKey} onChange={(e) => setQwenKey(e.target.value)} placeholder={config?.qwen_key_masked || (config?.qwen_key_configured ? '已配置' : 'Key')} />
              <i className={config?.qwen_key_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.qwen_key_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 12 }} />
            </div>
            <div className="api-key-row" style={{ padding: '6px 8px', borderRadius: 6, background: 'var(--bg-secondary)' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 60 }}>智谱 GLM</div>
              <input type="password" className="api-key-input" style={{ flex: 1 }} value={glmKey} onChange={(e) => setGlmKey(e.target.value)} placeholder={config?.glm_key_masked || (config?.glm_key_configured ? '已配置' : 'Key')} />
              <i className={config?.glm_key_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.glm_key_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 12 }} />
            </div>
            <div className="api-key-row" style={{ padding: '6px 8px', borderRadius: 6, background: 'var(--bg-secondary)' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 60 }}>Moonshot</div>
              <input type="password" className="api-key-input" style={{ flex: 1 }} value={moonshotKey} onChange={(e) => setMoonshotKey(e.target.value)} placeholder={config?.moonshot_key_masked || (config?.moonshot_key_configured ? '已配置' : 'Key')} />
              <i className={config?.moonshot_key_configured ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-minus'} style={{ color: config?.moonshot_key_configured ? 'var(--success)' : 'var(--text-faint)', fontSize: 12 }} />
            </div>
          </div>
        </div>
      </div>

      <div className="config-card">
        <div className="config-card-header">
          <div className="config-card-title"><Route size={14} /> 路线规划</div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
            <label className="form-label">路线模式</label>
            <select value={routingMode} onChange={(e) => setRoutingModeOverride(e.target.value)} className="form-input">
              <option value="ai">AI 模式（零成本）</option>
              <option value="api">API 模式（高德/百度付费）</option>
            </select>
          </div>
        </div>
      </div>

      <button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending} className="btn btn-primary">
        {saveMutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={16} />}
        保存配置
      </button>
    </>
  )
}

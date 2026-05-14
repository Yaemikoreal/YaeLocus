import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchConfig, saveConfig, testAPIKeys } from '../../lib/api'
import type { ConfigTestResponse } from '../../lib/types'
import { Loader2, Check, X, Save, FlaskConical } from 'lucide-react'
import { toast } from 'sonner'

export default function APIKeyForm() {
  const queryClient = useQueryClient()

  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
  })

  const [amapKey, setAmapKey] = useState('')
  const [baiduAk, setBaiduAk] = useState('')
  const [tiandituTk, setTiandituTk] = useState('')
  const [aiEnabled, setAiEnabled] = useState('false')
  const [aiProvider, setAiProvider] = useState('deepseek')
  const [deepseekKey, setDeepseekKey] = useState('')
  const [initialized, setInitialized] = useState(false)
  const [testResults, setTestResults] = useState<ConfigTestResponse>({})

  // Track which API keys are already configured (for placeholder display)
  const hasAmapKey = config?.apis?.includes('amap') ?? false
  const hasBaiduKey = config?.apis?.includes('baidu') ?? false
  const hasTiandituKey = config?.apis?.includes('tianditu') ?? false

  useEffect(() => {
    if (config && !initialized) {
      setAiEnabled(config.ai_enabled ? 'true' : 'false')
      setAiProvider(config.ai_provider || 'deepseek')
      setInitialized(true)
    }
  }, [config, initialized])

  const saveMutation = useMutation({
    mutationFn: () => {
      // Only send non-empty values to avoid overwriting stored keys
      return saveConfig({
        amap_key: amapKey,
        baidu_ak: baiduAk,
        tianditu_tk: tiandituTk,
        ai_enabled: aiEnabled,
        ai_provider: aiProvider,
        deepseek_key: deepseekKey,
      })
    },
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

  const statusBadge = (key: keyof ConfigTestResponse) => {
    if (testResults[key] === undefined) return null
    if (testResults[key] === null) return <span style={{ fontSize: 12, color: '#6b6b6b' }}>测试中...</span>
    if (testResults[key]) return <span style={{ fontSize: 12, color: '#1e8e3e', display: 'inline-flex', alignItems: 'center', gap: 4 }}><Check size={14} /> 有效</span>
    return <span style={{ fontSize: 12, color: '#d93025', display: 'inline-flex', alignItems: 'center', gap: 4 }}><X size={14} /> 无效</span>
  }

  if (isLoading) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#888' }}>加载中...</div>
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', fontFamily: 'monospace',
  }

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>API 密钥</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 20 }}>
        至少配置一个地图 API 密钥即可使用。保存后将写入项目 .env 文件
      </p>

      {/* Amap */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>
          高德地图 API Key
          <span style={{ display: 'inline-block', padding: '2px 6px', borderRadius: 4, fontSize: 11, background: '#e6f4ea', color: '#1e8e3e' }}>推荐</span>
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="password" value={amapKey} onChange={(e) => setAmapKey(e.target.value)} placeholder={hasAmapKey ? '已配置，留空则不修改' : '32位 Key'} style={inputStyle} />
          <button onClick={() => handleTest('amap')} style={{ padding: '8px 16px', background: '#e8eaed', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 4 }}>
            <FlaskConical size={14} /> 测试
          </button>
        </div>
        <div style={{ marginTop: 4 }}>{statusBadge('amap')}</div>
      </div>

      {/* Baidu */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>百度地图 AK</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="password" value={baiduAk} onChange={(e) => setBaiduAk(e.target.value)} placeholder={hasBaiduKey ? '已配置，留空则不修改' : '百度 AK'} style={inputStyle} />
          <button onClick={() => handleTest('baidu')} style={{ padding: '8px 16px', background: '#e8eaed', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 4 }}>
            <FlaskConical size={14} /> 测试
          </button>
        </div>
        <div style={{ marginTop: 4 }}>{statusBadge('baidu')}</div>
      </div>

      {/* Tianditu */}
      <div style={{ marginBottom: 24 }}>
        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>天地图 TK</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="password" value={tiandituTk} onChange={(e) => setTiandituTk(e.target.value)} placeholder={hasTiandituKey ? '已配置，留空则不修改' : '天地图 Key'} style={inputStyle} />
          <button onClick={() => handleTest('tianditu')} style={{ padding: '8px 16px', background: '#e8eaed', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 4 }}>
            <FlaskConical size={14} /> 测试
          </button>
        </div>
        <div style={{ marginTop: 4 }}>{statusBadge('tianditu')}</div>
      </div>

      <div style={{ borderTop: '1px solid #eae8e7', paddingTop: 20, marginBottom: 20 }}>
        <h4 style={{ fontSize: 16, fontWeight: 600, color: '#555', marginBottom: 12 }}>AI 配置 (可选)</h4>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>启用 AI</label>
            <select value={aiEnabled} onChange={(e) => setAiEnabled(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', fontFamily: 'inherit' }}>
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>AI 供应商</label>
            <select value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', fontFamily: 'inherit' }}>
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">通义千问</option>
              <option value="glm">智谱 GLM</option>
              <option value="moonshot">Moonshot</option>
            </select>
          </div>
          <div style={{ flex: 2, minWidth: 200 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>API Key</label>
            <input type="password" value={deepseekKey} onChange={(e) => setDeepseekKey(e.target.value)} placeholder="sk-..." style={inputStyle} />
          </div>
        </div>
      </div>

      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 24px',
          background: '#ff9d4d', color: 'rgba(20,20,19,0.88)', border: 'none', borderRadius: 10,
          fontSize: 14, fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s',
        }}
      >
        {saveMutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={16} />}
        保存配置
      </button>
    </div>
  )
}

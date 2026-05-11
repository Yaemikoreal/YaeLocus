import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { executeCommand } from '../../lib/api'
import { Loader2, Route, AlertTriangle } from 'lucide-react'

export default function RoutePlan() {
  const [filePath, setFilePath] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: (cmd: string) => executeCommand(cmd),
    onSuccess: (data) => {
      if (data.success) {
        setResult(data.stdout)
        setError('')
      } else {
        setError(data.stderr || '规划失败')
        setResult('')
      }
    },
    onError: (e: Error) => {
      setError(e.message)
      setResult('')
    },
  })

  const handleRoute = () => {
    if (!filePath.trim()) return
    setResult('')
    setError('')
    mutation.mutate(`ai route -i "${filePath.trim()}"`)
  }

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>路线规划</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        AI 智能路线规划，根据地址分布推荐最优拜访路线
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <input
          type="text"
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="输入 CSV 文件路径，如: output/csv/结果.csv"
          disabled={mutation.isPending}
          style={{
            flex: 1, padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8,
            fontSize: 14, outline: 'none', fontFamily: 'monospace',
          }}
        />
        <button
          onClick={handleRoute}
          disabled={mutation.isPending || !filePath.trim()}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '10px 24px',
            background: '#ff9d4d', color: 'rgba(20,20,19,0.88)', border: 'none', borderRadius: 10,
            fontSize: 14, fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s', whiteSpace: 'nowrap',
          }}
        >
          {mutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Route size={16} />}
          规划
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {result && (
        <div style={{ padding: 16, background: '#fff', border: '1px solid #eae8e7', borderRadius: 8, fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap', maxHeight: 500, overflow: 'auto' }}>
          {result}
        </div>
      )}
    </div>
  )
}

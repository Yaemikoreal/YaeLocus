import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { executeCommand } from '../../lib/api'
import { Loader2, BarChart3, AlertTriangle } from 'lucide-react'

export default function AnalysisResult() {
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
        setError(data.stderr || '分析失败')
        setResult('')
      }
    },
    onError: (e: Error) => {
      setError(e.message)
      setResult('')
    },
  })

  const handleAnalyze = () => {
    if (!filePath.trim()) return
    setResult('')
    setError('')
    mutation.mutate(`ai analyze -i "${filePath.trim()}"`)
  }

  return (
    <div className="content-block">
      <h3>数据分析</h3>
      <p className="desc">对地理编码结果进行 AI 分析，获取数据洞察和统计信息</p>

      <div className="form-row">
        <div className="form-group" style={{ flex: 1 }}>
          <input
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="输入 CSV 文件路径，如: output/csv/结果.csv"
            disabled={mutation.isPending}
            className="form-input"
            style={{ fontFamily: 'var(--font-mono)' }}
          />
        </div>
        <button
          onClick={handleAnalyze}
          disabled={mutation.isPending || !filePath.trim()}
          className="btn btn-primary"
        >
          {mutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <BarChart3 size={16} />}
          分析
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {result && (
        <div className="card" style={{ whiteSpace: 'pre-wrap', maxHeight: 500, overflow: 'auto', fontSize: 14, lineHeight: 1.6 }}>
          {result}
        </div>
      )}
    </div>
  )
}

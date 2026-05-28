import { useState, useRef, useCallback } from 'react'
import { aiAnalyzeStream } from '../../lib/api'
import { BarChart3, AlertTriangle, Square } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function AnalysisResult() {
  const [filePath, setFilePath] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const handleAnalyze = useCallback(() => {
    if (!filePath.trim()) return
    setResult('')
    setError('')
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    let fullText = ''
    let lastRenderTime = 0

    aiAnalyzeStream(
      filePath.trim(),
      (token) => {
        fullText += token
        const now = Date.now()
        if (now - lastRenderTime >= 50) {
          lastRenderTime = now
          setResult(fullText)
        }
      },
      () => {
        setResult(fullText)
        setStreaming(false)
      },
      (err) => {
        setError(err)
        setResult(fullText || '')
        setStreaming(false)
      },
      controller.signal
    )
  }, [filePath])

  const handleCancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

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
            disabled={streaming}
            className="form-input"
            style={{ fontFamily: 'var(--font-mono)' }}
          />
        </div>
        {streaming ? (
          <button onClick={handleCancel} className="btn btn-secondary" title="停止">
            <Square size={16} /> 停止
          </button>
        ) : (
          <button
            onClick={handleAnalyze}
            disabled={streaming || !filePath.trim()}
            className="btn btn-primary"
          >
            <BarChart3 size={16} /> 分析
          </button>
        )}
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {result && (
        <div className="card markdown-body" style={{ maxHeight: 500, overflow: 'auto', fontSize: 14, lineHeight: 1.6 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {result}
          </ReactMarkdown>
          {streaming && <span className="typing-indicator"><span></span><span></span><span></span></span>}
        </div>
      )}
    </div>
  )
}
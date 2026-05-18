import { useState, useRef, useCallback } from 'react'
import { batchGeocodeStream } from '../../lib/api'
import { validateFile } from '../../lib/utils'
import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import ProgressBar from './ProgressBar'
import { Upload, Loader2, X, FileText } from 'lucide-react'

interface Props {
  disabled?: boolean
}

interface ProgressState {
  total: number
  current: number
  success: number
}

export default function BatchGeocode({ disabled }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [column, setColumn] = useState('地址')
  const [workers, setWorkers] = useState('auto')
  const [city, setCity] = useState('')
  const [status, setStatus] = useState<'idle' | 'uploading' | 'running' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')
  const [progress, setProgress] = useState<ProgressState>({ total: 0, current: 0, success: 0 })
  const [results, setResults] = useState<GeocodeResultType[]>([])
  const [fileError, setFileError] = useState('')
  const [startTime, setStartTime] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  const handleFileSelect = useCallback((f: File | null) => {
    setFileError('')
    if (!f) { setFile(null); return }
    const err = validateFile(f)
    if (err) { setFileError(err); setFile(null); return }
    setFile(f)
  }, [])

  const handleStart = () => {
    if (!file) return
    setStatus('uploading')
    setError('')
    setResults([])
    setProgress({ total: 0, current: 0, success: 0 })
    const st = Date.now()
    setStartTime(st)

    const controller = new AbortController()
    abortRef.current = controller

    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      controller.abort()
      setStatus('error')
      setError('编码超时（10分钟），请重试或减少地址数量')
    }, 600_000)

    batchGeocodeStream(
      file, column, workers, city,
      (evt) => { setStatus('running'); setProgress({ total: evt.total, current: evt.current, success: evt.success }) },
      (res) => { setStatus('running'); setResults((prev) => [...prev, res]) },
      (_taskId, res) => {
        if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null }
        setStatus('done')
        if (res && res.length > 0) setResults(res)
      },
      (err) => {
        if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null }
        setStatus('error')
        setError(err)
      },
      controller.signal
    )
  }

  const handleCancel = () => {
    abortRef.current?.abort()
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setStatus('idle')
  }

  const successCount = results.filter((r) => r.success).length
  const failCount = results.length - successCount

  return (
    <div className="card">
      <div className="card-title"><i className="fa-solid fa-layer-group" /> 批量编码</div>
      <p className="card-desc">上传 Excel 或 CSV 文件，自动批量转换地址为经纬度坐标</p>

      <div
        ref={dropRef}
        onClick={() => document.getElementById('batchFileInput')?.click()}
        onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('dragover') }}
        onDragLeave={(e) => { e.currentTarget.classList.remove('dragover') }}
        onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove('dragover'); handleFileSelect(e.dataTransfer.files[0]) }}
        className="batch-zone"
      >
        <i className="fa-solid fa-cloud-arrow-up" />
        <div style={{ fontWeight: 600, fontSize: 15 }}>点击选择文件 或 拖拽到此处</div>
        <p style={{ color: 'var(--text-tertiary)', marginTop: 8, fontSize: 13 }}>支持 CSV / XLSX / XLS 格式，最大 100MB</p>
      </div>
      <input id="batchFileInput" type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={(e) => handleFileSelect(e.target.files?.[0] || null)} />

      {fileError && (
        <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{fileError}</div>
      )}

      {file && (
        <div className="alert alert-info" style={{ marginTop: 12, marginBottom: 0, display: 'inline-flex', gap: 8 }}>
          <FileText size={14} />
          <span>{file.name} ({file.size > 1024 * 1024 ? (file.size / (1024 * 1024)).toFixed(1) + ' MB' : (file.size / 1024).toFixed(1) + ' KB'})</span>
          <button onClick={() => { setFile(null); setFileError('') }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'inherit', marginLeft: 4 }}>
            <X size={14} />
          </button>
        </div>
      )}

      <div className="form-row" style={{ marginTop: 16 }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">地址列名</label>
          <input type="text" value={column} onChange={(e) => setColumn(e.target.value)} className="form-input" />
        </div>
        <div className="form-group" style={{ width: 160 }}>
          <label className="form-label">线程数</label>
          <select value={workers} onChange={(e) => setWorkers(e.target.value)} className="form-input">
            <option value="auto">auto（自动）</option>
            <option value="1">1（串行）</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="5">5</option>
          </select>
        </div>
        <div className="form-group" style={{ width: 180 }}>
          <label className="form-label">指定地市（可选）</label>
          <input type="text" value={city} onChange={(e) => setCity(e.target.value)} placeholder="如：眉山市" className="form-input" />
        </div>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
        <button onClick={handleStart} disabled={disabled || !file || status === 'running' || status === 'uploading'} className="btn btn-primary">
          {(status === 'running' || status === 'uploading') ? (
            <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Upload size={16} />
          )}
          开始编码
        </button>
        {(status === 'running' || status === 'uploading') && (
          <button onClick={handleCancel} className="btn btn-secondary">取消</button>
        )}
      </div>

      {(status === 'running' || status === 'uploading') && (
        <ProgressBar total={progress.total} current={progress.current} success={progress.success} startTime={startTime} />
      )}

      {status === 'error' && (
        <div className="alert alert-error" style={{ marginTop: 16, marginBottom: 0 }}>{error}</div>
      )}

      {status === 'done' && results.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div className="status-overview" style={{ marginBottom: 12, padding: '10px 14px' }}>
            <span>成功 <strong style={{ color: 'var(--success)' }}>{successCount}</strong></span>
            <span>失败 <strong style={{ color: 'var(--error)' }}>{failCount}</strong></span>
            <span>总计 <strong>{results.length}</strong></span>
          </div>
          <div className="result-list">
            {results.map((r, i) => <GeocodeResultCard key={i} result={r} />)}
          </div>
        </div>
      )}
    </div>
  )
}

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
  const abortRef = useRef<AbortController | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startTimeRef = useRef(0)
  const dropRef = useRef<HTMLDivElement>(null)

  const handleFileSelect = useCallback((f: File | null) => {
    setFileError('')
    if (!f) {
      setFile(null)
      return
    }
    const err = validateFile(f)
    if (err) {
      setFileError(err)
      setFile(null)
      return
    }
    setFile(f)
  }, [])

  const handleStart = () => {
    if (!file) return
    setStatus('uploading')
    setError('')
    setResults([])
    setProgress({ total: 0, current: 0, success: 0 })
    startTimeRef.current = Date.now()

    const controller = new AbortController()
    abortRef.current = controller

    // 10 分钟超时保护，防止 SSE 流挂起
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      controller.abort()
      setStatus('error')
      setError('编码超时（10分钟），请重试或减少地址数量')
    }, 600_000)

    batchGeocodeStream(
      file,
      column,
      workers,
      city,
      (evt) => {
        console.log('[BatchGeocode] onProgress:', { total: evt.total, current: evt.current, success: evt.success })
        setStatus('running')
        setProgress({
          total: evt.total,
          current: evt.current,
          success: evt.success,
        })
      },
      (res) => {
        setStatus('running')
        setResults((prev) => [...prev, res])
      },
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
    <div
      style={{
        background: 'rgba(43,18,0,0.02)',
        borderRadius: 8,
        padding: 28,
        marginBottom: 20,
      }}
    >
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>批量编码</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        上传包含地址列的 CSV / XLSX 文件，自动批量转换为经纬度坐标
      </p>

      {/* Drop zone */}
      <div
        ref={dropRef}
        onClick={() => document.getElementById('batchFileInput')?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          e.currentTarget.style.borderColor = '#ff9d4d'
          e.currentTarget.style.background = 'rgba(255,157,77,0.05)'
        }}
        onDragLeave={(e) => {
          e.currentTarget.style.borderColor = '#ccc'
          e.currentTarget.style.background = 'transparent'
        }}
        onDrop={(e) => {
          e.preventDefault()
          e.currentTarget.style.borderColor = '#ccc'
          e.currentTarget.style.background = 'transparent'
          handleFileSelect(e.dataTransfer.files[0])
        }}
        style={{
          border: '2px dashed #ccc',
          borderRadius: 12,
          padding: 48,
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
      >
        <Upload size={48} style={{ color: '#ccc', marginBottom: 8 }} />
        <div style={{ fontWeight: 600, fontSize: 15 }}>点击选择文件 或 拖拽到此处</div>
        <p style={{ color: '#888', marginTop: 8, fontSize: 14 }}>支持 CSV / XLSX / XLS 格式，最大 100MB</p>
      </div>
      <input
        id="batchFileInput"
        type="file"
        accept=".csv,.xlsx,.xls"
        style={{ display: 'none' }}
        onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
      />

      {fileError && (
        <div style={{ marginTop: 12, padding: '8px 12px', background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 13 }}>
          {fileError}
        </div>
      )}

      {/* File info */}
      {file && (
        <div
          style={{
            marginTop: 12,
            padding: '8px 12px',
            background: '#e8f0fe',
            borderRadius: 8,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
            color: '#1a73e8',
          }}
        >
          <FileText size={14} />
          {file.name} ({file.size > 1024 * 1024 ? (file.size / (1024 * 1024)).toFixed(1) + ' MB' : (file.size / 1024).toFixed(1) + ' KB'})
          <button
            onClick={() => { setFile(null); setFileError('') }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: '#1a73e8' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Options */}
      <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>
            地址列名
          </label>
          <input
            type="text"
            value={column}
            onChange={(e) => setColumn(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 14px',
              border: '1.5px solid #eae8e7',
              borderRadius: 8,
              fontSize: 14,
              outline: 'none',
              fontFamily: 'inherit',
            }}
          />
        </div>
        <div style={{ width: 180 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>
            线程数
          </label>
          <select
            value={workers}
            onChange={(e) => setWorkers(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 14px',
              border: '1.5px solid #eae8e7',
              borderRadius: 8,
              fontSize: 14,
              outline: 'none',
              background: '#fff',
              fontFamily: 'inherit',
            }}
          >
            <option value="auto">auto（自动）</option>
            <option value="1">1（串行）</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="5">5</option>
          </select>
        </div>
        <div style={{ width: 180 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>
            指定地市（可选）
          </label>
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="如：眉山市"
            style={{
              width: '100%',
              padding: '10px 14px',
              border: '1.5px solid #eae8e7',
              borderRadius: 8,
              fontSize: 14,
              outline: 'none',
              fontFamily: 'inherit',
            }}
          />
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
        <button
          onClick={handleStart}
          disabled={disabled || !file || status === 'running' || status === 'uploading'}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 24px',
            background: disabled || !file ? '#ccc' : '#ff9d4d',
            color: 'rgba(20,20,19,0.88)',
            border: 'none',
            borderRadius: 10,
            fontSize: 14,
            fontWeight: 600,
            cursor: disabled || !file ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {(status === 'running' || status === 'uploading') ? (
            <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Upload size={16} />
          )}
          开始编码
        </button>
        {(status === 'running' || status === 'uploading') && (
          <button
            onClick={handleCancel}
            style={{
              padding: '10px 24px',
              background: '#e8eaed',
              color: '#333',
              border: 'none',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            取消
          </button>
        )}
      </div>

      {/* Progress */}
      {(status === 'running' || status === 'uploading') && (
        <ProgressBar
          total={progress.total}
          current={progress.current}
          success={progress.success}
          startTime={startTimeRef.current}
        />
      )}

      {/* Error */}
      {status === 'error' && (
        <div
          style={{
            marginTop: 16,
            padding: '12px 16px',
            background: '#fce8e6',
            borderRadius: 8,
            color: '#d93025',
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {status === 'done' && results.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div
            style={{
              marginBottom: 12,
              padding: '12px 16px',
              background: '#f5f7fa',
              borderRadius: 8,
              fontSize: 14,
              display: 'flex',
              gap: 16,
            }}
          >
            <span>
              成功 <strong style={{ color: '#1e8e3e' }}>{successCount}</strong>
            </span>
            <span>
              失败 <strong style={{ color: '#d93025' }}>{failCount}</strong>
            </span>
            <span>
              总计 <strong>{results.length}</strong>
            </span>
          </div>
          <div
            style={{
              border: '1px solid #eae8e7',
              borderRadius: 8,
              maxHeight: 500,
              overflow: 'auto',
            }}
          >
            {results.map((r, i) => (
              <GeocodeResultCard key={i} result={r} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

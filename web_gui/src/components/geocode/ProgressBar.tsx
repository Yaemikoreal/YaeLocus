import { useState, useEffect } from 'react'
import { formatDuration } from '../../lib/utils'

interface Props {
  total: number
  current: number
  success: number
  startTime: number
}

export default function ProgressBar({ total, current, success, startTime }: Props) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const safeTotal = total || 0
  const safeCurrent = current || 0
  const safeSuccess = success || 0
  const pct = safeTotal > 0 ? Math.round((safeCurrent / safeTotal) * 100) : 0
  const elapsed = startTime > 0 ? (now - startTime) / 1000 : 0
  const speed = elapsed > 0 ? safeCurrent / elapsed : 0
  const remaining = speed > 0 ? (safeTotal - safeCurrent) / speed : 0

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 14, color: 'var(--text)' }}>
        <span>已处理 {safeCurrent}/{safeTotal}</span>
        <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--color-primary-deep)' }}>{pct}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-info">
        <span>成功: {safeSuccess}</span>
        <span>速度: {speed.toFixed(1)} 条/秒 · 预计剩余: {formatDuration(remaining)}</span>
      </div>
    </div>
  )
}

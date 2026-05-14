import { formatDuration } from '../../lib/utils'

interface Props {
  total: number
  current: number
  success: number
  startTime: number
}

export default function ProgressBar({ total, current, success, startTime }: Props) {
  const safeTotal = total || 0
  const safeCurrent = current || 0
  const safeSuccess = success || 0
  const pct = safeTotal > 0 ? Math.round((safeCurrent / safeTotal) * 100) : 0
  const elapsed = (Date.now() - startTime) / 1000
  const speed = elapsed > 0 ? safeCurrent / elapsed : 0
  const remaining = speed > 0 ? (safeTotal - safeCurrent) / speed : 0

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 14 }}>
        <span>
          已处理 {safeCurrent}/{safeTotal}
        </span>
        <span style={{ fontWeight: 600 }}>{pct}%</span>
      </div>
      <div
        style={{
          height: 8,
          background: '#e8eaed',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            background: 'linear-gradient(90deg, #ff9d4d, #e77c29)',
            borderRadius: 4,
            width: `${pct}%`,
            transition: 'width 0.3s',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 4,
          fontSize: 12,
          color: '#888',
        }}
      >
        <span>成功: {safeSuccess}</span>
        <span>
          速度: {speed.toFixed(1)} 条/秒 · 预计剩余: {formatDuration(remaining)}
        </span>
      </div>
    </div>
  )
}

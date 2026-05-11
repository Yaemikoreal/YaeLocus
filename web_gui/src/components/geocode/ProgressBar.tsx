import { formatDuration } from '../../lib/utils'

interface Props {
  progress: number
  total: number
  current: number
  success: number
  startTime: number
}

export default function ProgressBar({ progress, total, current, success, startTime }: Props) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0
  const elapsed = (Date.now() - startTime) / 1000
  const speed = elapsed > 0 ? current / elapsed : 0
  const remaining = speed > 0 ? (total - current) / speed : 0

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 14 }}>
        <span>
          已处理 {progress}/{total}
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
        <span>成功: {success}</span>
        <span>
          速度: {speed.toFixed(1)} 条/秒 · 预计剩余: {formatDuration(remaining)}
        </span>
      </div>
    </div>
  )
}

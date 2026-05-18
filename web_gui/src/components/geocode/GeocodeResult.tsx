import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import { getSourceLabel, getSourceColor } from '../../lib/utils'
import { MapPin, Copy, Check } from 'lucide-react'
import { useState } from 'react'

export default function GeocodeResult({ result }: { result: GeocodeResultType }) {
  const [copied, setCopied] = useState(false)

  if (!result.success) {
    return (
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-light)', fontSize: 14 }}>
        <span style={{ fontWeight: 600 }}>{result.original_address}</span>
        <span className="badge badge-error" style={{ marginLeft: 8 }}>失败</span>
        {result.warning && (
          <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 4 }}>{result.warning}</div>
        )}
      </div>
    )
  }

  const coordStr = `${result.latitude.toFixed(6)}, ${result.longitude.toFixed(6)}`
  const sourceColor = getSourceColor(result.source || 'unknown')
  const confidenceTotal = result.confidence?.total ?? null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(coordStr)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div
      className="result-row"
      style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-light)',
        fontSize: 14,
        transition: 'background var(--transition-fast)',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>{result.original_address}</div>
          {result.formatted_address && result.formatted_address !== result.original_address && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 4 }}>
              标准化: {result.formatted_address}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--success)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>
              <MapPin size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
              {coordStr}
            </span>
            <span
              className="badge"
              style={{ background: `${sourceColor}15`, color: sourceColor, padding: '1px 6px', fontSize: 11 }}
            >
              {getSourceLabel(result.source || 'unknown')}
            </span>
            {result.coordinate_system && (
              <span className="badge" style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)', padding: '1px 6px', fontSize: 11 }}>
                {result.coordinate_system}
              </span>
            )}
          </div>
          {result.province && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>
              {[result.province, result.city, result.district].filter(Boolean).join(' ')}
            </div>
          )}
          {confidenceTotal !== null && (
            <div style={{ marginTop: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                <span style={{ color: confidenceTotal >= 85 ? 'var(--success)' : confidenceTotal >= 60 ? 'var(--warning)' : 'var(--error)', fontWeight: 500 }}>
                  置信度 {confidenceTotal}%
                </span>
                {result.confidence?.is_trustworthy ? (
                  <span className="tag tag-green">可信</span>
                ) : (
                  <span className="tag tag-amber">待确认</span>
                )}
              </div>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${confidenceTotal}%`,
                    background: confidenceTotal >= 85 ? 'var(--success)' : confidenceTotal >= 60 ? 'var(--warning)' : 'var(--error)',
                  }}
                />
              </div>
            </div>
          )}
        </div>
        <button
          onClick={handleCopy}
          title="复制坐标"
          className="btn-icon"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 6,
            borderRadius: 6,
            color: copied ? 'var(--success)' : 'var(--text-muted)',
            transition: 'all var(--transition-fast)',
            flexShrink: 0,
            marginLeft: 8,
          }}
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
      </div>
    </div>
  )
}

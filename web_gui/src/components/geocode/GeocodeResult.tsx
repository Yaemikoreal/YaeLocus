import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import { getSourceLabel, getSourceColor } from '../../lib/utils'
import { MapPin, Copy, Check } from 'lucide-react'
import { useState } from 'react'

export default function GeocodeResult({ result }: { result: GeocodeResultType }) {
  const [copied, setCopied] = useState(false)

  if (!result.success) {
    return (
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          fontSize: 14,
        }}
      >
        <span style={{ fontWeight: 600 }}>{result.original_address}</span>
        <span
          style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 600,
            background: '#fce8e6',
            color: '#d93025',
            marginLeft: 8,
          }}
        >
          失败
        </span>
        {result.warning && (
          <div style={{ color: '#d93025', fontSize: 12, marginTop: 4 }}>{result.warning}</div>
        )}
      </div>
    )
  }

  const coordStr = `${result.latitude.toFixed(6)}, ${result.longitude.toFixed(6)}`
  const sourceColor = getSourceColor(result.source)

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
      style={{
        padding: '12px 16px',
        borderBottom: '1px solid #f0f0f0',
        fontSize: 14,
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(43,18,0,0.01)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>{result.original_address}</div>
          {result.formatted_address && result.formatted_address !== result.original_address && (
            <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
              标准化: {result.formatted_address}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: '#1e8e3e', fontSize: 13, fontFamily: 'ui-monospace, monospace' }}>
              <MapPin size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
              {coordStr}
            </span>
            <span
              style={{
                display: 'inline-block',
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 600,
                background: `${sourceColor}15`,
                color: sourceColor,
              }}
            >
              {getSourceLabel(result.source)}
            </span>
            {result.coordinate_system && (
              <span
                style={{
                  display: 'inline-block',
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: 11,
                  background: 'rgba(43,18,0,0.04)',
                  color: '#6b6b6b',
                }}
              >
                {result.coordinate_system}
              </span>
            )}
          </div>
          {result.province && (
            <div style={{ color: '#888', fontSize: 12, marginTop: 2 }}>
              {[result.province, result.city, result.district].filter(Boolean).join(' ')}
            </div>
          )}
        </div>
        <button
          onClick={handleCopy}
          title="复制坐标"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 6,
            borderRadius: 6,
            color: copied ? '#1e8e3e' : '#6b6b6b',
            transition: 'all 0.2s',
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

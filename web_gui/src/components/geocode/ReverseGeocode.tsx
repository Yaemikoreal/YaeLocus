import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { reverseGeocode } from '../../lib/api'
import { isValidLat, isValidLon, parseCoordinate } from '../../lib/utils'
import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import { MapPin, Loader2 } from 'lucide-react'

interface Props {
  disabled?: boolean
}

export default function ReverseGeocode({ disabled }: Props) {
  const [latStr, setLatStr] = useState('')
  const [lonStr, setLonStr] = useState('')
  const [result, setResult] = useState<GeocodeResultType | null>(null)
  const [inputError, setInputError] = useState('')

  const mutation = useMutation({
    mutationFn: ({ lat, lon }: { lat: number; lon: number }) => reverseGeocode(lat, lon),
    onSuccess: (data) => setResult(data),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setInputError('')

    const lat = parseCoordinate(latStr)
    const lon = parseCoordinate(lonStr)

    if (lat === null || lon === null) {
      setInputError('请输入有效的数字坐标')
      return
    }
    if (!isValidLat(lat)) {
      setInputError('纬度范围: -90 到 90')
      return
    }
    if (!isValidLon(lon)) {
      setInputError('经度范围: -180 到 180')
      return
    }

    setResult(null)
    mutation.mutate({ lat, lon })
  }

  return (
    <div
      style={{
        background: 'rgba(43,18,0,0.02)',
        borderRadius: 8,
        padding: 28,
        marginBottom: 20,
      }}
    >
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>逆地理编码</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        输入经纬度坐标，查询对应的地址信息
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <label
              style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}
            >
              纬度 (Latitude)
            </label>
            <input
              type="text"
              value={latStr}
              onChange={(e) => setLatStr(e.target.value)}
              placeholder="例: 39.9087"
              disabled={disabled || mutation.isPending}
              style={{
                width: '100%',
                padding: '10px 14px',
                border: `1.5px solid ${inputError && !isValidLat(parseCoordinate(latStr) ?? 0) ? '#d93025' : '#eae8e7'}`,
                borderRadius: 8,
                fontSize: 14,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label
              style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}
            >
              经度 (Longitude)
            </label>
            <input
              type="text"
              value={lonStr}
              onChange={(e) => setLonStr(e.target.value)}
              placeholder="例: 116.3975"
              disabled={disabled || mutation.isPending}
              style={{
                width: '100%',
                padding: '10px 14px',
                border: `1.5px solid ${inputError && !isValidLon(parseCoordinate(lonStr) ?? 0) ? '#d93025' : '#eae8e7'}`,
                borderRadius: 8,
                fontSize: 14,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={disabled || mutation.isPending || !latStr.trim() || !lonStr.trim()}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 24px',
              marginTop: 25,
              background: disabled ? '#ccc' : '#ff9d4d',
              color: 'rgba(20,20,19,0.88)',
              border: 'none',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600,
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            {mutation.isPending ? (
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <MapPin size={16} />
            )}
            查询
          </button>
        </div>
        {inputError && (
          <div style={{ color: '#d93025', fontSize: 13, marginTop: 8 }}>{inputError}</div>
        )}
      </form>

      {mutation.isError && (
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
          {(mutation.error as Error)?.message || '查询失败，请重试'}
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: 16,
            border: '1px solid #eae8e7',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        >
          <GeocodeResultCard result={result} />
        </div>
      )}
    </div>
  )
}

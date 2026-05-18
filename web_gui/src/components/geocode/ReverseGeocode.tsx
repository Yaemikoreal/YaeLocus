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

  const latError = inputError && !isValidLat(parseCoordinate(latStr) ?? 0)
  const lonError = inputError && !isValidLon(parseCoordinate(lonStr) ?? 0)

  return (
    <div className="card">
      <h3 className="card-title">逆地理编码</h3>
      <p className="card-desc">输入经纬度坐标，查询对应的地址信息</p>

      <form onSubmit={handleSubmit}>
        <div className="form-row" style={{ alignItems: 'flex-start' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">纬度 (Latitude)</label>
            <input
              type="text"
              value={latStr}
              onChange={(e) => setLatStr(e.target.value)}
              placeholder="例: 39.9087"
              disabled={disabled || mutation.isPending}
              className="form-input"
              style={{ borderColor: latError ? 'var(--error)' : undefined }}
            />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">经度 (Longitude)</label>
            <input
              type="text"
              value={lonStr}
              onChange={(e) => setLonStr(e.target.value)}
              placeholder="例: 116.3975"
              disabled={disabled || mutation.isPending}
              className="form-input"
              style={{ borderColor: lonError ? 'var(--error)' : undefined }}
            />
          </div>
          <button
            type="submit"
            disabled={disabled || mutation.isPending || !latStr.trim() || !lonStr.trim()}
            className="btn btn-primary"
            style={{ marginTop: 25 }}
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
          <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 8 }}>{inputError}</div>
        )}
      </form>

      {mutation.isError && (
        <div className="alert alert-error" style={{ marginTop: 16, marginBottom: 0 }}>
          {(mutation.error as Error)?.message || '查询失败，请重试'}
        </div>
      )}

      {result && (
        <div className="result-list" style={{ marginTop: 16 }}>
          <GeocodeResultCard result={result} />
        </div>
      )}
    </div>
  )
}

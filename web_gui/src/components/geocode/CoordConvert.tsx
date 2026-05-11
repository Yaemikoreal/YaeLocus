import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { convertCoords } from '../../lib/api'
import { isValidLat, isValidLon, parseCoordinate } from '../../lib/utils'
import type { CoordSystem, ConvertResult } from '../../lib/types'
import { ArrowRight, Loader2, Copy, Check } from 'lucide-react'

const SYSTEMS: { value: CoordSystem; label: string }[] = [
  { value: 'wgs84', label: 'WGS-84 (GPS)' },
  { value: 'gcj02', label: 'GCJ-02 (高德/腾讯)' },
  { value: 'bd09', label: 'BD-09 (百度)' },
]

export default function CoordConvert() {
  const [latStr, setLatStr] = useState('')
  const [lonStr, setLonStr] = useState('')
  const [from, setFrom] = useState<CoordSystem>('gcj02')
  const [to, setTo] = useState<CoordSystem>('wgs84')
  const [result, setResult] = useState<ConvertResult | null>(null)
  const [inputError, setInputError] = useState('')
  const [copied, setCopied] = useState(false)

  const mutation = useMutation({
    mutationFn: ({ lat, lon, fromSys, toSys }: { lat: number; lon: number; fromSys: CoordSystem; toSys: CoordSystem }) =>
      convertCoords(lat, lon, fromSys, toSys),
    onSuccess: (data) => setResult(data),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setInputError('')

    const lat = parseCoordinate(latStr)
    const lon = parseCoordinate(lonStr)
    if (lat === null || lon === null) { setInputError('请输入有效的数字坐标'); return }
    if (!isValidLat(lat)) { setInputError('纬度范围: -90 到 90'); return }
    if (!isValidLon(lon)) { setInputError('经度范围: -180 到 180'); return }

    setResult(null)
    mutation.mutate({ lat, lon, fromSys: from, toSys: to })
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28, marginBottom: 20 }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>坐标转换</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        在 WGS-84、GCJ-02、BD-09 坐标系之间进行转换
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>纬度</label>
            <input
              type="text" value={latStr} onChange={(e) => setLatStr(e.target.value)}
              placeholder="39.9087"
              disabled={mutation.isPending}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', fontFamily: 'inherit' }}
            />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>经度</label>
            <input
              type="text" value={lonStr} onChange={(e) => setLonStr(e.target.value)}
              placeholder="116.3975"
              disabled={mutation.isPending}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', fontFamily: 'inherit' }}
            />
          </div>
          <div style={{ width: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>源坐标系</label>
            <select
              value={from} onChange={(e) => setFrom(e.target.value as CoordSystem)}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', fontFamily: 'inherit' }}
            >
              {SYSTEMS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', paddingBottom: 8 }}>
            <ArrowRight size={20} style={{ color: '#999' }} />
          </div>
          <div style={{ width: 150 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#555' }}>目标坐标系</label>
            <select
              value={to} onChange={(e) => setTo(e.target.value as CoordSystem)}
              style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', fontFamily: 'inherit' }}
            >
              {SYSTEMS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={mutation.isPending || !latStr.trim() || !lonStr.trim()}
            style={{
              padding: '10px 24px', marginBottom: 0,
              background: '#ff9d4d', color: 'rgba(20,20,19,0.88)', border: 'none', borderRadius: 10,
              fontSize: 14, fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s', whiteSpace: 'nowrap',
            }}
          >
            {mutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : '转换'}
          </button>
        </div>
        {inputError && <div style={{ color: '#d93025', fontSize: 13, marginTop: 8 }}>{inputError}</div>}
      </form>

      {mutation.isError && (
        <div style={{ marginTop: 16, padding: '12px 16px', background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 14 }}>
          {(mutation.error as Error)?.message || '转换失败'}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 16, padding: 16, background: '#e6f4ea', borderRadius: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 13, color: '#6b6b6b', marginBottom: 4 }}>
                {result.input.system} → {result.output.system}
              </div>
              <div style={{ fontSize: 16, fontFamily: 'ui-monospace, monospace', fontWeight: 600, color: '#1c1c1c' }}>
                {result.output.latitude.toFixed(6)}, {result.output.longitude.toFixed(6)}
              </div>
            </div>
            <button
              onClick={() => handleCopy(`${result.output.latitude.toFixed(6)}, ${result.output.longitude.toFixed(6)}`)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 6, color: copied ? '#1e8e3e' : '#6b6b6b' }}
            >
              {copied ? <Check size={18} /> : <Copy size={18} />}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

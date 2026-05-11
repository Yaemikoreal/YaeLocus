import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { geocodeSingle } from '../../lib/api'
import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import { Search, Loader2 } from 'lucide-react'

interface Props {
  disabled?: boolean
}

export default function SingleGeocode({ disabled }: Props) {
  const [address, setAddress] = useState('')
  const [result, setResult] = useState<GeocodeResultType | null>(null)

  const mutation = useMutation({
    mutationFn: (addr: string) => geocodeSingle(addr),
    onSuccess: (data) => setResult(data),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = address.trim()
    if (!trimmed || trimmed.length < 2) return
    setResult(null)
    mutation.mutate(trimmed)
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
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>单地址编码</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        输入一个中文地址，查询其经纬度坐标
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="输入地址，如：北京市朝阳区建国路88号"
            disabled={disabled || mutation.isPending}
            style={{
              flex: 1,
              padding: '10px 14px',
              border: '1.5px solid #eae8e7',
              borderRadius: 8,
              fontSize: 14,
              outline: 'none',
              transition: 'border-color 0.2s',
              fontFamily: 'inherit',
            }}
            onFocus={(e) => (e.target.style.borderColor = '#ff9d4d')}
            onBlur={(e) => (e.target.style.borderColor = '#eae8e7')}
          />
          <button
            type="submit"
            disabled={disabled || mutation.isPending || address.trim().length < 2}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 24px',
              background: disabled || address.trim().length < 2 ? '#ccc' : '#ff9d4d',
              color: 'rgba(20,20,19,0.88)',
              border: 'none',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600,
              cursor: disabled || address.trim().length < 2 ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            {mutation.isPending ? (
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Search size={16} />
            )}
            编码
          </button>
        </div>
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
          {(mutation.error as Error)?.message || '编码失败，请重试'}
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

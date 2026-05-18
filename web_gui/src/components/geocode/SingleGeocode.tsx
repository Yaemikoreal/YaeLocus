import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { geocodeSingle } from '../../lib/api'
import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import { Loader2 } from 'lucide-react'

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
    <div className="geocode-hero">
      <h2>探索每一个位置</h2>
      <p>输入地址或坐标，即刻获取精准的地理编码结果</p>

      <form onSubmit={handleSubmit}>
        <div className="geocode-input-wrapper">
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="输入地址，如：北京市朝阳区建国路88号"
            disabled={disabled || mutation.isPending}
          />
          <button
            type="submit"
            disabled={disabled || mutation.isPending || address.trim().length < 2}
            className="geocode-submit-btn"
          >
            {mutation.isPending ? (
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <i className="fa-solid fa-search" />
            )}
            编码
          </button>
        </div>
      </form>

      {mutation.isError && (
        <div className="alert alert-error" style={{ marginTop: 16, marginBottom: 0, maxWidth: 640, margin: '16px auto 0' }}>
          {(mutation.error as Error)?.message || '编码失败，请重试'}
        </div>
      )}

      {result && (
        <div className="result-card" style={{ maxWidth: 640, margin: '20px auto 0', textAlign: 'left' }}>
          <GeocodeResultCard result={result} />
        </div>
      )}
    </div>
  )
}

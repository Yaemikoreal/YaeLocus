import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCacheStats, clearCache, cleanupCache, exportCache } from '../../lib/api'
import { Trash2, RefreshCw, Download, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function CachePanel() {
  const queryClient = useQueryClient()

  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ['cacheStats'],
    queryFn: ({ signal }) => fetchCacheStats(signal),
    refetchInterval: 10_000,
  })

  const clearMutation = useMutation({
    mutationFn: () => clearCache(),
    onSuccess: (data) => {
      toast.success(`已清空 ${data.cleared} 条缓存记录`)
      queryClient.invalidateQueries({ queryKey: ['cacheStats'] })
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const cleanupMutation = useMutation({
    mutationFn: () => cleanupCache(),
    onSuccess: (data) => {
      toast.success(`已清理 ${data.removed} 条过期记录`)
      queryClient.invalidateQueries({ queryKey: ['cacheStats'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const exportMutation = useMutation({
    mutationFn: () => exportCache(),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `cache_export_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('缓存已导出')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>缓存管理</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 20 }}>
        SQLite 地理编码缓存数据库，加速重复地址查询
      </p>

      {isLoading && <div style={{ padding: 32, textAlign: 'center', color: '#888' }}>加载中...</div>}
      {isError && <div style={{ padding: 16, background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 14 }}>加载缓存统计失败</div>}

      {stats && (
        <>
          {/* Stats cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 24 }}>
            <StatCard label="总条目" value={stats.total_entries} color="#1a73e8" />
            <StatCard label="命中次数" value={stats.hits} color="#1e8e3e" />
            <StatCard label="未命中" value={stats.misses} color="#d93025" />
            <StatCard label="命中率" value={`${(stats.hit_rate * 100).toFixed(1)}%`} color="#ff9d4d" />
            <StatCard label="过期条目" value={stats.expired_entries} color="#6b6b6b" />
            <StatCard label="待写入" value={stats.pending_writes} color="#6b6b6b" />
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button
              onClick={() => cleanupMutation.mutate()}
              disabled={cleanupMutation.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', background: '#e8eaed', color: '#333', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
            >
              {cleanupMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={14} />}
              清理过期
            </button>
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', background: '#e8eaed', color: '#333', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
            >
              {exportMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Download size={14} />}
              导出 JSON
            </button>
            <button
              onClick={() => {
                if (window.confirm('确认清空全部缓存？此操作不可撤销。')) {
                  clearMutation.mutate()
                }
              }}
              disabled={clearMutation.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', background: '#d93025', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
            >
              {clearMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={14} />}
              清空缓存
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 8, padding: '16px', border: '1px solid #eae8e7', textAlign: 'center' }}>
      <div style={{ fontSize: 24, fontWeight: 700, color, fontFamily: 'ui-monospace, monospace' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b6b6b', marginTop: 4 }}>{label}</div>
    </div>
  )
}

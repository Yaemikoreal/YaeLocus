import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCacheStats, clearCache, cleanupCache, exportCache } from '../../lib/api'
import { Trash2, RefreshCw, Download, Loader2, MemoryStick } from 'lucide-react'
import { toast } from 'sonner'

export default function CachePanel() {
  const queryClient = useQueryClient()

  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ['cacheStats'],
    queryFn: ({ signal }) => fetchCacheStats(signal),
    refetchInterval: 30_000,
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
      toast.success(`缓存已导出（${data.entries?.length ?? 0} 条记录）`)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="card">
      <div className="card-title"><i className="fa-solid fa-database" /> 缓存管理</div>
      <p className="card-desc">混合缓存架构：内存 LRU + SQLite 持久化</p>

      {isLoading && <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</div>}
      {isError && <div className="alert alert-error">加载缓存统计失败</div>}

      {stats && (
        <>
          <div className="cache-stat-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
            <div className="cache-stat">
              <div className="num">{stats.total_entries.toLocaleString()}</div>
              <div className="txt">缓存条目</div>
            </div>
            <div className="cache-stat">
              <div className="num">{(stats.hit_rate).toFixed(1)}%</div>
              <div className="txt">命中率</div>
            </div>
            <div className="cache-stat">
              <div className="num">{stats.hits.toLocaleString()}</div>
              <div className="txt">命中次数</div>
            </div>
            <div className="cache-stat">
              <div className="num">{stats.misses.toLocaleString()}</div>
              <div className="txt">未命中</div>
            </div>
            {stats.mem_entries != null && (
              <div className="cache-stat">
                <div className="num" style={{ display: 'flex', alignItems: 'center', gap: 4 }}><MemoryStick size={12} /> {stats.mem_entries.toLocaleString()}</div>
                <div className="txt">内存 / {stats.mem_max ?? '-'}</div>
              </div>
            )}
            {stats.expired_entries != null && stats.expired_entries > 0 && (
              <div className="cache-stat">
                <div className="num" style={{ color: 'var(--warning)' }}>{stats.expired_entries.toLocaleString()}</div>
                <div className="txt">已过期</div>
              </div>
            )}
            {stats.evictions != null && stats.evictions > 0 && (
              <div className="cache-stat">
                <div className="num">{stats.evictions.toLocaleString()}</div>
                <div className="txt">LRU 淘汰</div>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button onClick={() => cleanupMutation.mutate()} disabled={cleanupMutation.isPending} className="btn btn-secondary btn-sm">
              {cleanupMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={14} />}
              清理过期
            </button>
            <button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending} className="btn btn-secondary btn-sm">
              {exportMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Download size={14} />}
              导出 JSON
            </button>
            <button onClick={() => {
              if (window.confirm('确认清空全部缓存？此操作不可撤销。')) { clearMutation.mutate() }
            }} disabled={clearMutation.isPending} className="btn btn-danger btn-sm">
              {clearMutation.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={14} />}
              清空缓存
            </button>
          </div>
        </>
      )}
    </div>
  )
}

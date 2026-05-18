import { useState, useEffect, useCallback } from 'react'
import { fetchCompletedTasks, fetchTaskStatus, fetchTaskDetail, deleteTask } from '../../lib/api'
import { API_BASE } from '../../lib/constants'
import type { GeocodeResult as GeocodeResultType, CompletedTask } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import { Eye, RefreshCw, X, Trash2, FileText, MapPin } from 'lucide-react'

export default function TaskHistory() {
  const [tasks, setTasks] = useState<CompletedTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [detailTask, setDetailTask] = useState<string | null>(null)
  const [detailResults, setDetailResults] = useState<GeocodeResultType[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchCompletedTasks()
      setTasks(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchCompletedTasks()
      .then((data) => { if (!cancelled) { setTasks(data); setLoading(false) } })
      .catch((e) => { if (!cancelled) { setError((e as Error).message); setLoading(false) } })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === 'running')
    if (runningTasks.length === 0) return

    const timer = setInterval(async () => {
      for (const t of runningTasks) {
        try {
          const data = await fetchTaskStatus(t.task_id)
          if (data.status === 'done' || data.status === 'error') {
            loadTasks()
          }
        } catch {
          // ignore
        }
      }
    }, 3000)

    return () => clearInterval(timer)
  }, [tasks, loadTasks])

  const handleViewDetail = useCallback(async (taskId: string) => {
    setDetailTask(taskId)
    setDetailLoading(true)
    setDetailError('')
    setDetailResults([])
    try {
      const data = await fetchTaskDetail(taskId)
      if (data.results && data.results.length > 0) {
        setDetailResults(data.results)
      } else if (data.csv_output) {
        try {
          const csvRes = await fetch(`${API_BASE}/api/file/content?path=${encodeURIComponent(data.csv_output.replace(/^.*output\//, 'output/'))}`)
          if (csvRes.ok) {
            const csvData = await csvRes.json() as { preview?: Array<Record<string, string>> }
            if (csvData.preview && csvData.preview.length > 0) {
              const results: GeocodeResultType[] = csvData.preview
                .filter((row) => row.latitude && row.longitude)
                .map((row) => ({
                  success: true,
                  latitude: parseFloat(row.latitude),
                  longitude: parseFloat(row.longitude),
                  original_address: row['地址'] || row['address'] || '',
                  formatted_address: row['formatted_address'] || null,
                  source: row['source'] || 'unknown',
                  coordinate_system: 'GCJ-02' as const,
                }))
              if (results.length > 0) {
                setDetailResults(results)
                return
              }
            }
          }
        } catch {
          // CSV 读取失败
        }
        setDetailError('该任务无可用结果（结果文件可能已被移动或删除）')
      } else {
        setDetailError('该任务无可用结果')
      }
    } catch (e) {
      setDetailError((e as Error).message)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const handleRefresh = useCallback(async (taskId: string) => {
    try {
      await fetchTaskStatus(taskId)
      loadTasks()
    } catch {
      // ignore
    }
  }, [loadTasks])

  const handleDelete = useCallback(async (taskId: string) => {
    if (!window.confirm('确认删除此任务？此操作不可撤销。')) return
    try {
      await deleteTask(taskId)
      loadTasks()
    } catch (e) {
      setError((e as Error).message)
    }
  }, [loadTasks])

  const formatTime = (ts: number | null | undefined) => {
    if (!ts) return '-'
    return new Date(ts * 1000).toLocaleString()
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="card-title">已完成任务</h3>
        <p className="card-desc">加载中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h3 className="card-title">已完成任务</h3>
        <p style={{ color: 'var(--error)', fontSize: 14 }}>{error}</p>
        <button onClick={loadTasks} className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}>
          重试
        </button>
      </div>
    )
  }

  if (tasks.length === 0) {
    return (
      <div className="card">
        <h3 className="card-title">已完成任务</h3>
        <p className="card-desc">暂无历史任务，上传文件并开始编码后记录将在此显示</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>已完成任务</h3>
        <button onClick={loadTasks} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>任务 ID</th>
              <th>文件</th>
              <th>列名</th>
              <th>地市</th>
              <th style={{ textAlign: 'center' }}>总数</th>
              <th style={{ textAlign: 'center' }}>成功</th>
              <th style={{ textAlign: 'center' }}>失败</th>
              <th style={{ textAlign: 'center' }}>状态</th>
              <th>时间</th>
              <th style={{ textAlign: 'center' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
              let statusBadge: React.ReactNode
              if (t.status === 'done') {
                statusBadge = <span className="badge badge-success">已完成</span>
              } else if (t.status === 'error') {
                statusBadge = <span className="badge badge-error">失败</span>
              } else {
                statusBadge = <span className="badge badge-info">处理中</span>
              }

              return (
                <tr key={t.task_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{t.task_id}</td>
                  <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.input_file}>{t.input_file || '-'}</td>
                  <td>{t.column || '-'}</td>
                  <td>{t.city || '-'}</td>
                  <td style={{ textAlign: 'center' }}>{t.total}</td>
                  <td style={{ textAlign: 'center', color: 'var(--success)', fontWeight: 600 }}>{t.status === 'done' ? t.success : '-'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--error)', fontWeight: 600 }}>{t.status === 'done' ? t.failed : '-'}</td>
                  <td style={{ textAlign: 'center' }}>{statusBadge}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{formatTime(t.started_at)}</td>
                  <td style={{ textAlign: 'center', display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'center' }}>
                    {t.status === 'done' && (
                      <>
                        {t.csv_output && (
                          <a href={`${API_BASE}/api/file/content?path=${encodeURIComponent(t.csv_output.replace(/^.*output\//, 'output/'))}`} target="_blank" rel="noreferrer" className="btn btn-sm" style={{ background: 'var(--info-bg)', color: 'var(--info)', textDecoration: 'none' }}>
                            <FileText size={12} /> CSV
                          </a>
                        )}
                        {t.map_output && (
                          <a href={`${API_BASE}/api/map/view/${encodeURIComponent(t.map_output.split('/').pop() || '')}`} target="_blank" rel="noreferrer" className="btn btn-sm" style={{ background: 'var(--info-bg)', color: 'var(--info)', textDecoration: 'none' }}>
                            <MapPin size={12} /> 地图
                          </a>
                        )}
                        <button onClick={() => handleViewDetail(t.task_id)} className="btn btn-primary btn-sm">
                          <Eye size={12} /> 明细
                        </button>
                      </>
                    )}
                    {t.status === 'running' && (
                      <button onClick={() => handleRefresh(t.task_id)} className="btn btn-secondary btn-sm">
                        <RefreshCw size={12} /> 刷新
                      </button>
                    )}
                    {t.status !== 'running' && (
                      <button onClick={() => handleDelete(t.task_id)} className="btn btn-danger btn-sm">
                        <Trash2 size={12} />
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {detailTask && (
        <div className="detail-modal">
          <div className="detail-modal-header">
            <strong style={{ fontSize: 14, fontFamily: 'monospace' }}>{detailTask}</strong>
            <button onClick={() => { setDetailTask(null); setDetailResults([]) }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#6b6b6b' }}>
              <X size={18} />
            </button>
          </div>
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            {detailLoading ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#888' }}>加载中...</div>
            ) : detailError ? (
              <div style={{ padding: 16, color: '#d93025', fontSize: 14 }}>{detailError}</div>
            ) : detailResults.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#888' }}>无结果</div>
            ) : (
              detailResults.map((r, i) => <GeocodeResultCard key={i} result={r} />)
            )}
          </div>
        </div>
      )}
    </div>
  )
}

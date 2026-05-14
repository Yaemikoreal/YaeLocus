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

  // 加载任务列表
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

  // 初始加载
  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  // 自动轮询运行中的任务
  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === 'running')
    if (runningTasks.length === 0) return

    const timer = setInterval(async () => {
      for (const t of runningTasks) {
        try {
          const data = await fetchTaskStatus(t.task_id)
          if (data.status === 'done' || data.status === 'error') {
            // 任务完成，刷新列表
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
        // 尝试从 CSV 文件读取结果
        try {
          const csvRes = await fetch(`${API_BASE}/api/file/content?path=${encodeURIComponent(data.csv_output.replace(/^.*output\//, 'output/'))}`)
          if (csvRes.ok) {
            const csvData = await csvRes.json()
            if (csvData.preview && csvData.preview.length > 0) {
              const results: GeocodeResultType[] = csvData.preview
                .filter((row: any) => row.latitude && row.longitude)
                .map((row: any) => ({
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
          // CSV 读取失败，使用默认消息
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
      // 刷新完成后重新加载任务列表
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
      <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
        <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>已完成任务</h3>
        <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14 }}>加载中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
        <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>已完成任务</h3>
        <p style={{ color: '#d93025', fontSize: 14 }}>{error}</p>
        <button onClick={loadTasks} style={{ marginTop: 8, padding: '8px 16px', background: '#e8eaed', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
          重试
        </button>
      </div>
    )
  }

  if (tasks.length === 0) {
    return (
      <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
        <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>已完成任务</h3>
        <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14 }}>暂无历史任务，上传文件并开始编码后记录将在此显示</p>
      </div>
    )
  }

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c' }}>已完成任务</h3>
        <button onClick={loadTasks} style={{ padding: '6px 12px', background: '#e8eaed', border: 'none', borderRadius: 6, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f7fa', borderBottom: '2px solid #e0e0e0' }}>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>任务 ID</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>文件</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>列名</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>地市</th>
              <th style={{ padding: '8px 10px', textAlign: 'center', fontSize: 12 }}>总数</th>
              <th style={{ padding: '8px 10px', textAlign: 'center', fontSize: 12 }}>成功</th>
              <th style={{ padding: '8px 10px', textAlign: 'center', fontSize: 12 }}>失败</th>
              <th style={{ padding: '8px 10px', textAlign: 'center', fontSize: 12 }}>状态</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>时间</th>
              <th style={{ padding: '8px 10px', textAlign: 'center', fontSize: 12 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
              let statusBadge: React.ReactNode
              if (t.status === 'done') {
                statusBadge = <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, background: '#e6f4ea', color: '#1e8e3e', fontWeight: 600 }}>已完成</span>
              } else if (t.status === 'error') {
                statusBadge = <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, background: '#fce8e6', color: '#d93025', fontWeight: 600 }}>失败</span>
              } else {
                statusBadge = <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, background: '#e8f0fe', color: '#1a73e8', fontWeight: 600 }}>处理中</span>
              }

              return (
                <tr key={t.task_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>{t.task_id}</td>
                  <td style={{ padding: '8px 10px', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.input_file}>{t.input_file || '-'}</td>
                  <td style={{ padding: '8px 10px' }}>{t.column || '-'}</td>
                  <td style={{ padding: '8px 10px' }}>{t.city || '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>{t.total}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center', color: '#1e8e3e', fontWeight: 600 }}>{t.status === 'done' ? t.success : '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center', color: '#d93025', fontWeight: 600 }}>{t.status === 'done' ? t.failed : '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>{statusBadge}</td>
                  <td style={{ padding: '8px 10px', color: '#888', fontSize: 11 }}>{formatTime(t.started_at)}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {t.status === 'done' && (
                      <>
                        {t.csv_output && (
                          <a href={`${API_BASE}/api/file/content?path=${encodeURIComponent(t.csv_output.replace(/^.*output\//, 'output/'))}`} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '4px 8px', background: '#e8f0fe', color: '#1a73e8', borderRadius: 4, fontSize: 11, textDecoration: 'none' }}>
                            <FileText size={12} /> CSV
                          </a>
                        )}
                        {t.map_output && (
                          <a href={`${API_BASE}/api/map/view/${encodeURIComponent(t.map_output.split('/').pop() || '')}`} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '4px 8px', background: '#e8f0fe', color: '#1a73e8', borderRadius: 4, fontSize: 11, textDecoration: 'none' }}>
                            <MapPin size={12} /> 地图
                          </a>
                        )}
                        <button onClick={() => handleViewDetail(t.task_id)}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', background: '#ff9d4d', color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' }}>
                          <Eye size={12} /> 明细
                        </button>
                      </>
                    )}
                    {t.status === 'running' && (
                      <button onClick={() => handleRefresh(t.task_id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', background: '#e8eaed', color: '#333', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' }}>
                        <RefreshCw size={12} /> 刷新
                      </button>
                    )}
                    {t.status !== 'running' && (
                      <button onClick={() => handleDelete(t.task_id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', background: '#fce8e6', color: '#d93025', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' }}>
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
        <div style={{ marginTop: 20, border: '1px solid #eae8e7', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', background: '#f5f7fa', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong style={{ fontSize: 14, fontFamily: 'monospace' }}>{detailTask}</strong>
            <button onClick={() => { setDetailTask(null); setDetailResults([]) }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#6b6b6b' }}>
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
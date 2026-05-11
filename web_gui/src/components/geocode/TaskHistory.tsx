import { useState, useEffect, useCallback } from 'react'
import { fetchTaskStatus } from '../../lib/api'
import { API_BASE } from '../../lib/constants'
import type { GeocodeResult as GeocodeResultType } from '../../lib/types'
import GeocodeResultCard from './GeocodeResult'
import { Eye, RefreshCw, X } from 'lucide-react'

interface LocalTask {
  id: string
  filename: string
  total: number
  status: 'running' | 'done' | 'error'
  success: number
  failed: number
  progress: number
  time: number
}

const STORAGE_KEY = 'yaelocus_tasks'

function loadTasks(): LocalTask[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function saveTasks(tasks: LocalTask[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks.slice(0, 20)))
}

export default function TaskHistory() {
  const [tasks, setTasks] = useState<LocalTask[]>(loadTasks)
  const [detailTask, setDetailTask] = useState<string | null>(null)
  const [detailResults, setDetailResults] = useState<GeocodeResultType[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  // Poll running tasks
  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === 'running')
    if (runningTasks.length === 0) return

    const timers: ReturnType<typeof setInterval>[] = []

    for (const t of runningTasks) {
      const timer = setInterval(() => {
        // 检查此任务是否仍在运行（避免泄漏：已完成的任务不再轮询）
        setTasks((prev) => {
          const current = prev.find((p) => p.id === t.id)
          if (!current || current.status !== 'running') return prev
          return prev
        })

        fetchTaskStatus(t.id)
          .then((data) => {
            setTasks((prev) => {
              const current = prev.find((p) => p.id === t.id)
              // 任务已不在列表中或已非运行状态 → 清除此 interval
              if (!current || current.status !== 'running') {
                clearInterval(timer)
                return prev
              }
              if (data.status === 'done' || data.status === 'error') {
                clearInterval(timer)
                const updated = prev.map((p) =>
                  p.id === t.id
                    ? { ...p, status: data.status, success: (data as any).success || 0, failed: (data as any).failed || 0, progress: data.total }
                    : p
                )
                saveTasks(updated)
                return updated
              }
              const updated = prev.map((p) =>
                p.id === t.id ? { ...p, progress: data.progress } : p
              )
              saveTasks(updated)
              return updated
            })
          })
          .catch(() => {})
      }, 3000)
      timers.push(timer)
    }

    return () => timers.forEach(clearInterval)
  }, [tasks.length])

  const handleViewDetail = useCallback(async (taskId: string) => {
    setDetailTask(taskId)
    setDetailLoading(true)
    setDetailError('')
    try {
      const res = await fetch(`${API_BASE}/api/geocode/task/${taskId}`)
      const data = await res.json()
      if (data.results) {
        setDetailResults(data.results)
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
      const data = await fetchTaskStatus(taskId)
      setTasks((prev) => {
        const updated = prev.map((p) =>
          p.id === taskId
            ? { ...p, status: data.status, progress: data.progress || data.total, success: (data as any).success || p.success, failed: (data as any).failed || p.failed }
            : p
        )
        saveTasks(updated)
        return updated
      })
    } catch { /* ignore */ }
  }, [])

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
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 16 }}>已完成任务</h3>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f7fa', borderBottom: '2px solid #e0e0e0' }}>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>任务 ID</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12 }}>文件</th>
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
                statusBadge = <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, background: '#e8f0fe', color: '#1a73e8', fontWeight: 600 }}>处理中 {t.progress}/{t.total}</span>
              }

              return (
                <tr key={t.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>{t.id}</td>
                  <td style={{ padding: '8px 10px', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.filename}>{t.filename || '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>{t.total}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center', color: '#1e8e3e', fontWeight: 600 }}>{t.status === 'done' ? t.success : '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center', color: '#d93025', fontWeight: 600 }}>{t.status === 'done' ? t.failed : '-'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>{statusBadge}</td>
                  <td style={{ padding: '8px 10px', color: '#888', fontSize: 11 }}>{new Date(t.time).toLocaleString()}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                    {t.status === 'done' && (
                      <button onClick={() => handleViewDetail(t.id)}
                        style={{ background: '#ff9d4d', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <Eye size={12} /> 明细
                      </button>
                    )}
                    {t.status === 'running' && (
                      <button onClick={() => handleRefresh(t.id)}
                        style={{ background: '#e8eaed', color: '#333', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <RefreshCw size={12} /> 刷新
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

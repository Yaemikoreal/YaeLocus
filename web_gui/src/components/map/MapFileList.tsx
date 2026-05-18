import { useQuery } from '@tanstack/react-query'
import { fetchMapFiles, getMapViewUrl } from '../../lib/api'
import { formatFileSize, formatDate } from '../../lib/utils'
import { ExternalLink, RefreshCw, Loader2, Globe } from 'lucide-react'

export default function MapFileList() {
  const { data: files, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['mapFiles'],
    queryFn: ({ signal }) => fetchMapFiles(signal),
  })

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 className="card-title" style={{ marginBottom: 4 }}><i className="fa-solid fa-map" /> 地图文件列表</h3>
          <p className="card-desc">output/map 目录中的 HTML 地图文件，点击阅览在新标签页打开</p>
        </div>
        <button onClick={() => refetch()} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      {isLoading && (
        <div className="empty-state">
          <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
          <p>加载中...</p>
        </div>
      )}

      {isError && (
        <div className="alert alert-error">
          {(error as Error)?.message || '加载失败'}
          <button onClick={() => refetch()} className="btn btn-ghost btn-sm" style={{ marginLeft: 12 }}>重试</button>
        </div>
      )}

      {!isLoading && !isError && files && files.length === 0 && (
        <div className="empty-state">
          <Globe size={48} />
          <h4>暂无地图文件</h4>
          <p>完成地理编码后将自动生成地图文件</p>
        </div>
      )}

      {!isLoading && !isError && files && files.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th style={{ textAlign: 'center' }}>大小</th>
              <th>修改时间</th>
              <th style={{ textAlign: 'center' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.name}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{f.name}</td>
                <td style={{ textAlign: 'center' }}>{formatFileSize(f.size_kb * 1024)}</td>
                <td>{formatDate(f.modified)}</td>
                <td style={{ textAlign: 'center' }}>
                  <a
                    href={getMapViewUrl(f.name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary btn-sm"
                    style={{ textDecoration: 'none' }}
                  >
                    <ExternalLink size={12} /> 阅览
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {files && files.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
          共 {files.length} 个地图文件
        </div>
      )}
    </div>
  )
}

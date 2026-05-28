import { useQuery } from '@tanstack/react-query'
import { fetchDataFiles, openDirectory } from '../../lib/api'
import { formatFileSize, formatDate } from '../../lib/utils'
import { RefreshCw, Loader2, FileSpreadsheet, FileText, FolderOpen } from 'lucide-react'
import { toast } from 'sonner'

export default function FileBrowser() {
  const { data: files, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dataFiles'],
    queryFn: ({ signal }) => fetchDataFiles(signal),
  })

  const handleOpenDir = async () => {
    try {
      await openDirectory('data')
    } catch (e: any) {
      toast.error(e.message || '无法打开目录')
    }
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 className="card-title" style={{ marginBottom: 4 }}><i className="fa-solid fa-folder-open" /> 数据文件列表</h3>
          <p className="card-desc">data/ 目录中可用于地理编码的 CSV / XLSX 文件</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleOpenDir} className="btn btn-secondary btn-sm" title="在文件资源管理器中打开 data 目录">
            <FolderOpen size={14} /> 打开目录
          </button>
          <button onClick={() => refetch()} className="btn btn-secondary btn-sm">
            <RefreshCw size={14} /> 刷新
          </button>
        </div>
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
          <FileSpreadsheet size={48} />
          <h4>暂无数据文件</h4>
          <p>将 CSV/XLSX 文件放入 data/ 目录即可在此浏览</p>
        </div>
      )}

      {!isLoading && !isError && files && files.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th style={{ textAlign: 'center' }}>大小</th>
              <th>修改时间</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.name}>
                <td style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {f.name.endsWith('.csv') ? (
                    <FileText size={16} style={{ color: 'var(--success)' }} />
                  ) : (
                    <FileSpreadsheet size={16} style={{ color: 'var(--info)' }} />
                  )}
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{f.name}</span>
                </td>
                <td style={{ textAlign: 'center' }}>{formatFileSize(f.size_kb * 1024)}</td>
                <td>{formatDate(f.modified)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {files && files.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
          共 {files.length} 个数据文件
        </div>
      )}
    </div>
  )
}

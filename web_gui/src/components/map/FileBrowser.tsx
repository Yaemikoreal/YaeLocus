import { useQuery } from '@tanstack/react-query'
import { fetchDataFiles } from '../../lib/api'
import { formatFileSize, formatDate } from '../../lib/utils'
import { RefreshCw, Loader2, FileSpreadsheet, FileText } from 'lucide-react'

export default function FileBrowser() {
  const { data: files, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dataFiles'],
    queryFn: ({ signal }) => fetchDataFiles(signal),
  })

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>数据文件列表</h3>
          <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14 }}>data/ 目录中可用于地理编码的 CSV / XLSX 文件</p>
        </div>
        <button
          onClick={() => refetch()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', background: '#e8eaed', color: '#333', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
        >
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      {isLoading && (
        <div style={{ padding: 48, textAlign: 'center', color: '#888' }}>
          <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
          <div>加载中...</div>
        </div>
      )}

      {isError && (
        <div style={{ padding: 16, background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 14 }}>
          {(error as Error)?.message || '加载失败'}
          <button onClick={() => refetch()} style={{ marginLeft: 12, background: 'none', border: 'none', color: '#d93025', cursor: 'pointer', textDecoration: 'underline' }}>重试</button>
        </div>
      )}

      {!isLoading && !isError && files && files.length === 0 && (
        <div style={{ padding: 48, textAlign: 'center' }}>
          <FileSpreadsheet size={48} style={{ color: '#ccc', marginBottom: 12 }} />
          <div style={{ color: '#888', fontSize: 15, marginBottom: 4 }}>暂无数据文件</div>
          <div style={{ color: '#aaa', fontSize: 13 }}>将 CSV/XLSX 文件放入 data/ 目录即可在此浏览</div>
        </div>
      )}

      {!isLoading && !isError && files && files.length > 0 && (
        <div style={{ border: '1px solid #eae8e7', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f5f7fa', borderBottom: '2px solid #e0e0e0' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12 }}>文件名</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontSize: 12, width: 100 }}>大小</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, width: 180 }}>修改时间</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {f.name.endsWith('.csv') ? <FileText size={16} style={{ color: '#1e8e3e' }} /> : <FileSpreadsheet size={16} style={{ color: '#1a73e8' }} />}
                    <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{f.name}</span>
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center', color: '#888', fontSize: 12 }}>
                    {formatFileSize(f.size_kb * 1024)}
                  </td>
                  <td style={{ padding: '8px 12px', color: '#888', fontSize: 11 }}>
                    {formatDate(f.modified)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {files && files.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>共 {files.length} 个数据文件</div>
      )}
    </div>
  )
}

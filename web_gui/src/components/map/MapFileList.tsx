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
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>地图文件列表</h3>
          <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14 }}>
            output/map 目录中的 HTML 地图文件，点击阅览在新标签页打开
          </p>
        </div>
        <button
          onClick={() => refetch()}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px',
            background: '#e8eaed', color: '#333', border: 'none', borderRadius: 8, fontSize: 13,
            cursor: 'pointer', transition: 'background 0.2s',
          }}
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
        <div style={{ padding: '16px', background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 14 }}>
          {(error as Error)?.message || '加载失败'}
          <button onClick={() => refetch()} style={{ marginLeft: 12, background: 'none', border: 'none', color: '#d93025', cursor: 'pointer', textDecoration: 'underline' }}>
            重试
          </button>
        </div>
      )}

      {!isLoading && !isError && files && files.length === 0 && (
        <div style={{ padding: 48, textAlign: 'center' }}>
          <Globe size={48} style={{ color: '#ccc', marginBottom: 12 }} />
          <div style={{ color: '#888', fontSize: 15, marginBottom: 4 }}>暂无地图文件</div>
          <div style={{ color: '#aaa', fontSize: 13 }}>完成地理编码后将自动生成地图文件</div>
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
                <th style={{ padding: '8px 12px', textAlign: 'center', fontSize: 12, width: 100 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: 12, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.name}>
                    {f.name}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center', color: '#888', fontSize: 12 }}>
                    {formatFileSize(f.size_kb * 1024)}
                  </td>
                  <td style={{ padding: '8px 12px', color: '#888', fontSize: 11 }}>
                    {formatDate(f.modified)}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    <a
                      href={getMapViewUrl(f.name)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '4px 12px', background: '#ff9d4d', color: 'rgba(20,20,19,0.88)',
                        border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600,
                        textDecoration: 'none', cursor: 'pointer',
                      }}
                    >
                      <ExternalLink size={12} /> 阅览
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>
        {files && files.length > 0 && `共 ${files.length} 个地图文件`}
      </div>
    </div>
  )
}

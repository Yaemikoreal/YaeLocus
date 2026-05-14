import { useState } from 'react'
import MapFileList from '../components/map/MapFileList'
import FileBrowser from '../components/map/FileBrowser'
import MapView from '../components/map/MapView'
import { Globe, FolderOpen, Map } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchDataFiles } from '../lib/api'
import type { GeocodeResult } from '../lib/types'

export default function MapPage() {
  const [tab, setTab] = useState<'maps' | 'files' | 'interactive'>('maps')
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  // 获取数据文件列表（用于交互地图）
  const { data: dataFiles } = useQuery({
    queryKey: ['dataFiles'],
    queryFn: () => fetchDataFiles(),
  })

  // 从选定的 CSV 文件加载地图数据
  const { data: mapData, isLoading } = useQuery<{ data: GeocodeResult[] }>({
    queryKey: ['csvData', selectedFile],
    queryFn: async () => {
      if (!selectedFile) return { data: [] }
      const res = await fetch(`/api/file/content?path=output/csv/${encodeURIComponent(selectedFile)}`)
      if (!res.ok) return { data: [] }
      const text = await res.text()
      // 解析 CSV 为 GeocodeResult 数组（支持引号转义）
      const parseCSVLine = (line: string): string[] => {
        const result: string[] = []
        let current = ''
        let inQuotes = false
        for (const ch of line) {
          if (ch === '"') { inQuotes = !inQuotes; continue }
          if (ch === ',' && !inQuotes) { result.push(current.trim()); current = ''; continue }
          current += ch
        }
        result.push(current.trim())
        return result
      }
      const lines = text.trim().split('\n')
      if (lines.length < 2) return { data: [] }
      const headers = parseCSVLine(lines[0])
      const results: GeocodeResult[] = []
      for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i])
        if (values.length < headers.length) continue
        const lat = parseFloat(values[headers.findIndex(h => h.toLowerCase().includes('lat'))] || '0')
        const lon = parseFloat(values[headers.findIndex(h => h.toLowerCase().includes('lon') || h.toLowerCase().includes('lng'))] || '0')
        if (!lat || !lon) continue
        results.push({
          success: true,
          latitude: lat,
          longitude: lon,
          original_address: values[headers.findIndex(h => h.includes('地址') || h.includes('address'))] || '',
          formatted_address: values[headers.findIndex(h => h.includes('formatted') || h.includes('标准化'))] || null,
          source: (values[headers.findIndex(h => h.includes('source') || h.includes('来源'))] || 'unknown') as any,
          coordinate_system: 'GCJ-02',
        })
      }
      return { data: results }
    },
    enabled: !!selectedFile && tab === 'interactive',
  })

  return (
    <div>
      <h1 style={{ fontSize: 36, fontWeight: 600, color: 'rgba(20,20,19,0.88)', lineHeight: 1.3, marginBottom: 8 }}>
        地图浏览
      </h1>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 16, marginBottom: 32 }}>
        浏览已生成的地图文件和处理数据文件，或在交互地图中测算距离
      </p>

      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid #eae8e7' }}>
        <button
          onClick={() => setTab('maps')}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: tab === 'maps' ? 600 : 400,
            color: tab === 'maps' ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
            borderBottom: tab === 'maps' ? '2px solid #ff9d4d' : '2px solid transparent',
            cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Globe size={16} /> 地图文件
        </button>
        <button
          onClick={() => setTab('files')}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: tab === 'files' ? 600 : 400,
            color: tab === 'files' ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
            borderBottom: tab === 'files' ? '2px solid #ff9d4d' : '2px solid transparent',
            cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <FolderOpen size={16} /> 数据文件
        </button>
        <button
          onClick={() => setTab('interactive')}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: tab === 'interactive' ? 600 : 400,
            color: tab === 'interactive' ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
            borderBottom: tab === 'interactive' ? '2px solid #ff9d4d' : '2px solid transparent',
            cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Map size={16} /> 交互地图
        </button>
      </div>

      {tab === 'maps' && <MapFileList />}
      {tab === 'files' && <FileBrowser />}
      {tab === 'interactive' && (
        <div>
          {/* 数据文件选择 */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 14, color: '#666', marginRight: 8 }}>选择数据文件:</label>
            <select
              value={selectedFile || ''}
              onChange={(e) => setSelectedFile(e.target.value)}
              style={{
                padding: '6px 12px',
                fontSize: 13,
                borderRadius: 4,
                border: '1px solid #dee2e6',
                minWidth: 200,
              }}
            >
              <option value="">-- 选择文件 --</option>
              {dataFiles?.filter(f => f.name.endsWith('.csv')).map((f) => (
                <option key={f.name} value={f.name}>{f.name}</option>
              ))}
            </select>
          </div>

          {/* 交互地图 */}
          {selectedFile ? (
            isLoading ? (
              <div style={{ textAlign: 'center', padding: 48, color: '#888' }}>加载中...</div>
            ) : (
              <MapView
                data={mapData?.data || []}
                center={mapData?.data && mapData.data.length > 0 ? [mapData.data[0].latitude, mapData.data[0].longitude] : [35, 105]}
                zoom={mapData?.data && mapData.data.length > 0 ? 12 : 5}
              />
            )
          ) : (
            <div style={{ textAlign: 'center', padding: 48, color: '#888', background: 'rgba(43,18,0,0.02)', borderRadius: 8 }}>
              <Map size={48} color="#4a90d9" style={{ marginBottom: 16 }} />
              <p>请选择一个 CSV 数据文件来在交互地图中查看和测算距离</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

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

  const { data: dataFiles } = useQuery({
    queryKey: ['dataFiles'],
    queryFn: () => fetchDataFiles(),
  })

  const { data: mapData, isLoading } = useQuery<{ data: GeocodeResult[] }>({
    queryKey: ['csvData', selectedFile],
    queryFn: async () => {
      if (!selectedFile) return { data: [] }
      const res = await fetch(`/api/file/content?path=output/csv/${encodeURIComponent(selectedFile)}`)
      if (!res.ok) return { data: [] }
      const text = await res.text()
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
    <div className="page">
      <div className="tab-bar">
        <button
          onClick={() => setTab('maps')}
          className={`tab-btn ${tab === 'maps' ? 'active' : ''}`}
        >
          <Globe size={16} /> 地图文件
        </button>
        <button
          onClick={() => setTab('files')}
          className={`tab-btn ${tab === 'files' ? 'active' : ''}`}
        >
          <FolderOpen size={16} /> 数据文件
        </button>
        <button
          onClick={() => setTab('interactive')}
          className={`tab-btn ${tab === 'interactive' ? 'active' : ''}`}
        >
          <Map size={16} /> 交互地图
        </button>
      </div>

      {tab === 'maps' && <MapFileList />}
      {tab === 'files' && <FileBrowser />}
      {tab === 'interactive' && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <label className="form-label">选择数据文件</label>
            <select
              value={selectedFile || ''}
              onChange={(e) => setSelectedFile(e.target.value)}
              className="form-input"
              style={{ display: 'inline-block', width: 'auto', minWidth: 200 }}
            >
              <option value="">-- 选择文件 --</option>
              {dataFiles?.filter(f => f.name.endsWith('.csv')).map((f) => (
                <option key={f.name} value={f.name}>{f.name}</option>
              ))}
            </select>
          </div>

          {selectedFile ? (
            isLoading ? (
              <div className="empty-state"><p>加载中...</p></div>
            ) : (
              <MapView
                data={mapData?.data || []}
                center={mapData?.data && mapData.data.length > 0 ? [mapData.data[0].latitude, mapData.data[0].longitude] : [35, 105]}
                zoom={mapData?.data && mapData.data.length > 0 ? 12 : 5}
              />
            )
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}>
              <Map size={48} style={{ marginBottom: 16, color: 'var(--text-muted)' }} />
              <p style={{ color: 'var(--text-muted)' }}>请选择一个 CSV 数据文件来在交互地图中查看和测算距离</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

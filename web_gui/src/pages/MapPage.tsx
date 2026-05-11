import { useState } from 'react'
import MapFileList from '../components/map/MapFileList'
import FileBrowser from '../components/map/FileBrowser'
import { Globe, FolderOpen } from 'lucide-react'

export default function MapPage() {
  const [tab, setTab] = useState<'maps' | 'files'>('maps')

  return (
    <div>
      <h1 style={{ fontSize: 36, fontWeight: 600, color: 'rgba(20,20,19,0.88)', lineHeight: 1.3, marginBottom: 8 }}>
        地图浏览
      </h1>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 16, marginBottom: 32 }}>
        浏览已生成的地图文件和处理数据文件
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
      </div>

      {tab === 'maps' && <MapFileList />}
      {tab === 'files' && <FileBrowser />}
    </div>
  )
}

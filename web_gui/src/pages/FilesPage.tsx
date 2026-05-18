import { useState } from 'react'
import MapFileList from '../components/map/MapFileList'
import FileBrowser from '../components/map/FileBrowser'
import { Globe, FolderOpen } from 'lucide-react'

export default function FilesPage() {
  const [tab, setTab] = useState<'output' | 'data'>('output')

  return (
    <div className="page">
      <div className="tab-bar">
        <button onClick={() => setTab('output')} className={`tab-btn ${tab === 'output' ? 'active' : ''}`}>
          <Globe size={16} /> 地图文件
        </button>
        <button onClick={() => setTab('data')} className={`tab-btn ${tab === 'data' ? 'active' : ''}`}>
          <FolderOpen size={16} /> 数据文件
        </button>
      </div>
      {tab === 'output' && <MapFileList />}
      {tab === 'data' && <FileBrowser />}
    </div>
  )
}

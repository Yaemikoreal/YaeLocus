import { useState } from 'react'
import { aiRoute } from '../../lib/api'
import { Loader2, Route, AlertTriangle } from 'lucide-react'

export default function RoutePlan() {
  const [filePath, setFilePath] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [numRoutes, setNumRoutes] = useState(3)
  const [travelMode, setTravelMode] = useState('driving')
  const [startAddress, setStartAddress] = useState('')

  const handleRoute = async () => {
    if (!filePath.trim()) return
    setResult('')
    setError('')
    setLoading(true)
    try {
      const data = await aiRoute({
        input_file: filePath.trim(),
        num_routes: numRoutes,
        travel_mode: travelMode,
        start_address: startAddress.trim() || undefined,
      })
      if (data.success) {
        setResult('路线规划完成！地图已生成到 output/map/ 目录。')
        setError('')
      } else {
        setError('路线规划失败，请检查输入文件格式')
        setResult('')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '路线规划失败')
      setResult('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="content-block">
      <h3>路线规划</h3>
      <p className="desc">AI 智能路线规划，根据地址分布推荐最优拜访路线</p>

      <div className="form-row">
        <div className="form-group" style={{ flex: 2 }}>
          <input
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="输入 CSV 文件路径，如: output/csv/结果.csv"
            disabled={loading}
            className="form-input"
            style={{ fontFamily: 'var(--font-mono)' }}
          />
        </div>
        <div className="form-group">
          <select
            value={travelMode}
            onChange={(e) => setTravelMode(e.target.value)}
            disabled={loading}
            className="form-input"
          >
            <option value="driving">驾车</option>
            <option value="transit">公交</option>
            <option value="walking">步行</option>
            <option value="bicycling">骑行</option>
          </select>
        </div>
        <div className="form-group">
          <input
            type="number"
            value={numRoutes}
            onChange={(e) => setNumRoutes(Math.max(1, Math.min(10, parseInt(e.target.value) || 3)))}
            min={1}
            max={10}
            disabled={loading}
            className="form-input"
            style={{ width: 60 }}
            title="路线数量"
          />
        </div>
        <button
          onClick={handleRoute}
          disabled={loading || !filePath.trim()}
          className="btn btn-primary"
        >
          {loading ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Route size={16} />}
          规划
        </button>
      </div>

      <div className="form-row" style={{ marginTop: 8 }}>
        <input
          type="text"
          value={startAddress}
          onChange={(e) => setStartAddress(e.target.value)}
          placeholder="起点地址（可选，留空则AI自动优化）"
          disabled={loading}
          className="form-input"
          style={{ flex: 1 }}
        />
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {result && (
        <div className="card" style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>
          {result}
        </div>
      )}
    </div>
  )
}
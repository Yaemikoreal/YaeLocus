import { useState } from 'react'
import RoutePlan from '../components/ai/RoutePlan'
import AnalysisResult from '../components/ai/AnalysisResult'
import { Route, BarChart3 } from 'lucide-react'

export default function RoutePage() {
  const [tab, setTab] = useState<'route' | 'analyze'>('route')

  return (
    <div className="page">
      <div className="tab-bar">
        <button onClick={() => setTab('route')} className={`tab-btn ${tab === 'route' ? 'active' : ''}`}>
          <Route size={16} /> 路线规划
        </button>
        <button onClick={() => setTab('analyze')} className={`tab-btn ${tab === 'analyze' ? 'active' : ''}`}>
          <BarChart3 size={16} /> 数据分析
        </button>
      </div>
      {tab === 'route' && <RoutePlan />}
      {tab === 'analyze' && <AnalysisResult />}
    </div>
  )
}

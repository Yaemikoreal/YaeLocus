import { useState } from 'react'
import ChatPanel from '../components/ai/ChatPanel'
import AnalysisResult from '../components/ai/AnalysisResult'
import RoutePlan from '../components/ai/RoutePlan'
import { MessageSquare, BarChart3, Route } from 'lucide-react'

export default function AIPage() {
  const [tab, setTab] = useState<'chat' | 'analyze' | 'route'>('chat')

  const tabs = [
    { key: 'chat' as const, label: 'AI 对话', icon: MessageSquare },
    { key: 'analyze' as const, label: '数据分析', icon: BarChart3 },
    { key: 'route' as const, label: '路线规划', icon: Route },
  ]

  return (
    <div className="page">
      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`tab-btn ${tab === t.key ? 'active' : ''}`}
          >
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'chat' && <ChatPanel />}
      {tab === 'analyze' && <AnalysisResult />}
      {tab === 'route' && <RoutePlan />}
    </div>
  )
}

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
    <div>
      <h1 style={{ fontSize: 36, fontWeight: 600, color: 'rgba(20,20,19,0.88)', lineHeight: 1.3, marginBottom: 8 }}>
        AI 助手
      </h1>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 16, marginBottom: 32 }}>
        使用 AI 分析数据、规划路线、智能对话
      </p>

      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid #eae8e7' }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '10px 20px', fontSize: 14, fontWeight: tab === t.key ? 600 : 400,
              color: tab === t.key ? '#ff9d4d' : '#6b6b6b', background: 'none', border: 'none',
              borderBottom: tab === t.key ? '2px solid #ff9d4d' : '2px solid transparent',
              cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6,
            }}
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

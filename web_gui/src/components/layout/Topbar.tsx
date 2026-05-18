import { useLocation } from 'react-router-dom'

const PAGE_META: Record<string, { title: string; desc: string }> = {
  '/': { title: '地理编码', desc: '单地址 / 逆地理编码 / 智能补全' },
  '/batch': { title: '批量处理', desc: 'Excel / CSV 批量地址转换' },
  '/reverse': { title: '逆地理编码', desc: '坐标 → 地址解析' },
  '/convert': { title: '坐标转换', desc: 'WGS-84 / GCJ-02 / BD-09 双向转换' },
  '/map': { title: '地图可视化', desc: '交互式地图 · 热力图 · 路线叠加' },
  '/ai': { title: 'AI 对话', desc: '智能地理数据分析助手' },
  '/route': { title: '路线规划', desc: '多模式路径规划 · AI + API 双引擎' },
  '/optimize': { title: '行程优化', desc: 'DBSCAN 聚类 + TSP 求解器' },
  '/history': { title: '历史记录', desc: '查看和管理所有编码任务' },
  '/files': { title: '文件管理', desc: '输入数据与输出结果浏览' },
  '/cache': { title: '缓存管理', desc: '内存 LRU + SQLite 持久化' },
  '/config': { title: '系统配置', desc: 'API 密钥 / AI 供应商 / 环境诊断' },
}

interface TopbarProps {
  onMenuClick: () => void
}

export default function Topbar({ onMenuClick }: TopbarProps) {
  const location = useLocation()
  const meta = PAGE_META[location.pathname] || { title: '', desc: '' }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="mobile-menu-btn" onClick={onMenuClick} aria-label="打开菜单">
          <i className="fa-solid fa-bars" />
        </button>
        <span className="topbar-title">{meta.title}</span>
        <span className="topbar-desc">{meta.desc}</span>
      </div>
      <div className="topbar-right">
        <button className="topbar-btn" title="快捷键">
          <i className="fa-solid fa-keyboard" />
        </button>
        <button className="topbar-btn" title="帮助">
          <i className="fa-regular fa-circle-question" />
        </button>
      </div>
    </header>
  )
}

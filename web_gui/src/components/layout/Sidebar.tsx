import { NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../lib/api'

const NAV_SECTIONS: { title: string; badge?: string; items: { to: string; label: string; icon: string; end?: boolean; badge?: string }[] }[] = [
  {
    title: '核心功能',
    items: [
      { to: '/', label: '地理编码', icon: 'fa-solid fa-location-dot', end: true },
      { to: '/batch', label: '批量处理', icon: 'fa-solid fa-layer-group', badge: 'Pro' },
      { to: '/convert', label: '坐标转换', icon: 'fa-solid fa-arrows-rotate' },
    ],
  },
  {
    title: '智能分析',
    badge: 'Beta',
    items: [
      { to: '/ai', label: 'AI 对话', icon: 'fa-solid fa-wand-magic-sparkles' },
      { to: '/route', label: '路线规划', icon: 'fa-solid fa-route' },
      { to: '/optimize', label: '行程优化', icon: 'fa-solid fa-diagram-project' },
    ],
  },
  {
    title: '管理',
    items: [
      { to: '/history', label: '历史记录', icon: 'fa-solid fa-clock-rotate-left' },
      { to: '/files', label: '文件管理', icon: 'fa-solid fa-folder-open' },
      { to: '/cache', label: '缓存管理', icon: 'fa-solid fa-database' },
      { to: '/config', label: '系统配置', icon: 'fa-solid fa-gear' },
    ],
  },
]

interface SidebarProps {
  mobileOpen: boolean
  onClose: () => void
}

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
    retry: false,
  })

  const apisOk = health?.apis?.length ?? 0
  const location = useLocation()

  const handleNavClick = () => {
    if (window.innerWidth <= 768) {
      onClose()
    }
  }

  return (
    <>
      <div
        className={`sidebar-overlay ${mobileOpen ? 'open' : ''}`}
        onClick={onClose}
      />
      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">
              <i className="fa-solid fa-map-marker-alt" />
            </div>
            <div className="brand-text">
              <div className="brand-title">YaeLocus</div>
              <div className="brand-subtitle">Geocoding Platform</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <div className="nav-section-title">
                {section.title}
                {section.badge && <span className="nav-beta">{section.badge}</span>}
              </div>
              {section.items.map((item) => {
                const isActive = item.end
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.to)
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={`nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                  >
                    <i className={item.icon} />
                    <span>{item.label}</span>
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="api-status">
            <div className={`status-dot ${apisOk > 0 ? 'online' : 'offline'}`} />
            <span>{apisOk > 0 ? 'API 服务运行中' : 'API 未配置'}</span>
          </div>
        </div>
      </aside>
    </>
  )
}

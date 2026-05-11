import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../lib/api'
import { MapPin, Globe, MessageSquare, Settings, Activity } from 'lucide-react'

const navLinkStyle = (isActive: boolean): React.CSSProperties => ({
  color: isActive ? '#ff9d4d' : 'rgba(0,0,0,0.65)',
  textDecoration: 'none',
  padding: '16px 16px',
  fontSize: 14,
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  borderBottom: isActive ? '2px solid #ff9d4d' : '2px solid transparent',
  transition: 'all 0.2s',
  fontWeight: isActive ? 600 : 400,
})

export default function Navbar() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
    retry: false,
  })

  const apisOk = health?.apis?.length ?? 0

  return (
    <nav
      style={{
        background: '#fff',
        height: 65,
        position: 'sticky',
        top: 0,
        zIndex: 50,
        borderBottom: '1px solid #eae8e7',
      }}
    >
      <div
        style={{
          maxWidth: '64rem',
          margin: '0 auto',
          padding: '0 32px',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <NavLink
          to="/"
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: '#1c1c1c',
            textDecoration: 'none',
            marginRight: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <MapPin size={22} style={{ color: '#ff9d4d' }} />
          YaeLocus
        </NavLink>

        <NavLink to="/" end style={({ isActive }) => navLinkStyle(isActive)}>
          <MapPin size={16} /> 地理编码
        </NavLink>
        <NavLink to="/map" style={({ isActive }) => navLinkStyle(isActive)}>
          <Globe size={16} /> 地图浏览
        </NavLink>
        <NavLink to="/ai" style={({ isActive }) => navLinkStyle(isActive)}>
          <MessageSquare size={16} /> AI 助手
        </NavLink>
        <NavLink to="/config" style={({ isActive }) => navLinkStyle(isActive)}>
          <Settings size={16} /> 配置
        </NavLink>

        <div
          style={{
            marginLeft: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: '#6b6b6b',
          }}
          title={`已配置 ${apisOk} 个 API`}
        >
          <Activity size={14} style={{ color: apisOk > 0 ? '#1e8e3e' : '#d93025' }} />
          <span>{apisOk > 0 ? `${apisOk} API` : '未配置'}</span>
        </div>
      </div>
    </nav>
  )
}

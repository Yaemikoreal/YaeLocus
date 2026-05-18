import type { ReactNode } from 'react'
import { useState } from 'react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="app-layout">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="main-content">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <div className="page-container">
          {children}
        </div>
      </div>
    </div>
  )
}

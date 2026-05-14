import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../lib/api'
import Navbar from './Navbar'

export default function Layout({ children }: { children: ReactNode }) {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    staleTime: 30_000,
    retry: false,
  })

  return (
    <>
      <Navbar />
      <main
        style={{
          flex: 1,
          width: 'min(100% - 32px, 64rem)',
          margin: '0 auto',
          padding: '32px 0 64px',
        }}
      >
        {children}
      </main>
      <footer
        style={{
          textAlign: 'center',
          padding: '32px',
          color: '#999',
          fontSize: 13,
          borderTop: '1px solid #eae8e7',
        }}
      >
        YaeLocus v{health?.version || '?.?.?'} · Web GUI ·{' '}
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener"
          style={{ color: '#ff9d4d', textDecoration: 'none' }}
        >
          GitHub
        </a>
      </footer>
    </>
  )
}

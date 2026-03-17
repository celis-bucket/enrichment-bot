import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Monitor de Crisis Logística — Melonn',
  description: 'Monitoreo semanal de quejas logísticas en Instagram para el equipo de adquisición',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <link rel="stylesheet" href="/melonn-design-system.css" />
      </head>
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="sidebar-logo">
              <span className="text-gradient" style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--font-bold)' }}>
                Melonn
              </span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', display: 'block' }}>
                Crisis Monitor
              </span>
            </div>
            <nav className="sidebar-nav">
              <a href="/" className="sidebar-item active">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
                </svg>
                Dashboard
              </a>
            </nav>
            <div className="sidebar-footer">
              <DarkModeToggle />
            </div>
          </aside>
          <main className="app-main">
            <div className="page-content">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  )
}

function DarkModeToggle() {
  return (
    <button
      className="btn btn-ghost btn-sm"
      id="dark-mode-toggle"
      style={{ width: '100%', justifyContent: 'flex-start', gap: 'var(--space-2)' }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
      Modo oscuro
    </button>
  )
}

import { useLiveSync } from '../hooks/useLiveSync'
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { GlobalSidebar } from '../components/navigation/GlobalSidebar'
import { TopHeader } from '../components/navigation/TopHeader'
import { ErrorBoundary } from '../components/layout/ErrorBoundary'
import { ToastViewport } from '../components/ui'

const DESKTOP_QUERY = '(min-width: 1024px)'

export function AppLayout() {
  useLiveSync() // WebSocket messages keep every page's data fresh without polling
  // Desktop: collapse to icon rail. Mobile: slide-in drawer.
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setDrawerOpen(false)
  }, [location.pathname])

  const toggleSidebar = () => {
    if (window.matchMedia(DESKTOP_QUERY).matches) setCollapsed((prev) => !prev)
    else setDrawerOpen((prev) => !prev)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary text-text-primary">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <GlobalSidebar collapsed={collapsed} drawerOpen={drawerOpen} onCloseDrawer={() => setDrawerOpen(false)} />

      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <TopHeader onToggleSidebar={toggleSidebar} drawerOpen={drawerOpen} />

        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto px-4 pb-10 pt-4 outline-none md:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl space-y-6">
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <ToastViewport />
    </div>
  )
}

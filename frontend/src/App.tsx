import React, { Suspense, lazy } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import './App.css'

const Search = lazy(() => import('./pages/Search'))
const Browse = lazy(() => import('./pages/Browse'))
const Settings = lazy(() => import('./pages/Settings'))

function PageFallback() {
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)' }}>
      Loading...
    </div>
  )
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error.message, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            style={{
              padding: 40,
              textAlign: 'center',
              color: 'var(--danger)',
              maxWidth: 600,
              margin: '0 auto',
            }}
          >
            <div style={{ fontSize: 14, marginBottom: 8 }}>Something went wrong</div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                marginBottom: 12,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {this.state.error?.message ?? 'Unknown error'}
            </div>
            <details style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 12, textAlign: 'left' }}>
              <summary>Stack trace</summary>
              <pre style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>
                {this.state.error?.stack ?? 'No stack available'}
              </pre>
            </details>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                padding: '6px 16px',
                background: 'var(--accent)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Try again
            </button>
          </div>
        )
      )
    }
    return this.props.children
  }
}

function App() {
  return (
    <div className="app">
      <nav className="top-nav" aria-label="Main navigation">
        <div className="nav-brand">Sample DNA</div>
        <NavLink to="/search" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Search
        </NavLink>
        <NavLink to="/browse" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Browse
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Settings
        </NavLink>
        <div className="nav-spacer" />
        <div className="nav-stats">Sample DNA Tagger</div>
      </nav>

      <main className="main-content">
        <ErrorBoundary>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Search />} />
              <Route path="/search" element={<Search />} />
              <Route path="/browse" element={<Browse />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App

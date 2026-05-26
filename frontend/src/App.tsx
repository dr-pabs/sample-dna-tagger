import React, { Suspense, lazy, useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { AudioManagerProvider } from './components/AudioManager'
import './App.css'

const Search = lazy(() => import('./pages/Search'))
const Browse = lazy(() => import('./pages/Browse'))
const Settings = lazy(() => import('./pages/Settings'))

const GITHUB_RELEASES_API = 'https://api.github.com/repos/dr-pabs/sample-dna-tagger/releases/latest';

function UpdateBanner() {
  const [update, setUpdate] = useState<{ available: boolean; url: string; version: string } | null>(null)

  useEffect(() => {
    const check = async () => {
      try {
        const [localRes, remoteRes] = await Promise.all([
          fetch('/api/version').then(r => r.json()).catch(() => ({ version: '0.1.0' })),
          fetch(GITHUB_RELEASES_API, { headers: { Accept: 'application/vnd.github+json' } })
            .then(r => r.ok ? r.json() : null)
            .catch(() => null),
        ])
        if (!remoteRes || !remoteRes.tag_name) return
        const local = localRes.version || '0.1.0'
        const remote = remoteRes.tag_name.replace(/^v/, '')
        if (remote > local) {
          setUpdate({ available: true, url: remoteRes.html_url, version: remote })
        }
      } catch {
        // silently ignore network errors
      }
    }
    check()
  }, [])

  if (!update) return null

  return (
    <div
      style={{
        background: 'rgba(99,102,241,0.15)',
        borderBottom: '1px solid var(--accent)',
        padding: '6px 20px',
        fontSize: 12,
        color: 'var(--accent)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>🎉</span>
      <span>
        <strong>Update available:</strong> v{update.version} is ready.
      </span>
      <a
        href={update.url}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: 'var(--accent)', textDecoration: 'underline' }}
      >
        Download
      </a>
      <button
        onClick={() => setUpdate(null)}
        style={{
          marginLeft: 'auto',
          background: 'none',
          border: 'none',
          color: 'var(--text-dim)',
          cursor: 'pointer',
          fontSize: 12,
        }}
        aria-label="Dismiss update"
      >
        ✕
      </button>
    </div>
  )
}

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
      <UpdateBanner />
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
        <AudioManagerProvider>
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
        </AudioManagerProvider>
      </main>
    </div>
  )
}

export default App

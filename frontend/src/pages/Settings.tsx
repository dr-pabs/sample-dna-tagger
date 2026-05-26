import { useState, useEffect } from 'react'
import {
  SettingsResponse,
  getSettings,
  updateSettings,
  testLLMConnection,
  startScan,
  addScanRoot,
  removeScanRoot,
  rescanRoot,
} from '../api'

// ── Provider presets ────────────────────────────────────────────────

interface ProviderPreset {
  label: string
  base_url: string
  model: string
}

const PRESETS: ProviderPreset[] = [
  { label: 'Deepseek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: 'Kimi (Moonshot)', base_url: 'https://api.moonshot.ai/v1', model: 'moonshot-v1-8k' },
  { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4.1-mini' },
  { label: 'Ollama (local)', base_url: 'http://localhost:11434/v1', model: 'llama3.2' },
  { label: 'Custom', base_url: '', model: '' },
]

type SettingsTab = 'library' | 'ai' | 'about'

// ── Module-level styles ─────────────────────────────────────────────

const TAB_BTN = {
  padding: '6px 10px',
  borderRadius: 6,
  cursor: 'pointer',
  marginBottom: 2,
  border: 'none',
  background: 'none',
  color: 'var(--text-muted)',
  fontSize: 12,
  textAlign: 'left' as const,
  width: '100%',
  fontFamily: 'inherit',
} as React.CSSProperties

const TAB_BTN_ACTIVE = {
  ...TAB_BTN,
  background: 'var(--tag-bg)',
  color: 'var(--text-secondary)',
} as React.CSSProperties

const WATCH_ROW = {
  background: 'var(--surface-1)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: '10px 12px',
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  marginBottom: 4,
} as React.CSSProperties

// ── Component ───────────────────────────────────────────────────────

export default function Settings() {
  const [tab, setTab] = useState<SettingsTab>('library')
  const [data, setData] = useState<SettingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [provider, setProvider] = useState('Deepseek')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [testErrorMsg, setTestErrorMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [scanning, setScanning] = useState(false)
  const [newFolderPath, setNewFolderPath] = useState('')

  const handleAddFolder = async () => {
    const path = newFolderPath.trim()
    if (!path) return
    try {
      await addScanRoot(path)
      setNewFolderPath('')
      // Refresh settings to show new folder
      const refreshed = await getSettings()
      setData(refreshed)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleRemoveFolder = async (rootId: string) => {
    if (!confirm('Remove this watch folder? Its samples will be deleted from the library.')) return
    try {
      await removeScanRoot(rootId)
      const refreshed = await getSettings()
      setData(refreshed)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleRescanFolder = async (rootId: string) => {
    try {
      await rescanRoot(rootId)
      const refreshed = await getSettings()
      setData(refreshed)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getSettings()
      .then((res) => {
        if (cancelled) return
        setData(res)
        setProvider(res.provider || 'Deepseek')
        setModel(res.model || '')
        setBaseUrl(res.base_url || '')
        setApiKey(res.api_key || '')
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handlePreset = (label: string) => {
    setProvider(label)
    const preset = PRESETS.find((p) => p.label === label)
    if (preset) {
      setBaseUrl(preset.base_url)
      setModel(preset.model)
    }
  }

  // Save & test in one action
  const handleSaveAndTest = async () => {
    setTestStatus('testing')
    setTestErrorMsg(null)
    setSaving(true)
    try {
      await updateSettings({ provider, model, base_url: baseUrl, api_key: apiKey })
      const res = await testLLMConnection()
      if (res.ok) {
        setTestStatus('ok')
      } else {
        setTestStatus('fail')
        setTestErrorMsg(res.error || 'Connection failed')
      }
    } catch (err) {
      setTestStatus('fail')
      setTestErrorMsg((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleScan = async () => {
    setScanning(true)
    try {
      const status = await startScan()
      if (data) {
        setData({ ...data, scan_status: status })
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setScanning(false)
    }
  }

  const fmtRelative = (ts: string | null): string => {
    if (!ts) return 'Never'
    const diff = Date.now() - new Date(ts).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
    const days = Math.floor(hrs / 24)
    return `${days} day${days > 1 ? 's' : ''} ago`
  }

  if (loading) {
    return (
      <div className="page">
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)' }}>
          Loading settings...
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div style={{ display: 'flex', height: '100%' }}>
        {/* ── Settings nav ─────────────────────────────────────── */}
        <nav
          aria-label="Settings sections"
          style={{
            width: 160,
            borderRight: '1px solid var(--border-color)',
            background: 'var(--surface-0)',
            padding: '10px 8px',
            flexShrink: 0,
          }}
        >
          {(['library', 'ai', 'about'] as SettingsTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={tab === t ? TAB_BTN_ACTIVE : TAB_BTN}
              aria-pressed={tab === t}
            >
              {t === 'library' ? 'Library' : t === 'ai' ? 'AI Provider' : 'About'}
            </button>
          ))}
        </nav>

        {/* ── Content area ─────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
          }}
          aria-live="polite"
        >
          {/* Global error */}
          {error && (
            <div
              role="alert"
              style={{
                padding: '8px 12px',
                background: 'rgba(248,113,113,0.1)',
                border: '1px solid var(--danger)',
                borderRadius: 6,
                color: 'var(--danger)',
                fontSize: 11,
              }}
            >
              {error}
            </div>
          )}

          {/* ── Library ────────────────────────────────────────── */}
          {tab === 'library' && (
            <div>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                Watch folders
              </h2>
              <p style={{ color: 'var(--text-dim)', fontSize: 11, marginBottom: 12 }}>
                The scanner monitors these folders for new and changed files. Subfolders are included automatically.
              </p>

              <div style={{ marginBottom: 10 }}>
                {(data?.watch_folders ?? []).map((wf) => (
                  <div key={wf.id} style={WATCH_ROW}>
                    <span style={{ color: 'var(--accent)', fontSize: 14 }} aria-hidden="true">📁</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {wf.path}
                      </div>
                      <div style={{ color: 'var(--text-dim)', fontSize: 10, marginTop: 2 }}>
                        Last scanned: {fmtRelative(wf.last_scanned)} · {wf.file_count.toLocaleString()} files
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                      <button
                        style={{ color: 'var(--accent)', cursor: 'pointer', fontSize: 11, background: 'none', border: 'none' }}
                        onClick={() => handleRescanFolder(wf.id)}
                        aria-label={`Rescan ${wf.path}`}
                      >
                        Rescan
                      </button>
                      <button
                        style={{ color: 'var(--danger)', cursor: 'pointer', fontSize: 11, background: 'none', border: 'none' }}
                        onClick={() => handleRemoveFolder(wf.id)}
                        aria-label={`Remove ${wf.path}`}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                  <Label htmlFor="new-folder-path">Folder path</Label>
                  <input
                    id="new-folder-path"
                    type="text"
                    value={newFolderPath}
                    onChange={(e) => setNewFolderPath(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddFolder() }}
                    placeholder="/Users/you/Samples"
                    style={{
                      width: '100%',
                      background: 'var(--surface-1)',
                      border: '1px solid #2d2d50',
                      borderRadius: 6,
                      padding: '7px 10px',
                      color: 'var(--text-primary)',
                      fontSize: 12,
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
                <button
                  onClick={handleAddFolder}
                  disabled={!newFolderPath.trim()}
                  style={{
                    background: newFolderPath.trim() ? 'var(--accent)' : 'rgba(99,102,241,0.12)',
                    border: newFolderPath.trim() ? 'none' : '1px dashed rgba(99,102,241,0.4)',
                    color: newFolderPath.trim() ? 'white' : 'var(--text-dim)',
                    borderRadius: 6,
                    padding: '7px 14px',
                    cursor: newFolderPath.trim() ? 'pointer' : 'default',
                    fontSize: 11,
                    whiteSpace: 'nowrap',
                  }}
                >
                  Add
                </button>
              </div>

              {/* Scan status */}
              <div style={{ marginTop: 24 }}>
                <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  Scan status
                </h2>
                <div
                  style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 8,
                    padding: '12px 14px',
                  }}
                  aria-live="polite"
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ color: statusColor(data?.scan_status?.state ?? 'idle'), fontSize: 11 }}>
                      ● {data?.scan_status?.state ?? 'idle'} — {data?.scan_status?.state === 'scanning' ? 'Scanning in progress' : 'All files up to date'}
                    </span>
                    <button
                      onClick={handleScan}
                      disabled={scanning}
                      style={{
                        color: 'var(--accent)',
                        cursor: scanning ? 'default' : 'pointer',
                        fontSize: 11,
                        opacity: scanning ? 0.6 : 1,
                      }}
                    >
                      {scanning ? 'Scanning...' : 'Scan all now'}
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: 16 }}>
                    <StatBox value={data?.scan_status?.indexed ?? 0} label="Indexed" color="var(--text-secondary)" />
                    <StatBox value={data?.scan_status?.tagged ?? 0} label="Tagged" color="var(--success)" />
                    <StatBox value={data?.scan_status?.queued ?? 0} label="Queued" color="var(--warning)" />
                    <StatBox value={data?.scan_status?.errors ?? 0} label="Errors" color="var(--danger)" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── AI Provider ────────────────────────────────────── */}
          {tab === 'ai' && (
            <div>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                AI provider
              </h2>
              <p style={{ color: 'var(--text-dim)', fontSize: 11, marginBottom: 16 }}>
                Choose a preset or enter custom endpoint details. Click "Save &amp; Test" to verify.
              </p>

              {/* Current status */}
              {testStatus === 'idle' && data?.api_key && (
                <div style={{
                  background: 'var(--surface-1)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  marginBottom: 16,
                  fontSize: 11,
                  color: 'var(--text-muted)',
                }}>
                  Currently: <strong style={{ color: 'var(--text-secondary)' }}>{data.provider || provider}</strong>
                  {' → '}
                  <span style={{ color: 'var(--text-dim)', fontFamily: 'monospace' }}>{data.model || model}</span>
                  {data.base_url && <span style={{ color: 'var(--text-dim)' }}> @ {data.base_url}</span>}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Provider preset */}
                <div>
                  <Label htmlFor="provider-preset">Provider</Label>
                  <p style={{ color: 'var(--text-dim)', fontSize: 10, marginBottom: 6 }}>
                    Select a preset to auto-fill Base URL and Model below.
                  </p>
                  <Select id="provider-preset" value={provider} onChange={(e) => handlePreset(e.target.value)}>
                    {PRESETS.map((p) => (
                      <option key={p.label} value={p.label}>{p.label}</option>
                    ))}
                  </Select>
                </div>

                {/* Model */}
                <div>
                  <Label htmlFor="model-name">Model name</Label>
                  <Input id="model-name" value={model} onChange={(e) => setModel(e.target.value)} style={{ width: '100%' }} />
                </div>

                {/* Base URL */}
                <div>
                  <Label htmlFor="base-url">Base URL</Label>
                  <Input id="base-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} style={{ width: '100%' }} />
                </div>

                {/* API Key */}
                <div>
                  <Label htmlFor="api-key">API key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    style={{ width: '100%' }}
                  />
                </div>

                {/* Save & Test button */}
                <button
                  onClick={handleSaveAndTest}
                  disabled={testStatus === 'testing' || saving}
                  style={{
                    background: 'var(--accent)',
                    border: 'none',
                    borderRadius: 6,
                    padding: '10px 20px',
                    color: 'white',
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: (testStatus === 'testing' || saving) ? 'default' : 'pointer',
                    opacity: (testStatus === 'testing' || saving) ? 0.6 : 1,
                    alignSelf: 'flex-start',
                  }}
                >
                  {testStatus === 'testing' ? '⏳ Testing...' : '💾 Save & Test Connection'}
                </button>

                {/* Test result */}
                {testStatus === 'ok' && (
                  <div role="status" style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: '#0d2d1a', border: '1px solid #166534',
                    borderRadius: 6, padding: '8px 12px',
                  }}>
                    <span style={{ color: 'var(--success)' }}>✓</span>
                    <span style={{ color: 'var(--success)', fontSize: 11 }}>
                      Connected — {model} responding
                    </span>
                  </div>
                )}
                {testStatus === 'fail' && (
                  <div role="alert" style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: 'rgba(248,113,113,0.1)', border: '1px solid var(--danger)',
                    borderRadius: 6, padding: '8px 12px',
                  }}>
                    <span style={{ color: 'var(--danger)' }}>✕</span>
                    <span style={{ color: 'var(--danger)', fontSize: 11 }}>
                      {testErrorMsg || 'Connection failed'}
                    </span>
                  </div>
                )}

                {testStatus === 'idle' && !data?.api_key && (
                  <div style={{
                    color: 'var(--text-dim)', fontSize: 10, fontStyle: 'italic',
                  }}>
                    Enter your API key and click "Save &amp; Test" to verify the connection.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── About ──────────────────────────────────────────── */}
          {tab === 'about' && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.6 }}>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
                About
              </h2>
              <p style={{ marginBottom: 8 }}>
                <strong style={{ color: 'var(--text-primary)' }}>Sample DNA Tagger</strong> v0.1.0
              </p>
              <p style={{ marginBottom: 8 }}>
                AI-powered sample library tagging and search for music producers. Built with
                FastAPI, React, and pywebview.
              </p>
              <p style={{ marginBottom: 8 }}>
                Local audio analysis via librosa + Essentia. Expressive AI tagging via any
                OpenAI-compatible LLM endpoint.
              </p>
              <p style={{ marginTop: 16, color: 'var(--text-dim)', fontSize: 11 }}>
                © 2026 Sample DNA Tagger Contributors
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Mini components ─────────────────────────────────────────────────

function Label({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label
      htmlFor={htmlFor}
      style={{
        display: 'block',
        fontSize: 10,
        color: 'var(--text-muted)',
        marginBottom: 4,
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}
    >
      {children}
    </label>
  )
}

function Input({
  id,
  value,
  onChange,
  type,
  style,
}: {
  id?: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  type?: string
  style?: React.CSSProperties
}) {
  return (
    <input
      id={id}
      type={type ?? 'text'}
      value={value}
      onChange={onChange}
      style={{
        background: 'var(--surface-1)',
        border: '1px solid #2d2d50',
        borderRadius: 6,
        padding: '7px 10px',
        color: 'var(--text-primary)',
        fontSize: 12,
        outline: 'none',
        boxSizing: 'border-box',
        ...style,
      }}
    />
  )
}

function Select({
  id,
  value,
  onChange,
  children,
}: {
  id?: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void
  children: React.ReactNode
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={onChange}
      style={{
        width: '100%',
        background: 'var(--surface-1)',
        border: '1px solid #2d2d50',
        borderRadius: 6,
        padding: '7px 10px',
        color: 'var(--text-primary)',
        fontSize: 12,
        outline: 'none',
      }}
    >
      {children}
    </select>
  )
}

function StatBox({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 16, fontWeight: 700, color }}>{value.toLocaleString()}</div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{label}</div>
    </div>
  )
}

function statusColor(state: string): string {
  switch (state) {
    case 'scanning': return 'var(--accent)'
    case 'error': return 'var(--danger)'
    default: return 'var(--success)'
  }
}

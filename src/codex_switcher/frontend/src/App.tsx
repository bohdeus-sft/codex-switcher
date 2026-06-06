import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactElement } from 'react'
import './App.css'
import { resolveApiBase } from './apiBase'

type LimitWindow = {
  remaining: number | null
  reset: string
  resetsAt?: number | null
  error?: string
}

type Session = {
  id: string
  key: string
  account: string
  category: string
  displayCategory?: string
  fingerprint: string
  active: boolean
  capturedAt: string
  fiveHour: LimitWindow | null
  weekly: LimitWindow | null
}

type BackendState = {
  sessions: Session[]
  activeAuthExists: boolean
  paths: {
    auth: string
    sessions: string
    cache: string
  }
}

type ActivityLog = {
  timestamp: string
  method?: string
  path?: string
  status?: number | null
  statusText?: string
  durationMs?: number
  requestBody?: unknown
  responseBody?: unknown
  serverMessage?: string
  errorName?: string
  errorMessage?: string
  errorStack?: string
  cause?: string
  note?: string
}

type Activity = {
  id: number
  tone: 'success' | 'warning' | 'neutral'
  title: string
  detail: string
  log?: ActivityLog
}

type IconName =
  | 'archive'
  | 'capture'
  | 'check'
  | 'clock'
  | 'folder'
  | 'log'
  | 'plus'
  | 'refresh'
  | 'shield'
  | 'switch'
  | 'trash'

const API_BASE = resolveApiBase(window.location, import.meta.env.VITE_API_BASE_URL)

console.info('[codex-switcher] frontend booted', {
  apiBase: API_BASE || '(same-origin)',
  location: window.location.href,
})

class ApiError extends Error {
  readonly method: string
  readonly path: string
  readonly status: number | null
  readonly statusText: string
  readonly requestBody?: unknown
  readonly responseBody?: unknown
  readonly durationMs: number
  readonly cause?: unknown

  constructor(init: {
    method: string
    path: string
    status: number | null
    statusText: string
    requestBody?: unknown
    responseBody?: unknown
    durationMs: number
    detail: string
    cause?: unknown
  }) {
    const prefix = `${init.method} ${init.path}`
    const message =
      init.status === null
        ? `${prefix} → network error: ${init.detail}`
        : `${prefix} → ${init.status}: ${init.detail}`
    super(message)
    this.name = 'ApiError'
    this.method = init.method
    this.path = init.path
    this.status = init.status
    this.statusText = init.statusText
    this.requestBody = init.requestBody
    this.responseBody = init.responseBody
    this.durationMs = init.durationMs
    this.cause = init.cause
  }
}

const initialSessions: Session[] = [
  {
    id: 'work/account-a@example.com',
    key: 'work/account-a@example.com',
    account: 'account-a@example.com',
    category: 'work',
    displayCategory: 'work',
    fingerprint: '4f6a...91c2',
    active: true,
    capturedAt: 'May 13 00:12',
    fiveHour: { remaining: 72, reset: '02:40' },
    weekly: { remaining: 54, reset: 'Mon 09:00' },
  },
  {
    id: 'personal/account-b@example.com',
    key: 'personal/account-b@example.com',
    account: 'account-b@example.com',
    category: 'personal',
    displayCategory: 'personal',
    fingerprint: '9bb2...a814',
    active: false,
    capturedAt: 'May 13 00:19',
    fiveHour: { remaining: 41, reset: '01:18' },
    weekly: { remaining: 88, reset: 'Sun 18:00' },
  },
  {
    id: 'tests/account-c@example.com',
    key: 'tests/account-c@example.com',
    account: 'account-c@example.com',
    category: 'tests',
    displayCategory: 'tests',
    fingerprint: 'c102...70de',
    active: false,
    capturedAt: 'May 13 00:27',
    fiveHour: null,
    weekly: null,
  },
]

const initialActivity: Activity[] = [
  {
    id: 3,
    tone: 'success',
    title: 'Frontend ready',
    detail: 'Start the backend to control real Codex auth files from this UI.',
  },
  {
    id: 2,
    tone: 'neutral',
    title: 'Backend endpoint',
    detail: API_BASE || 'Using same-origin /api endpoints.',
  },
]

const categoryLabel = (value: string) => value || 'default'

function splitAccount(account: string): { friendly: string | null; codex: string } {
  const idx = account.indexOf('+')
  if (idx === -1) return { friendly: null, codex: account }
  return { friendly: account.slice(0, idx), codex: account.slice(idx + 1) }
}

function App() {
  const [sessions, setSessions] = useState(initialSessions)
  const [activity, setActivity] = useState(initialActivity)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [captureOpen, setCaptureOpen] = useState(false)
  const [captureFriendly, setCaptureFriendly] = useState('')
  const [captureCodex, setCaptureCodex] = useState('')
  const [captureCategory, setCaptureCategory] = useState('')
  const [backendState, setBackendState] = useState<BackendState | null>(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const pushActivity = useCallback((entry: Omit<Activity, 'id'>) => {
    setActivity((current) => [{ ...entry, id: Date.now() }, ...current].slice(0, 7))
  }, [])

  const loadState = useCallback(async () => {
    try {
      const state = await request<BackendState>('/api/state')
      setBackendState(state)
      setSessions(state.sessions.map(normalizeSession))
      setBackendOnline(true)
    } catch (error) {
      setBackendOnline(false)
      console.error('[codex-switcher] state load failed', { error })
      pushActivity({
        tone: 'warning',
        title: 'Backend unavailable',
        detail: formatErrorDetail(error),
        log: logFromError(error),
      })
    }
  }, [pushActivity])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadState()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadState])

  const activeSession = sessions.find((session) => session.active) ?? null
  const captureCategories = useMemo(
    () =>
      Array.from(
        new Set(sessions.map((session) => session.category.trim()).filter((value) => value.length > 0)),
      ).sort(),
    [sessions],
  )
  const categories = useMemo(
    () => ['all', ...Array.from(new Set(sessions.map((session) => categoryLabel(session.category))))],
    [sessions],
  )
  const filteredSessions = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return sessions.filter((session) => {
      const matchesQuery =
        !needle ||
        session.account.toLowerCase().includes(needle) ||
        categoryLabel(session.category).toLowerCase().includes(needle) ||
        session.fingerprint.toLowerCase().includes(needle)
      const matchesCategory = category === 'all' || categoryLabel(session.category) === category
      return matchesQuery && matchesCategory
    })
  }, [category, query, sessions])

  const stats = useMemo(() => {
    const captured = sessions.length
    const loadedLimits = sessions.filter((session) => session.fiveHour || session.weekly).length
    const staleLimits = captured - loadedLimits
    return { captured, loadedLimits, staleLimits }
  }, [sessions])

  const runAction = async (
    title: string,
    action: () => Promise<{ data: { message?: string }; log: ActivityLog }>,
    fallback?: () => void,
    tone: Activity['tone'] = 'success',
  ) => {
    if (!backendOnline) {
      fallback?.()
      pushActivity({
        tone: 'warning',
        title: `${title} simulated`,
        detail: 'Backend is offline, so only the visible demo state changed.',
        log: { timestamp: new Date().toISOString(), note: 'backend offline; no request made' },
      })
      return
    }

    setBusy(title)
    try {
      const { data, log } = await action()
      await loadState()
      pushActivity({
        tone,
        title,
        detail: data.message || 'Backend operation completed.',
        log,
      })
    } catch (error) {
      console.error('[codex-switcher] action failed', { title, error })
      pushActivity({
        tone: 'warning',
        title: `${title} failed`,
        detail: formatErrorDetail(error),
        log: logFromError(error),
      })
    } finally {
      setBusy(null)
    }
  }

  const switchToSession = (id: string) => {
    const target = sessions.find((session) => session.id === id)
    if (!target) return
    void runAction(
      `Switched to ${target.account}`,
      () => requestWithLog('/api/sessions/switch', { method: 'POST', body: { key: target.key } }),
      () => setSessions((current) => current.map((session) => ({ ...session, active: session.id === id }))),
    )
  }

  const prepareLogin = () => {
    void runAction(
      'Prepared clean login',
      () => requestWithLog('/api/auth/prepare-login', { method: 'POST' }),
      () => setSessions((current) => current.map((session) => ({ ...session, active: false }))),
      'warning',
    )
  }

  const openPathInFinder = (key: 'auth' | 'sessions') => {
    void runAction(
      key === 'auth' ? 'Revealed active auth.json in Finder' : 'Opened sessions folder in Finder',
      () => requestWithLog('/api/paths/open', { method: 'POST', body: { key } }),
      undefined,
      'neutral',
    )
  }

  const triggerCodexLogin = () => {
    void runAction(
      'Triggered Codex login',
      () =>
        requestWithLog('/api/auth/prepare-login', {
          method: 'POST',
          body: { openCodex: true },
        }),
      () => setSessions((current) => current.map((session) => ({ ...session, active: false }))),
      'neutral',
    )
  }

  const forgetSession = (id: string) => {
    const target = sessions.find((session) => session.id === id)
    if (!target) return
    void runAction(
      `Removed saved session ${target.account}`,
      () => requestWithLog(`/api/sessions/${encodeURIComponent(target.key)}`, { method: 'DELETE' }),
      () => setSessions((current) => current.filter((session) => session.id !== id)),
      'warning',
    )
  }

  const captureCurrent = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const friendly = captureFriendly.trim()
    const codex = captureCodex.trim()
    if (!friendly || !codex) return

    const account = `${friendly}+${codex}`

    void runAction(
      `Captured ${account}`,
      () =>
        requestWithLog('/api/sessions/capture', {
          method: 'POST',
          body: {
            email: account,
            category: captureCategory.trim(),
            friendlyShareEmail: friendly,
            codexEmail: codex,
          },
        }),
      () => captureDemoSession(account, captureCategory.trim()),
    )
    setCaptureFriendly('')
    setCaptureCodex('')
    setCaptureCategory('')
    setCaptureOpen(false)
  }

  const captureDemoSession = (account: string, cleanCategory: string) => {
    const key = `${cleanCategory || 'default'}/${account}`
    const session: Session = {
      id: key,
      key,
      account,
      category: cleanCategory,
      displayCategory: categoryLabel(cleanCategory),
      fingerprint: makeFingerprint(key),
      active: true,
      capturedAt: formatCapturedAt(),
      fiveHour: null,
      weekly: null,
    }

    setSessions((current) => [
      session,
      ...current.map((item) => ({ ...item, active: false })),
    ])
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Codex switcher navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Icon name="switch" />
          </span>
          <div>
            <strong>Codex Switcher</strong>
            <span>Local auth control</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="Primary">
          <a className="nav-item active" href="#sessions">
            <Icon name="archive" />
            Sessions
          </a>
          <a className="nav-item" href="#capture">
            <Icon name="capture" />
            Capture
          </a>
          <a className="nav-item" href="#limits">
            <Icon name="clock" />
            Limits
          </a>
          <a className="nav-item" href="#activity">
            <Icon name="log" />
            Activity
          </a>
        </nav>

        <div className="safety-panel">
          <Icon name="shield" />
          <p>Do not use Codex.app logout for saved accounts. Prepare login only removes the local active auth file.</p>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Accounts</h1>
          <p>Switch, capture, and track saved Codex.app sessions from one place.</p>
          </div>
          <div className="topbar-actions">
            <button className="button ghost" type="button" onClick={() => void loadState()} disabled={busy !== null}>
              <Icon name="refresh" />
              Reload
            </button>
          </div>
        </header>

        <div className={backendOnline ? 'backend-status online' : 'backend-status offline'}>
          <span>{backendOnline ? 'Backend connected' : 'Demo mode'}</span>
          <strong>{backendOnline ? backendState?.paths.sessions : 'Run codex-switcher-backend for real auth operations.'}</strong>
        </div>

        {backendOnline && backendState && (
          <section className="paths-panel" aria-label="On-disk paths">
            <div className="path-row">
              <div>
                <span className="section-label">Active auth.json</span>
                <code>{backendState.paths.auth}</code>
              </div>
              <button
                className="button ghost"
                type="button"
                onClick={() => openPathInFinder('auth')}
                disabled={busy !== null}
              >
                <Icon name="folder" />
                Reveal in Finder
              </button>
            </div>
            <div className="path-row">
              <div>
                <span className="section-label">Saved sessions folder</span>
                <code>{backendState.paths.sessions}</code>
              </div>
              <button
                className="button ghost"
                type="button"
                onClick={() => openPathInFinder('sessions')}
                disabled={busy !== null}
              >
                <Icon name="folder" />
                Open in Finder
              </button>
            </div>
          </section>
        )}

        <section className="status-strip" aria-label="Session summary">
          <Metric label="Captured" value={String(stats.captured)} />
          <Metric label="Limits loaded" value={String(stats.loadedLimits)} />
          <Metric label="Limits missing" value={String(stats.staleLimits)} />
        </section>

        <section className="command-center" id="capture">
          <div className="current-session">
            {activeSession ? (
              (() => {
                const { friendly, codex } = splitAccount(activeSession.account)
                return friendly ? (
                  <div className="account-fields">
                    <div className="account-field">
                      <span className="account-field-label">Friendly Share</span>
                      <h2>{friendly}</h2>
                    </div>
                    <div className="account-field">
                      <span className="account-field-label">Codex</span>
                      <h2>{codex}</h2>
                    </div>
                  </div>
                ) : (
                  <h2>{codex}</h2>
                )
              })()
            ) : (
              <h2>No active auth.json</h2>
            )}
            {!activeSession && (
              <p>Prepare login or switch to a saved session to populate ~/.codex/auth.json.</p>
            )}
          </div>

          <div className="command-grid">
            <CommandButton
              icon="switch"
              title="Switch saved session"
              detail="Copy selected auth.json into place."
              onClick={() => filteredSessions[0] && switchToSession(filteredSessions[0].id)}
              disabled={filteredSessions.length === 0 || busy !== null}
            />
            <CommandButton
              icon="trash"
              title="Prepare clean login"
              detail="Close Codex and clear active auth locally."
              onClick={prepareLogin}
              disabled={busy !== null}
            />
            <CommandButton
              icon="plus"
              title="Codex login"
              detail="Clear active auth and open Codex.app to sign in."
              onClick={triggerCodexLogin}
              disabled={busy !== null}
            />
            <CommandButton
              icon="capture"
              title="Capture current"
              detail="Save the current active auth.json as a named session."
              onClick={() => setCaptureOpen(true)}
              disabled={busy !== null}
            />
          </div>
        </section>

        <section className="sessions-section" id="sessions">
          <div className="section-header">
            <div>
              <span className="section-label">Saved auth files</span>
              <h2>Session library</h2>
            </div>
            <div className="filters">
              <label>
                <span>Search</span>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="email, category, fingerprint"
                />
              </label>
              <label>
                <span>Category</span>
                <select value={category} onChange={(event) => setCategory(event.target.value)}>
                  {categories.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="session-table" role="table" aria-label="Saved Codex sessions">
            <div className="table-row table-head" role="row">
              <span role="columnheader">Account</span>
              <span role="columnheader">Category</span>
              <span role="columnheader">5h</span>
              <span role="columnheader">Weekly</span>
              <span role="columnheader">Actions</span>
            </div>
            {filteredSessions.map((session) => (
              <div className="table-row" role="row" key={session.id}>
                <div className="account-cell" role="cell">
                  <strong><AccountName account={session.account} /></strong>
                  <span className="account-meta">
                    {session.active && <b>active</b>}
                    <span className="account-captured">captured {session.capturedAt}</span>
                  </span>
                </div>
                <span className="category-pill" role="cell">
                  <Icon name="folder" />
                  {categoryLabel(session.category)}
                </span>
                <LimitCell window={session.fiveHour} />
                <LimitCell window={session.weekly} />
                <div className="row-actions" role="cell">
                  <IconButton label="Switch" icon="switch" onClick={() => switchToSession(session.id)} disabled={busy !== null} />
                  <IconButton label="Forget" icon="trash" onClick={() => forgetSession(session.id)} disabled={busy !== null} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="bottom-grid">
          <div className="limits-panel" id="limits">
            <div className="section-header compact">
              <div>
                <span className="section-label">Rate limits</span>
                <h2>Last known limits</h2>
              </div>
            </div>
            <ol className="refresh-list">
              {sessions.map((session, index) => (
                <li key={session.id}>
                  <span>{index + 1}</span>
                  <div>
                    <strong><AccountName account={session.account} /></strong>
                    <p>{session.fiveHour ? `${session.fiveHour.remaining ?? '?'}% 5h remaining` : 'Limits not loaded'}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="activity-panel" id="activity">
            <div className="section-header compact">
              <div>
                <span className="section-label">Audit trail</span>
                <h2>Recent actions</h2>
              </div>
            </div>
            <ul className="activity-list">
              {activity.map((entry) => (
                <li className={entry.tone} key={entry.id}>
                  <span aria-hidden="true"></span>
                  <div>
                    <strong>{entry.title}</strong>
                    <p>{entry.detail}</p>
                    {entry.log && <ActivityLogDetails log={entry.log} />}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </section>

      {captureOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCaptureOpen(false)}>
          <form className="capture-modal" onSubmit={captureCurrent} onMouseDown={(event) => event.stopPropagation()}>
            <div className="section-header compact">
              <div>
                <span className="section-label">New session</span>
                <h2>Capture current auth.json</h2>
              </div>
              <button className="icon-button" type="button" aria-label="Close" onClick={() => setCaptureOpen(false)}>
                x
              </button>
            </div>
            <label>
              <span>Friendly Share email</span>
              <input
                autoFocus
                type="email"
                value={captureFriendly}
                onChange={(event) => setCaptureFriendly(event.target.value)}
                placeholder="friendlyshare05@gmail.com"
              />
            </label>
            <label>
              <span>Codex email</span>
              <input
                type="email"
                value={captureCodex}
                onChange={(event) => setCaptureCodex(event.target.value)}
                placeholder="codex-account@example.com"
              />
            </label>
            <label>
              <span>Category folder</span>
              <input
                list="capture-category-options"
                value={captureCategory}
                onChange={(event) => setCaptureCategory(event.target.value)}
                placeholder={
                  captureCategories.length > 0
                    ? `${captureCategories.slice(0, 3).join(', ')} — or type a new one`
                    : 'work, personal, tests'
                }
              />
              <datalist id="capture-category-options">
                {captureCategories.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </label>
            <div className="modal-actions">
              <button className="button ghost" type="button" onClick={() => setCaptureOpen(false)}>
                Cancel
              </button>
              <button
                className="button primary"
                type="submit"
                disabled={!captureFriendly.trim() || !captureCodex.trim() || busy !== null}
              >
                <Icon name="check" />
                Save session
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  )
}

async function request<T = { message?: string }>(
  path: string,
  options: { method?: string; body?: Record<string, unknown> } = {},
): Promise<T> {
  const { data } = await requestWithLog<T>(path, options)
  return data
}

async function requestWithLog<T = { message?: string }>(
  path: string,
  options: { method?: string; body?: Record<string, unknown> } = {},
): Promise<{ data: T; log: ActivityLog }> {
  const method = options.method ?? 'GET'
  const requestBody = options.body
  const start = performance.now()
  const timestamp = new Date().toISOString()

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: requestBody ? { 'Content-Type': 'application/json' } : undefined,
      body: requestBody ? JSON.stringify(requestBody) : undefined,
    })
  } catch (cause) {
    const durationMs = Math.round(performance.now() - start)
    const detail = cause instanceof Error ? cause.message : String(cause)
    const apiError = new ApiError({
      method,
      path,
      status: null,
      statusText: '',
      requestBody,
      durationMs,
      detail,
      cause,
    })
    console.error('[codex-switcher] api failed', apiError)
    throw apiError
  }

  const rawText = await response.text()
  let parsed: unknown = undefined
  let parseError: unknown = undefined
  if (rawText) {
    try {
      parsed = JSON.parse(rawText)
    } catch (err) {
      parseError = err
    }
  }
  const durationMs = Math.round(performance.now() - start)
  const responseBody = parsed ?? rawText
  const parsedRecord =
    parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
  const ok = response.ok && parsedRecord?.ok !== false

  if (!ok) {
    const serverMessage =
      (typeof parsedRecord?.error === 'string' && parsedRecord.error) ||
      (typeof parsedRecord?.message === 'string' && parsedRecord.message) ||
      (parseError instanceof Error && `non-JSON response: ${truncate(rawText, 200)}`) ||
      response.statusText ||
      `HTTP ${response.status}`
    const apiError = new ApiError({
      method,
      path,
      status: response.status,
      statusText: response.statusText,
      requestBody,
      responseBody,
      durationMs,
      detail: serverMessage,
      cause: parseError,
    })
    console.error('[codex-switcher] api failed', apiError)
    throw apiError
  }

  console.debug('[codex-switcher] api', {
    method,
    path,
    status: response.status,
    durationMs,
    requestBody,
    response: responseBody,
  })
  const log: ActivityLog = {
    timestamp,
    method,
    path,
    status: response.status,
    statusText: response.statusText,
    durationMs,
    requestBody,
    responseBody,
    serverMessage:
      typeof parsedRecord?.message === 'string' ? (parsedRecord.message as string) : undefined,
  }
  return { data: (parsed ?? {}) as T, log }
}

function logFromError(error: unknown): ActivityLog {
  const timestamp = new Date().toISOString()
  if (error instanceof ApiError) {
    return {
      timestamp,
      method: error.method,
      path: error.path,
      status: error.status,
      statusText: error.statusText,
      durationMs: error.durationMs,
      requestBody: error.requestBody,
      responseBody: error.responseBody,
      errorName: error.name,
      errorMessage: error.message,
      errorStack: error.stack,
      cause:
        error.cause instanceof Error
          ? `${error.cause.name}: ${error.cause.message}`
          : error.cause !== undefined
            ? String(error.cause)
            : undefined,
    }
  }
  if (error instanceof Error) {
    return {
      timestamp,
      errorName: error.name,
      errorMessage: error.message,
      errorStack: error.stack,
    }
  }
  return { timestamp, errorMessage: String(error) }
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return `${text.slice(0, max)}… (${text.length - max} more chars)`
}

function normalizeSession(session: Session): Session {
  return {
    ...session,
    id: session.key || session.id,
    key: session.key || session.id,
    account: session.account || session.key,
    category: session.category || '',
    displayCategory: session.displayCategory || categoryLabel(session.category || ''),
    capturedAt: session.capturedAt || '',
    fiveHour: session.fiveHour,
    weekly: session.weekly,
  }
}

function makeFingerprint(seed: string) {
  let hash = 0
  for (const char of seed) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return `${hash.toString(16).slice(0, 4)}...${(hash ^ 0xabcd).toString(16).slice(0, 4)}`
}

function formatCapturedAt() {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
}

function formatErrorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    const responseSnippet =
      typeof error.responseBody === 'string'
        ? truncate(error.responseBody, 200)
        : ''
    const tail = responseSnippet ? ` — body: ${responseSnippet}` : ''
    return `${error.message} (${error.durationMs}ms)${tail}`
  }
  return error instanceof Error ? error.message : String(error)
}

function ActivityLogDetails({ log }: { log: ActivityLog }) {
  const rows: Array<{ label: string; value: ReactElement | string }> = []

  const add = (label: string, value: unknown) => {
    if (value === undefined || value === null || value === '') return
    if (typeof value === 'object') {
      rows.push({
        label,
        value: <pre>{JSON.stringify(value, null, 2)}</pre>,
      })
    } else {
      rows.push({ label, value: String(value) })
    }
  }

  add('Time', log.timestamp)
  if (log.method && log.path) {
    add('Request', `${log.method} ${log.path}`)
  } else {
    add('Method', log.method)
    add('Path', log.path)
  }
  if (log.status !== undefined) {
    add(
      'Status',
      log.status === null
        ? 'no response (network error)'
        : log.statusText
          ? `${log.status} ${log.statusText}`
          : String(log.status),
    )
  }
  add('Duration', log.durationMs !== undefined ? `${log.durationMs} ms` : undefined)
  add('Server message', log.serverMessage)
  add('Request body', log.requestBody)
  add('Response body', log.responseBody)
  add('Error', log.errorName ? `${log.errorName}: ${log.errorMessage ?? ''}` : log.errorMessage)
  add('Cause', log.cause)
  add('Stack', log.errorStack)
  add('Note', log.note)

  if (rows.length === 0) return null

  return (
    <details className="activity-log">
      <summary>Show details</summary>
      <dl>
        {rows.map((row) => (
          <div className="activity-log-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function CommandButton({
  detail,
  disabled,
  icon,
  onClick,
  title,
}: {
  detail: string
  disabled?: boolean
  icon: IconName
  onClick: () => void
  title: string
}) {
  return (
    <button className="command-button" type="button" onClick={onClick} disabled={disabled}>
      <Icon name={icon} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </button>
  )
}

function formatUntil(resetsAt: number): string {
  const diff = resetsAt - Math.floor(Date.now() / 1000)
  if (diff <= 0) return 'now'
  const days = Math.floor(diff / 86400)
  const hours = Math.floor((diff % 86400) / 3600)
  const mins = Math.floor((diff % 3600) / 60)
  if (days > 0) return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  if (hours > 0) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  return mins > 0 ? `${mins}m` : '<1m'
}

function AccountName({ account }: { account: string }) {
  const { friendly, codex } = splitAccount(account)
  if (!friendly) return <>{codex}</>
  return (
    <span className="account-name">
      <span className="account-name-friendly">{friendly}</span>
      <span className="account-name-codex">{codex}</span>
    </span>
  )
}

function LimitCell({ window }: { window: LimitWindow | null }) {
  if (!window) {
    return (
      <span className="limit-cell empty" role="cell">
        not loaded
      </span>
    )
  }

  if (window.error) {
    return (
      <span className="limit-cell empty" role="cell">
        error
      </span>
    )
  }

  return (
    <span className="limit-cell" role="cell">
      <strong>{window.remaining ?? '?'}% left</strong>
      <small>resets {window.reset}</small>
      {typeof window.resetsAt === 'number' && window.resetsAt > 0 && (
        <small>in {formatUntil(window.resetsAt)}</small>
      )}
    </span>
  )
}

function IconButton({
  disabled,
  icon,
  label,
  onClick,
}: {
  disabled?: boolean
  icon: IconName
  label: string
  onClick: () => void
}) {
  return (
    <button className="icon-button" type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}>
      <Icon name={icon} />
    </button>
  )
}

function Icon({ name }: { name: IconName }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      {icons[name]}
    </svg>
  )
}

const icons: Record<IconName, ReactElement> = {
  archive: (
    <>
      <path d="M4 7h16" />
      <path d="M6 7v12h12V7" />
      <path d="M8 4h8l2 3H6z" />
      <path d="M10 12h4" />
    </>
  ),
  capture: (
    <>
      <path d="M5 8V5h3" />
      <path d="M16 5h3v3" />
      <path d="M19 16v3h-3" />
      <path d="M8 19H5v-3" />
      <path d="M9 12h6" />
      <path d="M12 9v6" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" />
    </>
  ),
  folder: (
    <>
      <path d="M3 7h7l2 2h9v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <path d="M3 7v-.5A2.5 2.5 0 0 1 5.5 4H9l2 3" />
    </>
  ),
  log: (
    <>
      <path d="M7 5h10" />
      <path d="M7 12h10" />
      <path d="M7 19h10" />
      <path d="M3 5h.01" />
      <path d="M3 12h.01" />
      <path d="M3 19h.01" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 6v5h-5" />
      <path d="M4 18v-5h5" />
      <path d="M18 10a6 6 0 0 0-10-3L4 11" />
      <path d="M6 14a6 6 0 0 0 10 3l4-4" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 5 6v5c0 4.5 2.8 8.4 7 10 4.2-1.6 7-5.5 7-10V6z" />
      <path d="M9 12.5 11 15l4-6" />
    </>
  ),
  switch: (
    <>
      <path d="M7 7h11" />
      <path d="m15 4 3 3-3 3" />
      <path d="M17 17H6" />
      <path d="m9 14-3 3 3 3" />
    </>
  ),
  trash: (
    <>
      <path d="M5 7h14" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M7 7l1 13h8l1-13" />
      <path d="M9 7V4h6v3" />
    </>
  ),
}

export default App

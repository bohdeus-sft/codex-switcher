import { useMemo, useState } from 'react'
import type { FormEvent, ReactElement } from 'react'
import './App.css'

type LimitWindow = {
  remaining: number | null
  reset: string
}

type Session = {
  id: string
  account: string
  category: string
  fingerprint: string
  active: boolean
  capturedAt: string
  fiveHour: LimitWindow | null
  weekly: LimitWindow | null
}

type Activity = {
  id: number
  tone: 'success' | 'warning' | 'neutral'
  title: string
  detail: string
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

const initialSessions: Session[] = [
  {
    id: 'work-a',
    account: 'account-a@example.com',
    category: 'work',
    fingerprint: '4f6a...91c2',
    active: true,
    capturedAt: 'May 13 00:12',
    fiveHour: { remaining: 72, reset: '02:40' },
    weekly: { remaining: 54, reset: 'Mon 09:00' },
  },
  {
    id: 'personal-b',
    account: 'account-b@example.com',
    category: 'personal',
    fingerprint: '9bb2...a814',
    active: false,
    capturedAt: 'May 13 00:19',
    fiveHour: { remaining: 41, reset: '01:18' },
    weekly: { remaining: 88, reset: 'Sun 18:00' },
  },
  {
    id: 'test-c',
    account: 'account-c@example.com',
    category: 'tests',
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
    title: 'Captured account-c@example.com',
    detail: 'Saved auth.json into tests/account-c@example.com.json.',
  },
  {
    id: 2,
    tone: 'neutral',
    title: 'Prepared clean login',
    detail: 'Codex.app closed and the active auth.json was removed locally.',
  },
  {
    id: 1,
    tone: 'success',
    title: 'Switched to account-a@example.com',
    detail: 'Selected auth.json copied into ~/.codex/auth.json.',
  },
]

const categoryLabel = (value: string) => value || 'default'

const makeFingerprint = (seed: string) => {
  let hash = 0
  for (const char of seed) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return `${hash.toString(16).slice(0, 4)}...${(hash ^ 0xabcd).toString(16).slice(0, 4)}`
}

const formatCapturedAt = () =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())

function App() {
  const [sessions, setSessions] = useState(initialSessions)
  const [activity, setActivity] = useState(initialActivity)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [captureOpen, setCaptureOpen] = useState(false)
  const [captureName, setCaptureName] = useState('')
  const [captureCategory, setCaptureCategory] = useState('')

  const activeSession = sessions.find((session) => session.active) ?? null
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

  const pushActivity = (entry: Omit<Activity, 'id'>) => {
    setActivity((current) => [{ ...entry, id: Date.now() }, ...current].slice(0, 7))
  }

  const switchToSession = (id: string) => {
    const target = sessions.find((session) => session.id === id)
    if (!target) return

    setSessions((current) =>
      current.map((session) => ({ ...session, active: session.id === id })),
    )
    pushActivity({
      tone: 'success',
      title: `Switched to ${target.account}`,
      detail: 'Codex.app would close, active auth.json would be replaced, then Codex can be reopened.',
    })
  }

  const prepareLogin = () => {
    setSessions((current) => current.map((session) => ({ ...session, active: false })))
    pushActivity({
      tone: 'warning',
      title: 'Prepared clean login',
      detail: 'Active auth.json removed locally. Sign in to the next account, then capture current.',
    })
  }

  const removeActiveAuth = () => {
    if (!activeSession) return
    setSessions((current) => current.map((session) => ({ ...session, active: false })))
    pushActivity({
      tone: 'warning',
      title: `Removed active auth for ${activeSession.account}`,
      detail: 'Saved session remains in the list; only the active local auth file is cleared.',
    })
  }

  const refreshSession = (id: string) => {
    setSessions((current) =>
      current.map((session, index) => {
        if (session.id !== id) return session
        const base = (index + 1) * 17 + session.account.length
        return {
          ...session,
          fiveHour: { remaining: 35 + (base % 61), reset: `${1 + (base % 4)}:${String((base * 7) % 60).padStart(2, '0')}` },
          weekly: { remaining: 42 + (base % 50), reset: ['Fri 12:00', 'Sat 16:30', 'Mon 09:00'][base % 3] },
        }
      }),
    )
    const target = sessions.find((session) => session.id === id)
    pushActivity({
      tone: 'neutral',
      title: target ? `Refreshed limits for ${target.account}` : 'Refreshed limits',
      detail: 'Limit data updated for the selected saved auth file.',
    })
  }

  const refreshAll = () => {
    sessions.forEach((session) => refreshSession(session.id))
    pushActivity({
      tone: 'neutral',
      title: 'Queued slow refresh for all accounts',
      detail: 'Accounts are refreshed one at a time to avoid noisy app-server requests.',
    })
  }

  const forgetSession = (id: string) => {
    const target = sessions.find((session) => session.id === id)
    setSessions((current) => current.filter((session) => session.id !== id))
    if (target) {
      pushActivity({
        tone: 'warning',
        title: `Removed saved session ${target.account}`,
        detail: 'This removes the saved row in the UI. A real backend should confirm before deleting the file.',
      })
    }
  }

  const captureCurrent = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const account = captureName.trim()
    if (!account) return

    const cleanCategory = captureCategory.trim()
    const id = `${cleanCategory || 'default'}-${account}-${Date.now()}`
    const session: Session = {
      id,
      account,
      category: cleanCategory,
      fingerprint: makeFingerprint(id),
      active: true,
      capturedAt: formatCapturedAt(),
      fiveHour: null,
      weekly: null,
    }

    setSessions((current) => [
      session,
      ...current.map((item) => ({ ...item, active: false })),
    ])
    pushActivity({
      tone: 'success',
      title: `Captured ${account}`,
      detail: `Saved current auth.json as ${categoryLabel(cleanCategory)}/${account}.json.`,
    })
    setCaptureName('')
    setCaptureCategory('')
    setCaptureOpen(false)
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
            <p>Switch, capture, and refresh saved Codex.app sessions from one place.</p>
          </div>
          <div className="topbar-actions">
            <button className="button ghost" type="button" onClick={prepareLogin}>
              <Icon name="plus" />
              Prepare login
            </button>
            <button className="button primary" type="button" onClick={() => setCaptureOpen(true)}>
              <Icon name="capture" />
              Capture current
            </button>
          </div>
        </header>

        <section className="status-strip" aria-label="Session summary">
          <Metric label="Captured" value={String(stats.captured)} />
          <Metric label="Limits loaded" value={String(stats.loadedLimits)} />
          <Metric label="Need refresh" value={String(stats.staleLimits)} />
          <div className="active-account">
            <span>Active auth</span>
            <strong>{activeSession ? activeSession.account : 'None'}</strong>
          </div>
        </section>

        <section className="command-center" id="capture">
          <div className="current-session">
            <span className="section-label">Current account</span>
            <h2>{activeSession ? activeSession.account : 'No active auth.json'}</h2>
            <p>
              {activeSession
                ? `Loaded from ${categoryLabel(activeSession.category)} with fingerprint ${activeSession.fingerprint}.`
                : 'Prepare login or switch to a saved session to populate ~/.codex/auth.json.'}
            </p>
          </div>

          <div className="command-grid">
            <CommandButton
              icon="switch"
              title="Switch saved session"
              detail="Copy selected auth.json into place."
              onClick={() => filteredSessions[0] && switchToSession(filteredSessions[0].id)}
              disabled={filteredSessions.length === 0}
            />
            <CommandButton
              icon="plus"
              title="Prepare clean login"
              detail="Close Codex and clear active auth locally."
              onClick={prepareLogin}
            />
            <CommandButton
              icon="capture"
              title="Capture current"
              detail="Save the new login as a named session."
              onClick={() => setCaptureOpen(true)}
            />
            <CommandButton
              icon="trash"
              title="Remove active auth"
              detail="Clear active auth without deleting saved sessions."
              onClick={removeActiveAuth}
              disabled={!activeSession}
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
                  <strong>{session.account}</strong>
                  <span>
                    {session.active && <b>active</b>}
                    {session.fingerprint} captured {session.capturedAt}
                  </span>
                </div>
                <span className="category-pill" role="cell">
                  <Icon name="folder" />
                  {categoryLabel(session.category)}
                </span>
                <LimitCell window={session.fiveHour} />
                <LimitCell window={session.weekly} />
                <div className="row-actions" role="cell">
                  <IconButton label="Switch" icon="switch" onClick={() => switchToSession(session.id)} />
                  <IconButton label="Refresh" icon="refresh" onClick={() => refreshSession(session.id)} />
                  <IconButton label="Forget" icon="trash" onClick={() => forgetSession(session.id)} />
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
                <h2>Slow refresh queue</h2>
              </div>
              <button className="button ghost" type="button" onClick={refreshAll}>
                <Icon name="refresh" />
                Refresh all
              </button>
            </div>
            <ol className="refresh-list">
              {sessions.map((session, index) => (
                <li key={session.id}>
                  <span>{index + 1}</span>
                  <div>
                    <strong>{session.account}</strong>
                    <p>{session.fiveHour ? `${session.fiveHour.remaining}% 5h remaining` : 'Limits not loaded'}</p>
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
                ×
              </button>
            </div>
            <label>
              <span>Email or session name</span>
              <input
                autoFocus
                value={captureName}
                onChange={(event) => setCaptureName(event.target.value)}
                placeholder="account@example.com"
              />
            </label>
            <label>
              <span>Category folder</span>
              <input
                value={captureCategory}
                onChange={(event) => setCaptureCategory(event.target.value)}
                placeholder="work, personal, tests"
              />
            </label>
            <div className="modal-actions">
              <button className="button ghost" type="button" onClick={() => setCaptureOpen(false)}>
                Cancel
              </button>
              <button className="button primary" type="submit" disabled={!captureName.trim()}>
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

function LimitCell({ window }: { window: LimitWindow | null }) {
  if (!window) {
    return (
      <span className="limit-cell empty" role="cell">
        not loaded
      </span>
    )
  }

  return (
    <span className="limit-cell" role="cell">
      <strong>{window.remaining}% left</strong>
      <small>resets {window.reset}</small>
    </span>
  )
}

function IconButton({
  icon,
  label,
  onClick,
}: {
  icon: IconName
  label: string
  onClick: () => void
}) {
  return (
    <button className="icon-button" type="button" aria-label={label} title={label} onClick={onClick}>
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

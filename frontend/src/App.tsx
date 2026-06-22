import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import './App.css'

// Screen Wake Lock API 최소 타입(브라우저 lib에 없을 수 있어 직접 정의).
type WakeLockSentinelLike = { release: () => Promise<void> }
type WakeLockNavigator = Navigator & {
  wakeLock?: { request: (type: 'screen') => Promise<WakeLockSentinelLike> }
}

type DashboardRow = {
  asset_id: number
  name: string
  hostname: string
  offset_ms: number | null
  max_offset_ms: number
  status: string
  last_sync: string | null
}

type Dashboard = {
  generated_at: string
  assets: DashboardRow[]
}

type Standard = {
  id: number
  name: string
  source_host: string
  max_offset_ms: number
  poll_interval_s: number
  version: number
}
type Alert = {
  id: number
  asset_id: number
  asset_name: string
  opened_at: string
  closed_at: string | null
  offset_ms: number
  limit_ms: number | null
  status: string
}
type RefTime = { stratum: number | null; synced: boolean; source: string }
type StandardHistory = {
  id: number
  version: number
  name: string
  max_offset_ms: number
  poll_interval_s: number
  reason: string
  actor: string
  changed_at: string
}

const clockFmt = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const DASHBOARD_REFRESH_MS = 5000 // 대시보드 자동 갱신 주기

// 상태 한글 라벨 (UNKNOWN/UNREACHABLE/STALE/BREACH/OK)
const STATUS_LABEL: Record<string, string> = {
  OK: '정상',
  BREACH: '한계 초과',
  STALE: '갱신 지연',
  UNREACHABLE: '응답 없음',
  UNKNOWN: '미측정',
}

const statusClass = (s: string) => `badge badge--${s.toLowerCase()}`
// 표시는 초(s) 단위, 1자리. (-0.0s는 0.0s로 정규화)
const fmtOffset = (ms: number | null) => {
  if (ms === null) return '—'
  const s = (ms / 1000).toFixed(1)
  return `${s === '-0.0' ? '0.0' : s}s`
}
const fmtLimit = (ms: number) => `${(ms / 1000).toFixed(1)}s`
const fmtSync = (iso: string | null) => (iso ? clockFmt.format(new Date(iso)) : '—')

const dtFmt = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})
const fmtDateTime = (iso: string | null) => (iso ? dtFmt.format(new Date(iso)) : '—')

// 전체화면 시계용 전체 날짜(예: 2026년 6월 21일 일요일)
const fullDateFmt = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

type CollapsibleProps = {
  title: string
  defaultOpen?: boolean
  className?: string
  children: ReactNode
}

/**
 * 섹션 접기/펼치기 헤더. 평소 가독성을 위해 설정·등록·도움말처럼 가끔 쓰는
 * 섹션을 접어둔다. 순수 표시용이며 데이터·API에는 영향이 없다.
 */
function Collapsible({ title, defaultOpen = false, className, children }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className={`collapsible${open ? ' collapsible--open' : ''}${className ? ` ${className}` : ''}`}>
      <button
        type="button"
        className="section-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="section-caret" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <h2>{title}</h2>
      </button>
      {open && <div className="collapsible-body">{children}</div>}
    </section>
  )
}

function App() {
  const [health, setHealth] = useState<string>('확인 중…')
  const [referenceSource, setReferenceSource] = useState<string>('')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [standards, setStandards] = useState<Standard[]>([])

  // 장비 추가 폼
  const [form, setForm] = useState({ name: '', hostname: '', standardId: '' })
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [addOk, setAddOk] = useState<string | null>(null)

  // 한계 초과 로그(Alert) — 탭: 최근 1주일 / 지난 이력(기간 조회)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [alertTab, setAlertTab] = useState<'recent' | 'past'>('recent')
  const ymd = (dt: Date) =>
    `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
  const [pastSince, setPastSince] = useState(() => ymd(new Date(Date.now() - 30 * 86400000)))
  const [pastUntil, setPastUntil] = useState(() => ymd(new Date()))
  const [pastAlerts, setPastAlerts] = useState<Alert[]>([])
  const [pastLoading, setPastLoading] = useState(false)
  const [pastMsg, setPastMsg] = useState<string | null>(null)
  const [pastLoaded, setPastLoaded] = useState(false)

  // 동기화 설정(표준 편집)
  const [settingsStd, setSettingsStd] = useState<Standard | null>(null)
  const [intervalInput, setIntervalInput] = useState('')
  const [limitInput, setLimitInput] = useState('')
  const [reasonInput, setReasonInput] = useState('')
  const [savingSettings, setSavingSettings] = useState(false)
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null)
  const [history, setHistory] = useState<StandardHistory[]>([])
  const [historyOpen, setHistoryOpen] = useState(false) // 변경 이력 기본 접기(평소 가독성)

  // 대형 시계: /api/time(KRISS 보정 기준시각)을 앵커로 받아 로컬에서 매초 틱.
  const [refSkew, setRefSkew] = useState<number | null>(null)
  const [refMeta, setRefMeta] = useState<RefTime | null>(null)
  const [nowMs, setNowMs] = useState<number>(() => Date.now())

  // 전체화면 시계 모드(FS-042). 화면 절전 억제(Screen Wake Lock) 포함.
  const [fullscreen, setFullscreen] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)
  const wakeLockRef = useRef<WakeLockSentinelLike | null>(null)

  const loadDashboard = useCallback(
    () =>
      fetch('/api/dashboard')
        .then((r) => r.json())
        .then((d: Dashboard) => {
          setDashboard(d)
          setError(null)
        })
        .catch(() => {}),
    [],
  )

  const loadAlerts = useCallback(
    () =>
      fetch('/api/alerts')
        .then((r) => r.json())
        .then((d: Alert[]) => setAlerts(d))
        .catch(() => {}),
    [],
  )

  const loadHistory = useCallback(
    (sid: number) =>
      fetch(`/api/standards/${sid}/history`)
        .then((r) => r.json())
        .then((d: StandardHistory[]) => setHistory(d))
        .catch(() => {}),
    [],
  )

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        setHealth(d.status)
        setReferenceSource(d.reference_source)
      })
      .catch(() => setError('백엔드에 연결할 수 없습니다. (uvicorn 실행 여부 확인)'))

    fetch('/api/standards')
      .then((r) => r.json())
      .then((d: Standard[]) => {
        setStandards(d)
        if (d.length) {
          setForm((f) => (f.standardId ? f : { ...f, standardId: String(d[0].id) }))
          setSettingsStd(d[0])
          setIntervalInput(String(d[0].poll_interval_s))
          setLimitInput(String(d[0].max_offset_ms / 1000))
          loadHistory(d[0].id)
        }
      })
      .catch(() => {})
  }, [loadHistory])

  // 대시보드 + 한계초과 로그 자동 갱신: 마운트 시 1회 + 5초마다
  useEffect(() => {
    const load = () => {
      loadDashboard()
      loadAlerts()
    }
    load()
    const id = setInterval(load, DASHBOARD_REFRESH_MS)
    return () => clearInterval(id)
  }, [loadDashboard, loadAlerts])

  // 기준 시각 앵커 동기화: 즉시 1회 + 5분마다 재동기(드리프트 보정)
  useEffect(() => {
    let cancelled = false
    const sync = () =>
      fetch('/api/time')
        .then((r) => r.json())
        .then((d) => {
          if (cancelled) return
          setRefSkew(Date.parse(d.reference_utc) - Date.now())
          setRefMeta({ stratum: d.stratum, synced: d.synced, source: d.source_host })
        })
        .catch(() => {})
    sync()
    const id = setInterval(sync, 300_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  // 표시용 로컬 틱(250ms마다 갱신 → 초 단위 매끄럽게 전환)
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 250)
    return () => clearInterval(id)
  }, [])

  // 화면 절전·화면보호기 억제(localhost/HTTPS에서만 동작). 미지원 시 조용히 무시.
  const acquireWakeLock = useCallback(async () => {
    const wl = (navigator as WakeLockNavigator).wakeLock
    if (!wl) return
    try {
      wakeLockRef.current = await wl.request('screen')
    } catch {
      // 권한 거부·비보안 컨텍스트 등 — 시계는 계속 동작
    }
  }, [])

  // 전체화면 진입 동안: Wake Lock 획득 + 탭 복귀 시 재획득, 해제 시 정리
  useEffect(() => {
    if (!fullscreen) return
    acquireWakeLock()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') acquireWakeLock()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      wakeLockRef.current?.release().catch(() => {})
      wakeLockRef.current = null
    }
  }, [fullscreen, acquireWakeLock])

  // ESC 등으로 브라우저 전체화면이 풀리면 오버레이 상태도 동기화
  useEffect(() => {
    const onFsChange = () => {
      if (!document.fullscreenElement) setFullscreen(false)
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  const enterFullscreen = async () => {
    setFullscreen(true)
    try {
      await overlayRef.current?.requestFullscreen()
    } catch {
      // 전체화면 거부 시에도 오버레이는 표시
    }
  }

  const exitFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    setFullscreen(false)
  }

  const clockText =
    refSkew !== null ? clockFmt.format(new Date(nowMs + refSkew)) : '--:--:--'
  const fullDateText =
    refSkew !== null ? fullDateFmt.format(new Date(nowMs + refSkew)) : ''

  const submitAsset = async (e: React.FormEvent) => {
    e.preventDefault()
    setAddError(null)
    setAddOk(null)
    setAdding(true)
    try {
      // validate=true: 백엔드가 NTP 응답을 확인하고, 응답하는 장비만 등록한다.
      const res = await fetch('/api/assets?validate=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          hostname: form.hostname.trim(),
          standard_id: form.standardId ? Number(form.standardId) : null,
        }),
      })
      if (res.status === 201) {
        setAddOk(`'${form.name.trim()}' 등록됨 (NTP 응답 확인)`)
        setForm((f) => ({ ...f, name: '', hostname: '' }))
        await loadDashboard()
      } else {
        const d = await res.json().catch(() => ({}))
        setAddError(d.detail ?? `등록 실패 (HTTP ${res.status})`)
      }
    } catch {
      setAddError('백엔드에 연결할 수 없습니다.')
    } finally {
      setAdding(false)
    }
  }

  const deleteAsset = async (id: number, name: string) => {
    if (!window.confirm(`'${name}' 장비를 등록 해제할까요?`)) return
    await fetch(`/api/assets/${id}`, { method: 'DELETE' }).catch(() => {})
    await loadDashboard()
  }

  const saveSettings = async () => {
    if (!settingsStd) return
    const interval = Number(intervalInput)
    const limitSec = Number(limitInput)
    if (!Number.isFinite(interval) || interval < 1) {
      setSettingsMsg('폴링 주기는 1초 이상이어야 합니다.')
      return
    }
    if (!Number.isFinite(limitSec) || limitSec < 0) {
      setSettingsMsg('허용 한계는 0초 이상이어야 합니다.')
      return
    }
    setSavingSettings(true)
    setSettingsMsg(null)
    try {
      const res = await fetch(`/api/standards/${settingsStd.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: settingsStd.name,
          source_host: settingsStd.source_host,
          max_offset_ms: Math.round(limitSec * 1000),
          poll_interval_s: Math.round(interval),
          reason: reasonInput.trim() || null,
        }),
      })
      if (res.ok) {
        const updated: Standard = await res.json()
        setSettingsStd(updated)
        setStandards((arr) => arr.map((s) => (s.id === updated.id ? updated : s)))
        setSettingsMsg(
          `저장됨 (v${updated.version}) — ${updated.poll_interval_s}초마다 측정, 허용 한계 ${(updated.max_offset_ms / 1000).toFixed(1)}초`,
        )
        setReasonInput('')
        await loadDashboard()
        await loadHistory(updated.id)
      } else {
        setSettingsMsg(`저장 실패 (HTTP ${res.status})`)
      }
    } catch {
      setSettingsMsg('백엔드에 연결할 수 없습니다.')
    } finally {
      setSavingSettings(false)
    }
  }

  const loadPastAlerts = async () => {
    if (!pastSince || !pastUntil) {
      setPastMsg('시작일과 종료일을 선택하세요.')
      return
    }
    // 로컬 날짜 → UTC ISO(Z). 시작은 그날 00:00, 종료는 그날 23:59:59.999.
    const params = new URLSearchParams({
      since: new Date(`${pastSince}T00:00:00`).toISOString(),
      until: new Date(`${pastUntil}T23:59:59.999`).toISOString(),
    })
    setPastLoading(true)
    setPastMsg(null)
    try {
      const r = await fetch(`/api/alerts?${params.toString()}`)
      const d: Alert[] = await r.json()
      setPastAlerts(d)
      setPastLoaded(true)
      setPastMsg(`${d.length}건 조회됨`)
    } catch {
      setPastMsg('조회에 실패했습니다.')
    } finally {
      setPastLoading(false)
    }
  }

  // 한계 초과 로그 표(최근/지난 이력 공용)
  const alertTable = (list: Alert[]) => (
    <table>
      <thead>
        <tr>
          <th>장비</th>
          <th className="num">측정 오프셋</th>
          <th className="num">허용 한계</th>
          <th className="num">발생 시각</th>
          <th className="num">해제 시각</th>
          <th className="center">상태</th>
        </tr>
      </thead>
      <tbody>
        {list.map((al) => (
          <tr key={al.id}>
            <td>{al.asset_name || `#${al.asset_id}`}</td>
            <td className="num">{fmtOffset(al.offset_ms)}</td>
            <td className="num">{al.limit_ms != null ? fmtLimit(al.limit_ms) : '—'}</td>
            <td className="num">{fmtDateTime(al.opened_at)}</td>
            <td className="num">{fmtDateTime(al.closed_at)}</td>
            <td className="center">
              <span className={`badge badge--${al.status === 'OPEN' ? 'breach' : 'unreachable'}`}>
                {al.status === 'OPEN' ? '진행 중' : '해제됨'}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )

  const canSubmit = form.name.trim() && form.hostname.trim() && form.standardId && !adding

  return (
    <div className="app">
      {/* 전체화면 시계(FS-042) — 항상 DOM에 두고 클래스로 표시 전환(전체화면 요청은 사용자 제스처 내에서 안정적) */}
      <div
        ref={overlayRef}
        className={`fs-overlay${fullscreen ? ' fs-overlay--on' : ''}`}
        aria-hidden={!fullscreen}
      >
        <button className="fs-close" onClick={exitFullscreen} title="나가기 (ESC)">
          ✕
        </button>
        <div className="fs-label">KRISS 표준시 · UTC+9 (Asia/Seoul)</div>
        <div className={`fs-clock${refMeta && !refMeta.synced ? ' fs-clock--stale' : ''}`}>
          {clockText}
        </div>
        <div className="fs-date">{fullDateText}</div>
        <div className={`fs-sync${refMeta && !refMeta.synced ? ' fs-sync--stale' : ''}`}>
          <span className="fs-dot" />
          {refMeta === null
            ? '동기화 중…'
            : refMeta.synced
              ? `동기화 양호 · ${refMeta.source} · stratum ${refMeta.stratum ?? '—'}`
              : `미검증 — 서버 시각 표시 (${refMeta.source} 도달 실패)`}
        </div>
        <div className="fs-hint">ESC 또는 ✕ 로 나가기</div>
      </div>

      <header>
        <h1>pharma-ntp-standard</h1>
        <p className="subtitle">
          제약(GMP) NTP 시간 표준 · 기준: <strong>KRISS UTC(k)</strong>
          {referenceSource && <code>{referenceSource}</code>}
        </p>
        <p className="status">
          백엔드 상태:{' '}
          <span className={health === 'ok' ? 'ok' : 'warn'}>{health}</span>
        </p>
      </header>

      <section className="clock-panel">
        <div className="clock-label">KRISS 표준시 · UTC+9 (Asia/Seoul)</div>
        <div className={`clock${refMeta && !refMeta.synced ? ' clock--stale' : ''}`}>
          {clockText}
        </div>
        <div className="clock-meta">
          {refMeta === null
            ? '기준 시각 동기화 중…'
            : refMeta.synced
              ? `${refMeta.source} · stratum ${refMeta.stratum ?? '—'} · 동기화 상태 양호`
              : `${refMeta.source} 도달 실패 — 서버 시각 표시(미검증)`}
        </div>
        <button className="fs-enter" onClick={enterFullscreen}>
          ⛶ 전체화면 시계
        </button>
      </section>

      {error && <div className="error">{error}</div>}

      <section>
        <div className="section-head">
          <h2>동기화 모니터링 대시보드</h2>
          <span className="refresh-note">
            {dashboard
              ? `자동 갱신 · 최근 ${fmtSync(dashboard.generated_at)}`
              : '불러오는 중…'}
          </span>
        </div>
        {!dashboard || dashboard.assets.length === 0 ? (
          <p className="empty">
            등록된 장비가 없습니다. 아래 <strong>장비 등록</strong>에서 추가하세요.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>장비</th>
                <th>IP / 호스트</th>
                <th className="num">오프셋</th>
                <th className="num">허용 한계</th>
                <th className="center">상태</th>
                <th className="num">마지막 동기화</th>
                <th className="center">관리</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.assets.map((a) => (
                <tr key={a.asset_id}>
                  <td>{a.name}</td>
                  <td className="mono">{a.hostname}</td>
                  <td className="num">{fmtOffset(a.offset_ms)}</td>
                  <td className="num">{fmtLimit(a.max_offset_ms)}</td>
                  <td className="center">
                    <span className={statusClass(a.status)}>
                      {STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </td>
                  <td className="num">{fmtSync(a.last_sync)}</td>
                  <td className="center">
                    <button
                      className="btn-del"
                      onClick={() => deleteAsset(a.asset_id, a.name)}
                      title="등록 해제"
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <div className="section-head">
          <h2>허용 한계 초과 로그</h2>
          <div className="tabs">
            <button
              className={alertTab === 'recent' ? 'tab tab--on' : 'tab'}
              onClick={() => setAlertTab('recent')}
            >
              최근 1주일
            </button>
            <button
              className={alertTab === 'past' ? 'tab tab--on' : 'tab'}
              onClick={() => setAlertTab('past')}
            >
              지난 이력
            </button>
          </div>
        </div>

        {alertTab === 'recent' ? (
          <>
            <p className="form-hint">최근 7일 + 진행 중(OPEN) 경고 · {alerts.length}건</p>
            {alerts.length === 0 ? (
              <p className="empty">최근 7일간 한계를 초과한 기록이 없습니다.</p>
            ) : (
              alertTable(alerts)
            )}
          </>
        ) : (
          <>
            <div className="add-form">
              <label className="field">
                시작일
                <input
                  type="date"
                  value={pastSince}
                  max={pastUntil}
                  onChange={(e) => setPastSince(e.target.value)}
                />
              </label>
              <label className="field">
                종료일
                <input
                  type="date"
                  value={pastUntil}
                  min={pastSince}
                  onChange={(e) => setPastUntil(e.target.value)}
                />
              </label>
              <button onClick={loadPastAlerts} disabled={pastLoading}>
                {pastLoading ? '조회 중…' : '조회'}
              </button>
            </div>
            {pastMsg && <div className="ok-msg">{pastMsg}</div>}
            {pastAlerts.length === 0 ? (
              <p className="empty">
                {pastLoaded
                  ? '선택한 기간에 한계 초과 기록이 없습니다.'
                  : '기간을 선택하고 조회하세요.'}
              </p>
            ) : (
              alertTable(pastAlerts)
            )}
          </>
        )}
      </section>

      <Collapsible title="동기화 설정">
        {settingsStd ? (
          <>
            <div className="add-form">
              <label className="field">
                폴링 주기(초)
                <input
                  type="number"
                  min={1}
                  value={intervalInput}
                  onChange={(e) => setIntervalInput(e.target.value)}
                />
              </label>
              <label className="field">
                허용 한계(초)
                <input
                  type="number"
                  min={0}
                  step="0.1"
                  value={limitInput}
                  onChange={(e) => setLimitInput(e.target.value)}
                />
              </label>
              <label className="field field--grow">
                변경 사유
                <input
                  type="text"
                  placeholder="예: 장비 안정화로 한계 강화"
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                />
              </label>
              <button onClick={saveSettings} disabled={savingSettings}>
                {savingSettings ? '저장 중…' : '저장'}
              </button>
            </div>
            <p className="form-hint">
              표준 '<strong>{settingsStd.name}</strong>'에 적용 · 현재{' '}
              <strong>{settingsStd.poll_interval_s}초</strong>마다 (
              {(settingsStd.poll_interval_s / 60).toFixed(1)}분) 측정, 허용 한계{' '}
              <strong>{(settingsStd.max_offset_ms / 1000).toFixed(1)}초</strong> · 버전{' '}
              <strong>v{settingsStd.version}</strong> · 저장 시 변경 이력이 기록됩니다(FS-002)
            </p>
            {settingsMsg && <div className="ok-msg">{settingsMsg}</div>}
            {history.length > 0 && (
              <div className="history">
                <button
                  type="button"
                  className="history-toggle"
                  onClick={() => setHistoryOpen((v) => !v)}
                  aria-expanded={historyOpen}
                >
                  {historyOpen ? '▾' : '▸'} 표준 변경 이력 ({history.length}건)
                  {historyOpen ? ' 접기' : ''}
                </button>
                {historyOpen && (
                  <table>
                    <thead>
                      <tr>
                        <th className="num">버전</th>
                        <th className="num">변경 시각</th>
                        <th className="num">허용 한계</th>
                        <th className="num">폴링 주기</th>
                        <th>사유</th>
                        <th>기록자</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...history].reverse().map((h) => {
                        const isCurrent =
                          settingsStd != null && h.version === settingsStd.version
                        return (
                          <tr key={h.id} className={isCurrent ? 'history-current' : undefined}>
                            <td className="num">
                              v{h.version}
                              {isCurrent && <span className="badge badge--current">현재</span>}
                            </td>
                            <td className="num">{fmtDateTime(h.changed_at)}</td>
                            <td className="num">{fmtLimit(h.max_offset_ms)}</td>
                            <td className="num">{h.poll_interval_s}s</td>
                            <td>{h.reason || '—'}</td>
                            <td className="mono">{h.actor}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="empty">표준이 없습니다.</p>
        )}
      </Collapsible>

      <Collapsible title="장비 등록">
        <form className="add-form" onSubmit={submitAsset}>
          <input
            type="text"
            placeholder="장비 이름 (예: HPLC-WS-01)"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
          <input
            type="text"
            placeholder="IP 또는 호스트 (예: 10.0.0.5)"
            value={form.hostname}
            onChange={(e) => setForm((f) => ({ ...f, hostname: e.target.value }))}
          />
          <select
            value={form.standardId}
            onChange={(e) => setForm((f) => ({ ...f, standardId: e.target.value }))}
          >
            {standards.length === 0 && <option value="">표준 없음</option>}
            {standards.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <button type="submit" disabled={!canSubmit}>
            {adding ? 'NTP 확인 중…' : '추가'}
          </button>
        </form>
        <p className="form-hint">
          IP가 <strong>NTP에 응답할 때만</strong> 등록됩니다. (응답 없으면 거부)
        </p>
        {addError && <div className="error">{addError}</div>}
        {addOk && <div className="ok-msg">{addOk}</div>}
      </Collapsible>

      <Collapsible title="화면 설명" className="info-box">
        <ul>
          <li>
            <code>time.kriss.re.kr</code> — 한국표준과학연구원(KRISS)이 운영하는{' '}
            <strong>국가표준시 NTP 서버</strong>. 이 시스템이 신뢰하는 기준 시각(진실의
            시각)이며, 모든 장비의 오차는 이 시각을 기준으로 측정합니다.
          </li>
          <li>
            <strong>stratum(계층)</strong> — 원자시계로부터 떨어진 단계로, 숫자가 작을수록
            기준에 가깝습니다.
            <ul>
              <li>
                <strong>stratum 0</strong> — 원자시계·GPS 등 기준 시계 자체 (네트워크에 직접
                붙지 않음)
              </li>
              <li>
                <strong>stratum 1</strong> — 기준 시계에 직접 연결된 1차 시간 서버
              </li>
              <li>
                <strong>stratum 2</strong> — stratum 1로부터 시각을 받는 서버 (1단계 거침)
              </li>
              <li>
                <strong>stratum 3</strong> — stratum 2로부터 받는 서버 (2단계 거침). 우리가
                측정한 <code>time.kriss.re.kr</code>이 여기에 해당합니다 —{' '}
                <strong>KRISS는 stratum 2가 아니라 3</strong>으로 응답합니다(공개 서버가 내부
                분배 계층을 거치기 때문).
              </li>
            </ul>
          </li>
          <li>
            <strong>오프셋</strong> — 각 장비 시각이 KRISS 기준에서 벗어난 정도. 허용 한계를
            넘으면 <span className="badge badge--breach">한계 초과</span>로 경고하고,
            응답이 없으면 <span className="badge badge--unreachable">응답 없음</span>으로
            표시합니다.
          </li>
        </ul>
      </Collapsible>

      <footer>
        <a href="https://github.com" target="_blank" rel="noreferrer">
          오픈소스 · MIT
        </a>
      </footer>
    </div>
  )
}

export default App

import { useEffect, useState } from 'react'
import './App.css'

type DashboardRow = {
  asset_id: number
  name: string
  gxp_critical: boolean
  offset_ms: number | null
  max_offset_ms: number
  status: string
  last_sync: string | null
}

type Dashboard = {
  generated_at: string
  assets: DashboardRow[]
}

type RefTime = { stratum: number | null; synced: boolean; source: string }

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
const fmtOffset = (ms: number | null) => (ms === null ? '—' : ms.toFixed(2))
const fmtSync = (iso: string | null) => (iso ? clockFmt.format(new Date(iso)) : '—')

function App() {
  const [health, setHealth] = useState<string>('확인 중…')
  const [referenceSource, setReferenceSource] = useState<string>('')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 대형 시계: /api/time(KRISS 보정 기준시각)을 앵커로 받아 로컬에서 매초 틱.
  // skew = (서버가 준 기준 UTC ms) − (수신 시점 브라우저 ms). 매초 now+skew를 표시.
  const [refSkew, setRefSkew] = useState<number | null>(null)
  const [refMeta, setRefMeta] = useState<RefTime | null>(null)
  const [nowMs, setNowMs] = useState<number>(() => Date.now())

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        setHealth(d.status)
        setReferenceSource(d.reference_source)
      })
      .catch(() => setError('백엔드에 연결할 수 없습니다. (uvicorn 실행 여부 확인)'))
  }, [])

  // 대시보드 자동 갱신: 마운트 시 1회 + 5초마다(백엔드 스케줄러가 폴링한 최신값 반영)
  useEffect(() => {
    let cancelled = false
    const load = () =>
      fetch('/api/dashboard')
        .then((r) => r.json())
        .then((d) => {
          if (cancelled) return
          setDashboard(d)
          setError(null)
        })
        .catch(() => {})
    load()
    const id = setInterval(load, DASHBOARD_REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  // 기준 시각 앵커 동기화: 즉시 1회 + 60초마다 재동기(드리프트 보정)
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
    const id = setInterval(sync, 300_000) // 5분마다 재동기(그 사이 로컬 틱). KRISS 부하 최소화.
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

  const clockText =
    refSkew !== null ? clockFmt.format(new Date(nowMs + refSkew)) : '--:--:--'

  return (
    <div className="app">
      <header>
        <h1>pharma-ntp-standard</h1>
        <p className="subtitle">
          제약(GxP) NTP 시간 표준 · 기준: <strong>KRISS UTC(k)</strong>
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
              ? `${refMeta.source} · stratum ${refMeta.stratum ?? '—'} · 동기 양호`
              : `${refMeta.source} 도달 실패 — 서버 시각 표시(미검증)`}
        </div>
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
            등록된 장비가 없습니다. 백엔드 <code>/api/assets</code> 로 장비를
            등록하면 여기에 표시됩니다.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>장비</th>
                <th>GxP</th>
                <th>오프셋(ms)</th>
                <th>한계(ms)</th>
                <th>상태</th>
                <th>마지막 동기</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.assets.map((a) => (
                <tr key={a.asset_id}>
                  <td>{a.name}</td>
                  <td>{a.gxp_critical ? '✔' : ''}</td>
                  <td className="num">{fmtOffset(a.offset_ms)}</td>
                  <td className="num">{a.max_offset_ms}</td>
                  <td>
                    <span className={statusClass(a.status)}>
                      {STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </td>
                  <td>{fmtSync(a.last_sync)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <footer>
        <a href="https://github.com" target="_blank" rel="noreferrer">
          오픈소스 · MIT
        </a>
      </footer>
    </div>
  )
}

export default App

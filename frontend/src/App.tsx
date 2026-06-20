import { useCallback, useEffect, useState } from 'react'
import './App.css'

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

type Standard = { id: number; name: string }
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
// 표시는 초(s) 단위, 1자리. (-0.0s는 0.0s로 정규화)
const fmtOffset = (ms: number | null) => {
  if (ms === null) return '—'
  const s = (ms / 1000).toFixed(1)
  return `${s === '-0.0' ? '0.0' : s}s`
}
const fmtLimit = (ms: number) => `${(ms / 1000).toFixed(1)}s`
const fmtSync = (iso: string | null) => (iso ? clockFmt.format(new Date(iso)) : '—')

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

  // 대형 시계: /api/time(KRISS 보정 기준시각)을 앵커로 받아 로컬에서 매초 틱.
  const [refSkew, setRefSkew] = useState<number | null>(null)
  const [refMeta, setRefMeta] = useState<RefTime | null>(null)
  const [nowMs, setNowMs] = useState<number>(() => Date.now())

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
        if (d.length) setForm((f) => (f.standardId ? f : { ...f, standardId: String(d[0].id) }))
      })
      .catch(() => {})
  }, [])

  // 대시보드 자동 갱신: 마운트 시 1회 + 5초마다(백엔드 스케줄러가 폴링한 최신값 반영)
  useEffect(() => {
    loadDashboard()
    const id = setInterval(loadDashboard, DASHBOARD_REFRESH_MS)
    return () => clearInterval(id)
  }, [loadDashboard])

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

  const clockText =
    refSkew !== null ? clockFmt.format(new Date(nowMs + refSkew)) : '--:--:--'

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

  const canSubmit = form.name.trim() && form.hostname.trim() && form.standardId && !adding

  return (
    <div className="app">
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
      </section>

      <section className="info-box">
        <h3>화면 설명</h3>
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
      </section>

      {error && <div className="error">{error}</div>}

      <section>
        <h2>장비 등록</h2>
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
      </section>

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
            등록된 장비가 없습니다. 위 <strong>장비 등록</strong>에서 추가하세요.
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

      <footer>
        <a href="https://github.com" target="_blank" rel="noreferrer">
          오픈소스 · MIT
        </a>
      </footer>
    </div>
  )
}

export default App

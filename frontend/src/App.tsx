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

function App() {
  const [health, setHealth] = useState<string>('확인 중…')
  const [referenceSource, setReferenceSource] = useState<string>('')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        setHealth(d.status)
        setReferenceSource(d.reference_source)
      })
      .catch(() => setError('백엔드에 연결할 수 없습니다. (uvicorn 실행 여부 확인)'))

    fetch('/api/dashboard')
      .then((r) => r.json())
      .then(setDashboard)
      .catch(() => {})
  }, [])

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

      {error && <div className="error">{error}</div>}

      <section>
        <h2>동기화 모니터링 대시보드</h2>
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
                  <td>{a.offset_ms ?? '—'}</td>
                  <td>{a.max_offset_ms}</td>
                  <td>{a.status}</td>
                  <td>{a.last_sync ?? '—'}</td>
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

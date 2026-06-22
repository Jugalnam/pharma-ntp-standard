# 현장 검증 실행 런북 (Field Validation Runbook)

| 항목 | 내용 |
|------|------|
| 문서 ID | RUN-001 |
| 버전 | 1.0 |
| 대상 | 검증 실행자 / QA |
| 목적 | 이 PC에서 IQ 재실행 · OQ 자동/현장 케이스 · OQ-050~052(보안) · PQ를 **순서대로 실행하고 증빙을 남기는** 실무 절차서 |
| 관련 | [07 IQ](07-iq-protocol.md) · [08 OQ](08-oq-protocol.md) · [09 PQ](09-pq-protocol.md) · [03 DS-040](03-design-spec.md) · [04 RA](04-risk-assessment.md) |

> 이 문서는 검증 산출물(V 모델)이 아니라 **실행 절차서(런북)** 입니다. 셸은 **PowerShell** 기준이며, 명령은 그대로 복붙할 수 있게 작성했습니다. 실행 결과는 §8 증빙 양식에 기록하세요.

> ⚠️ **이 PC는 "리허설/개발 PC"로 분류됨.** 따라서 **OQ-050 egress 방화벽은 적용하지 않습니다**(절차만 정의 — §6). 실제 적용은 현장 "감시 전용 운영 호스트"에서 수행합니다. PQ(§7)도 현장 범위입니다.

---

## 0. 사전 준비 — 환경 구성 (이 PC 기준)

검증 전제: 이 PC엔 `backend/.venv`·`frontend/node_modules`·DB가 아직 없습니다. 먼저 환경을 구성합니다.

```powershell
# 백엔드
cd C:\Users\User\dev\pharma-ntp-standard\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # 차단되면: Set-ExecutionPolicy -Scope Process RemoteSigned
pip install -r requirements.txt

# 프런트 (새 창 또는 deactivate 후)
cd ..\frontend
npm install
```

증빙: `pip` 마지막 줄(Successfully installed …), `node_modules` 생성. → IQ-002/IQ-004 근거.

---

## 1. IQ 재실행 (설치 적격성 — 이 PC 재확인)

[07-iq-protocol.md](07-iq-protocol.md)는 PASS로 기록돼 있으나, 재생성 폴더가 정리된 상태이므로 **이 PC 기준으로 재실행**합니다.

| ID | 명령 | 기대 |
|----|------|------|
| IQ-001 | `python --version` | ≥ 3.11 |
| IQ-002 | `pip install -r requirements.txt` | 오류 없이 완료 |
| IQ-003 | `node --version` | ≥ 20 |
| IQ-004 | `npm install` → `Test-Path .\node_modules` | `True` |
| IQ-005 | 백엔드 기동 후 health (아래) | `200 {"status":"ok"}` |
| IQ-006 | 기동 후 `Test-Path .\backend\pharma_ntp.sqlite3` | `True` (DB 생성) |
| IQ-007 | `/api/time` (아래) | NTP 응답·stratum 유효 |

```powershell
# 백엔드 기동 (전용 창 — 이후 OQ 내내 켜둠)
cd C:\Users\User\dev\pharma-ntp-standard\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app                     # 기본 127.0.0.1:8000 (OQ-052 전제)

# 다른 창에서 IQ-005 / IQ-007
Invoke-RestMethod http://127.0.0.1:8000/api/health      # status=ok
Invoke-RestMethod http://127.0.0.1:8000/api/time        # synced=true, reference_utc, stratum
Test-Path C:\Users\User\dev\pharma-ntp-standard\backend\pharma_ntp.sqlite3   # IQ-006 → True
```

---

## 2. OQ 자동 케이스 (pytest 스위트)

OQ-001~031, OQ-028(영속), High 위험 OQ-022a/b·OQ-023(RISK-001)은 자동 테스트로 입증됩니다. **`backend/`에서** 실행해야 import가 풀립니다(테스트는 임시 DB `test_ntp.sqlite3` 사용 — 운영 DB와 분리).

```powershell
cd C:\Users\User\dev\pharma-ntp-standard\backend
.\.venv\Scripts\Activate.ps1
pytest -v
# High 위험만 집중 재확인
pytest tests/test_alerts.py -v
```

기대: 전건 PASS(문서 기준 27건). 증빙: pytest 요약 줄(`=== N passed ===`)을 캡처/저장. → OQ 자동 케이스 일괄 근거.

---

## 3. OQ-052 — 접근 통제 (이 PC에서 라이브 검증 가능)

근거: [main.py](../backend/app/main.py) 루프백 바인딩(FS-050), CORS는 `http://localhost:5173`만. 목표: **외부 인터페이스로 노출되지 않음**을 입증(RISK-008).

```powershell
# 3-1) 리슨 주소 확인 — LocalAddress가 127.0.0.1 이어야 함 (0.0.0.0 아님)
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress,LocalPort

# 3-2) 루프백은 응답
Invoke-RestMethod http://127.0.0.1:8000/api/health

# 3-3) 이 PC의 LAN IP 확인 후, 그 IP로는 접근 거부(연결 실패)되어야 함
Get-NetIPAddress -AddressFamily IPv4 | Where-Object PrefixOrigin -ne 'WellKnown' | Select-Object IPAddress,InterfaceAlias
try { Invoke-RestMethod "http://<위에서_확인한_LAN_IP>:8000/api/health" -TimeoutSec 3 }
catch { "거부됨(기대): " + $_.Exception.Message }
```

기대: 3-1 `LocalAddress = 127.0.0.1`, 3-2 정상 응답, 3-3 연결 실패. 미인증 접근 통제는 참조 구현에선 **루프백 전용 바인딩으로 대체**(내부망 노출 시 인증 게이트 필요 — 현장 형상 결정 사항, 결과란에 명시).

---

## 4. OQ-051 — 읽기 전용 동작 (코드 근거 + 현장 장비 전후 비교)

근거(이 PC에서 확인 가능): [ntp.py](../backend/app/services/ntp.py)는 `client.request(...)` **NTP 클라이언트 mode 3(읽기)만** 사용. 시각 설정·제어 모드(mode 6/7) 없음 → 대상 장비를 변경하지 않음(RISK-011).

현장 절차(대상 장비 1대 — 장비 콘솔에서 전후 스냅샷):

```powershell
# (장비 콘솔에서) 폴링 전 시각·NTP 설정 스냅샷
w32tm /query /status
w32tm /query /configuration

# (감시 PC에서) 해당 장비 1회 폴링
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/assets/<장비ID>/poll

# (장비 콘솔에서) 폴링 후 — 설정·동기화원 무변경 확인
w32tm /query /status
w32tm /query /configuration
```

기대: 폴링 전후 장비의 시각 동기화원·NTP 설정 **무변경**(질의만 발생). 선택: 감시 PC에서 `pktmon`/Wireshark로 송신 패킷이 mode 3뿐임을 캡처.

---

## 5. (참고) 프런트 대시보드 수동 확인 — OQ-042 등

```powershell
cd C:\Users\User\dev\pharma-ntp-standard\frontend
npm run dev          # http://localhost:5173 — 백엔드 기동 상태 전제
```

확인: 대형 시계(FS-041, synced 상태색), 전체화면 진입/ESC·Wake Lock(OQ-042), 한계초과 로그 표(OQ-023).

---

## 6. OQ-050 — Egress 제한 (절차 정의 — 이 PC 미적용)

> **High 위험 RISK-007 / "운영 승인 전 필수" 케이스.** ⚠️ **이 PC(리허설/개발)에는 적용 금지** — 적용 시 이 PC의 일반 인터넷이 차단됩니다. 아래는 **실제 운영 호스트**에서 관리자 권한으로 실행할 절차입니다.

설계 통제([DS-040](03-design-spec.md)): 아웃바운드 `time.kriss.re.kr:123/udp`만 허용, 그 외 인터넷·인바운드 차단.

```powershell
# (운영 호스트, 관리자 PowerShell) — 현장 방화벽 정책에 맞게 조정
Resolve-DnsName time.kriss.re.kr -Type A          # 6-1) KRISS IP 확인
$kriss = (Resolve-DnsName time.kriss.re.kr -Type A).IPAddress

# 6-2) KRISS:123/udp 아웃바운드 허용 규칙
New-NetFirewallRule -DisplayName "NTP-KRISS-out" -Direction Outbound `
  -Protocol UDP -RemotePort 123 -RemoteAddress $kriss -Action Allow
# 6-3) 그 외 아웃바운드 인터넷 차단·인바운드 차단은 현장 방화벽(그룹정책/경계 방화벽)으로 구성

# --- 검증 ---
Invoke-RestMethod http://127.0.0.1:8000/api/time            # KRISS 도달 → synced=true (성공 기대)
try { Invoke-WebRequest https://example.com -TimeoutSec 5 } # 임의 외부
catch { "차단됨(기대): " + $_.Exception.Message }

# --- 롤백 ---
Remove-NetFirewallRule -DisplayName "NTP-KRISS-out"
```

기대: KRISS:123 성공, 그 외 외부 통신·인바운드 차단. 합격 시 RISK-007 완화 입증 → 운영 승인 전제 충족.

---

## 7. PQ — 현장 운영 검증 (요약 절차, 현장 범위)

[09-pq-protocol.md](09-pq-protocol.md) 기준. 실 운영 환경·실 장비에서 수행:

| ID | 시나리오 | 측정·증빙 |
|----|---------|----------|
| PQ-001 | 실 NTP 소스(`time.kriss.re.kr`)로 표준 구성·운영 | 오프셋 수집 성공, **UTCk(공식 프로그램) 시각과 차이 ≤ 한계** 동시 측정·비교 |
| PQ-002 | 대표 장비 24h 연속 폴링 | 폴링 누락 0, 드리프트 추세 기록 |
| PQ-003 | 수십 대 규모 대시보드 조회 | `/api/dashboard` 응답 ≤ 1초 |
| PQ-004 | 장비 시각 인위적 이탈 | 경고 발생·운영자 인지(한계초과 로그·화면) |
| PQ-005 | IQ→OQ→PQ 산출물 승인 흐름 | 상태 전이(Draft→…→Effective)·이력 정상 |

---

## 8. 증빙 기록 (실행 결과)

> 실행 일자: **2026-06-22**, 이 PC(리허설/개발 PC). 아래 실측은 Claude Code 보조로 수집한 객관 증빙이다.
> **실행자·QA 검토 서명(§9)은 사람이 직접 작성**한다 — ALCOA+ *Attributable* 원칙상 판정의 책임 귀속은 사람에게 있다.
> 판정 표기: ✅ P(이 PC 라이브 통과) · ◐ 부분(이 PC 시연, 현장 잔여) · ⏳ 현장(미실행, 현장 범위).

| 케이스 | 기대 | 실측 / 증빙 | 판정 | 일자 |
|--------|------|------------|------|------|
| IQ-001 Python | ≥ 3.11 | Python 3.12.2 | ✅ P | 2026-06-22 |
| IQ-002 백엔드 deps | 설치 완료 | fastapi 0.138.0·sqlalchemy 2.0.51, import OK | ✅ P | 2026-06-22 |
| IQ-003 Node | ≥ 20 | v22.22.3 | ✅ P | 2026-06-22 |
| IQ-004 프런트 deps | node_modules | present | ✅ P | 2026-06-22 |
| IQ-005 health | 200 ok | `{"status":"ok","reference_source":"time.kriss.re.kr"}` | ✅ P | 2026-06-22 |
| IQ-006 DB 생성 | sqlite3 존재 | pharma_ntp.sqlite3 present | ✅ P | 2026-06-22 |
| IQ-007 NTP 도달 | stratum 유효 | synced=true, stratum 3, offset +468ms (KRISS) | ✅ P | 2026-06-22 |
| OQ 자동(pytest) | 전건 PASS | **29 passed** (2.40s) — test_alerts·test_monitor·test_api | ✅ P | 2026-06-22 |
| OQ-020 폴링·KRISS 보정 | 보정 오프셋·reachable | Label PC(192.0.6.144) 보정 오프셋 측정, reachable=true | ✅ P | 2026-06-22 |
| OQ-021 대시보드 | 장비별 최신 행 | Label PC offset/stratum/status=OK/last_sync 반환 | ✅ P | 2026-06-22 |
| OQ-022b/023 한계초과+로그 | BREACH+로그 | 한계 1.0s에서 BREACH→로그 1건(OPEN 11:16:08→CLOSED 11:26:09 KST, offset 1.35s>1.0s) | ✅ P | 2026-06-22 |
| OQ-025 자동 스케줄러 | 자동 측정·갱신 | 등록 후 수동 폴링 없이 자동 측정·대시보드 자동 갱신 | ✅ P | 2026-06-22 |
| OQ-041 기준시각 표시 | synced·stratum | synced=true, stratum 3, reference_utc 반환(대형 시계) | ✅ P | 2026-06-22 |
| OQ-052 바인딩 | 127.0.0.1 only | LocalAddress 127.0.0.1:8000 단독 LISTEN(0.0.0.0 아님) | ✅ P | 2026-06-22 |
| OQ-052 외부 거부 | LAN IP 실패 | LAN 172.20.240.1:8000 연결 거부, 127.0.0.1만 응답 | ✅ P | 2026-06-22 |
| OQ-051 읽기전용 | 장비 무변경 | 코드 mode3 전용(`ntp.py` client.request)·mode6/7 부재 확인. 장비 콘솔 전후 비교는 현장 | ◐ 부분 | 2026-06-22 |
| OQ-050 egress | KRISS만 허용 | 현장 운영 호스트에서 실행(이 PC 미적용 — §6) | ⏳ 현장 | — |
| PQ-001 UTCk 정합 | 차이 ≤ 한계 | KRISS 실소스로 표준 운영·오프셋 수집 확인; UTCk 공식프로그램 동시비교는 현장 | ◐ 부분 | 2026-06-22 |
| PQ-002 24h 모니터링 | 폴링 누락 0 | 현장(장기 연속 운영) | ⏳ 현장 | — |
| PQ-003 대시보드 성능 | ≤ 1초 | 현장(수십 대 규모) | ⏳ 현장 | — |
| PQ-004 드리프트 경고 | 경고·운영자 인지 | 실장비 1.35s 이탈→경고·로그·화면 표시로 시연(OQ-022b/023). 실운영 재확인은 현장 | ◐ 부분 | 2026-06-22 |
| PQ-005 산출물 승인 흐름 | 전이·이력 | 미실행 — `/api/deliverables` 생성·상태전이로 별도 수행 가능 | ⏳ 보류 | — |

## 9. 승인

| 역할 | 이름 | 서명 | 일자 |
|------|------|------|------|
| 실행(검증) | | | |
| 검토(QA) | | | |

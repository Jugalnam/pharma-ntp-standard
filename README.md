# pharma-ntp-standard

폐쇄망 GMP(제약) 환경에서, 한국표준과학연구원 **KRISS 표준시**를 기준으로 사내 장비들의 **NTP 시각 동기 상태를 실시간 감시·검증**하는 웹 애플리케이션입니다.
GMP 데이터 무결성(ALCOA+) 및 컴퓨터 시스템 검증(CSV)을 전제로 **V 모델(GAMP 5)** 에 따라 설계합니다.

> ⚠️ 본 프로젝트는 오픈소스 참조 구현이며 공식 인증 제품이 아닙니다. 실제 규제 환경 적용 시 별도 검증이 필요합니다.

## 이 시스템은 무엇인가 — 그리고 무엇이 아닌가

- ✅ **하는 것** — 등록된 장비들이 KRISS 기준으로 시각이 맞는지 **읽기 전용으로 감시**하고, 하나의 대시보드에 실시간 표시하며, 허용 한계를 벗어나면 로그로 기록합니다.
- ❌ **하지 않는 것** — 시각을 **배포하지 않습니다(이 시스템은 NTP 서버가 아닙니다).** 장비의 시각·설정을 바꾸지 않습니다. 시각 배포는 기존 인프라(사내 NTP/AD 서버 등)가 담당하고, 이 시스템은 그것이 **제대로 동작하는지 감시·검증**만 합니다.

> "감시자와 피감시자를 분리"하는 설계라, GMP 환경에서 검증·감사 방어가 쉽고, 검증된 측정 장비에 아무것도 설치하지 않아 안전합니다.

## 왜 필요한가

GxP 환경에서는 모든 전자 기록에 신뢰할 수 있는 타임스탬프가 요구됩니다(21 CFR Part 11, EU Annex 11).
모든 장비가 단일 신뢰 시간 소스에 동기화되어야 하고, **그 동기 상태가 지속적으로 감시·기록·검증**되어야 합니다. 이 앱은 그 "감시·검증" 계층을 담당합니다.

## 핵심 기능

- **실시간 동기화 대시보드** — 등록 장비의 KRISS 기준 오프셋·stratum·마지막 동기화·상태(정상 / 한계 초과 / 응답 없음 / 갱신 지연)를 백그라운드 스케줄러가 자동 폴링하고 화면이 자동 갱신
- **장비 등록(응답 검증)** — IP가 NTP에 응답할 때만 등록(죽은 장비가 등록부에 들어가지 않도록), 인라인 추가/삭제
- **동기화 설정** — 폴링 주기·허용 한계를 화면에서 조정
- **허용 한계 초과 로그** — 한계 초과 이벤트를 장비·측정 오프셋·당시 한계·시각과 함께 기록(진행 중 ↔ 해제됨)
- **검증 산출물(IQ/OQ/PQ)** — V 모델 검증 단계 산출물 관리

> **측정 원리**: 로컬 시계 미신뢰 원칙에 따라 장비 오프셋을 `(장비 vs PC) − (KRISS vs PC) = 장비 vs KRISS` 로 보정해, 모니터링 PC 자체 시계 오차를 상쇄합니다.

## 기준 표준 / 배포 형상

- **기준**: KRISS UTC(k) (`time.kriss.re.kr`). 공식 동기화 프로그램 UTCk를 참조 기준으로 삼습니다(UTCk 바이너리는 타사 프로그램이므로 미포함).
- **배포(자세 A)**: 단일 망(폐쇄망)에서 인터넷 되는 대역에 **감시 전용 PC 1대**를 두고, KRISS로의 아웃바운드 NTP(UDP 123)만 허용하는 보안 하드닝을 적용합니다. 상세는 [`docs/03`](docs/03-design-spec.md)·[`docs/04`](docs/04-risk-assessment.md) 참조.

## 기술 스택

- **Frontend**: React + Vite + TypeScript
- **Backend**: FastAPI (Python)
- **저장소**: 인메모리(현재 골격) → SQLite → PostgreSQL 전환 예정

## 저장소 구조

```
pharma-ntp-standard/
├── docs/        # V 모델 산출물 (URS, FS, DS, RA, RTM, IQ/OQ/PQ)
├── backend/     # FastAPI 애플리케이션
└── frontend/    # React/Vite 클라이언트
```

## 문서 (V 모델 산출물)

설계는 코드보다 [`docs/`](docs/README.md) 의 산출물이 먼저입니다. 시작점은 [docs/README.md](docs/README.md) 입니다.

## 개발 시작

```bash
# Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 라이선스

[MIT](LICENSE)

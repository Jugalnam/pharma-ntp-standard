# pharma-ntp-standard

제약회사(GxP) 환경에서 **NTP 시간 동기화 표준을 수립·모니터링·검증**하기 위한 웹 애플리케이션입니다.
GMP 데이터 무결성(ALCOA+) 및 컴퓨터 시스템 검증(CSV) 요구사항을 전제로 **V 모델(GAMP 5)** 에 따라 설계합니다.

> ⚠️ 본 프로젝트는 오픈소스 참조 구현입니다. 실제 규제 환경에 적용하려면 해당 기관의 품질 시스템에 맞춘 검증이 별도로 필요합니다.

## 왜 필요한가

GxP 환경에서는 모든 전자 기록에 신뢰할 수 있는 타임스탬프가 요구됩니다(21 CFR Part 11, EU Annex 11).
이를 위해 모든 장비·시스템이 **단일 신뢰 시간 소스**에 동기화되어야 하며, 그 상태가 지속적으로 모니터링·검증되어야 합니다.
이 앱은 (1) 동기화 표준 정의, (2) 실시간 모니터링, (3) 검증 산출물(IQ/OQ/PQ) 관리를 한 곳에서 제공합니다.

### 기준 표준

신뢰 시간 기준은 **한국표준과학연구원(KRISS)의 UTC(KRISS)** 이며, KRISS 공식 동기화 프로그램 **UTCk**(`time.kriss.re.kr`)를 참조 기준으로 삼습니다.
본 프로젝트는 공식 인증 제품이 **아니며**, UTCk에 *준하는* 오픈소스 참조 구현입니다. (UTCk 바이너리 자체는 타사 프로그램이므로 본 저장소에 포함하지 않습니다.)

## 핵심 기능 (범위)

- **동기화 모니터링 대시보드** — 등록 장비의 NTP 오프셋·드리프트·stratum을 수집하고 허용 한계 초과 시 경고
- **표준 / SOP · 장비 관리** — 신뢰 시간 소스, 허용 편차, 폴링 주기 등 표준 정의 및 장비 등록·분류·정책 배포
- **검증 산출물 관리(IQ/OQ/PQ)** — V 모델 검증 단계 산출물의 생성·승인·추적

## 기술 스택

- **Frontend**: React + Vite + TypeScript
- **Backend**: FastAPI (Python)
- **DB**: SQLite(개발) → PostgreSQL(운영)

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

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

제약(GxP) 환경에서 **NTP 시간 동기화 표준을 수립·모니터링·검증**하는 웹 앱이다. 기준 시간 소스는 한국표준과학연구원의 **UTC(KRISS)** (`time.kriss.re.kr`)이며, GMP 데이터 무결성(ALCOA+) / CSV 요구사항을 전제로 **GAMP 5 V 모델**에 따라 설계한다. 현재는 **인메모리 골격** 단계다(영속 저장소·폴링 워커·감사 추적 미연결).

> 공식 인증 제품이 **아니라** UTCk에 *준하는* 오픈소스 참조 구현이다(`README.md`). 실제 규제 환경 적용 시 별도 검증이 필요하다는 전제를 코드/문서 변경 시 깨지 않게 유지한다.

## 명령어

### Backend (`backend/`)
```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000 (Swagger: /docs)
pytest                                  # 전체 테스트
pytest tests/test_alerts.py             # 단일 파일
pytest tests/test_alerts.py::test_is_offset_breach   # 단일 테스트
```
테스트는 `test_alerts.py`(경계값/RISK-001), `test_monitor.py`(모니터링 엔진·상태 전이), `test_api.py`(엔드포인트·httpx) 세 파일이다.
`is_offset_breach`에는 doctest가 있으나 기본 pytest 실행에는 포함되지 않는다(`--doctest-modules`로 별도 실행).
`pytest.ini`/`conftest.py`/`pyproject.toml`이 없다 — 기본 discovery에 의존하므로 **`backend/`에서** 실행해야 import가 풀린다. `requirements.txt`도 `backend/`에 있다.

### Frontend (`frontend/`)
```bash
npm install
npm run dev        # Vite. /api 요청은 localhost:8000(백엔드)로 프록시
npm run build      # tsc -b && vite build
npm run lint       # eslint .
```
백엔드를 먼저 띄워야 대시보드/health가 동작한다. `/api` 프록시는 `vite.config.ts`, CORS는 `http://localhost:5173`만 허용(`app/main.py`).

## 아키텍처

3계층 구조 — `docs/`(설계 산출물) → `backend/`(FastAPI) → `frontend/`(React).
> 루트의 `UTCk/`·`UTCk.zip`은 KRISS 공식 동기화 프로그램(타사 바이너리) 참조본으로, `.gitignore`로 제외된 **코드베이스 외부** 자료다(분석은 `docs/05-utck-reference-analysis.md`).

**Backend 레이어** (`backend/app/`):
- `main.py` — FastAPI 진입점, CORS, 라우터 등록
- `config.py` — `Settings`(pydantic-settings). 환경변수 접두사 `NTP_`. 기준 호스트·기본 오프셋 한계 등
- `api/routes.py` — 모든 REST 엔드포인트(`/api` prefix). **인메모리 dict 저장소**(`_standards`/`_assets`/`_deliverables`)와 정수 시퀀스를 모듈 전역으로 보유
- `services/ntp.py` — `measure_offset()`: 다중 샘플 **중앙값**으로 오프셋 측정(RISK-004 완화)
- `services/alerts.py` — `is_offset_breach()`: 오프셋 한계 초과 판정. **경계 규칙: 한계와 같으면 합격, 초과해야 경고.** 이 프로젝트에서 가장 위험도 높은 로직(RISK-001)
- `services/monitor.py` — `Monitor`: 측정(ntp)과 경고 판정(alerts)을 연결하는 모니터링 엔진. 오프셋 샘플 기록, 경고 OPEN↔CLOSED 전이(FS-022/023), 대시보드 상태 `UNKNOWN/STALE/BREACH/OK` 산정. `STALE`은 last_sync 노후(=poll_interval×`STALE_FACTOR` 초과) 감지로 RISK-003 완화. `routes.py`가 전역 `monitor` 인스턴스 보유
- `models/schemas.py` — Pydantic 도메인 모델. `*In` 입력 모델을 상속해 `id`/`version` 추가하는 패턴

**Frontend** (`frontend/src/`): 라우터·컴포넌트 분리 없이 단일 `App.tsx` 골격이다. 마운트 시 `/api/health`(상태·기준 소스)와 `/api/dashboard`(장비별 오프셋/상태 행)를 fetch해 표시. 새 화면은 여기서 확장한다 — 별도 컴포넌트 디렉터리는 아직 없다.

**핵심 도메인 규칙:**
- 표준(`TimeStandard`)은 PUT 시 `version`이 증가한다(FS-002).
- 산출물(`Deliverable`) 상태는 `Draft → Reviewed → Approved → Effective` 순서로만 전이 가능. 건너뛰기·역방향은 409. 규칙은 `routes.py`의 `_TRANSITIONS` 딕셔너리에 정의(RISK-005).

## V 모델 추적성 규약 (이 저장소에서 가장 중요)

코드와 테스트는 **`docs/`의 검증 산출물 ID와 양방향으로 연결**되어 있다. 코드 주석/docstring/테스트에 박힌 `URS-xxx`, `FS-xxx`, `DS-xxx`, `RISK-xxx`, `IQ/OQ/PQ-xxx` 태그는 장식이 아니라 추적성 매트릭스(`docs/06-traceability-matrix.md`)의 실제 항목이다.

- 좌측 가지(분해): URS(요구) → FS(기능) → DS(설계) → 구현
- 우측 가지(검증): IQ(설치) ↔ DS, OQ(운영) ↔ FS, PQ(성능) ↔ URS
- **기능·위험을 추가/변경하면 대응하는 `docs/` 산출물과 RTM도 함께 갱신**해야 추적성이 깨지지 않는다. 새 테스트는 검증하는 OQ/PQ ID를 주석에 명시하는 관례를 따른다(`test_alerts.py`가 OQ-022a/b를 검증하는 식).
- High 위험(RISK-001 등)은 반드시 경계값 단위 테스트로 입증한다.

설계가 코드보다 먼저다 — 새 기능 작업 전 `docs/README.md`(산출물 00–11 인덱스가 권위 있는 지도)와 해당 산출물을 먼저 읽는다. 분석/근거 문서도 RTM 항목이다: `05`(UTCk 참조, REF) · `10`(KRISS 정합성 요약, VSR-001) · `11`(규제·산업 모범사례, REG).

## 후속 반복 예정 (현재 미구현)

모니터링 엔진은 구현됐고(수동 폴링 `POST /api/assets/{id}/poll` → 실측 → 대시보드/경고), OQ-020/021/022/023이 실측 검증을 통과했다. 남은 예정 작업: **주기적 백그라운드 폴링 스케줄러**(현재는 수동 트리거만), SQLAlchemy(SQLite→PostgreSQL) 전환, **감사 추적(FS-040, OQ-040 유보 중)** 및 표준 변경 이력(OQ-002 PARTIAL). 검증 진행 현황은 `docs/07-iq-protocol.md`·`docs/08-oq-protocol.md`의 결과 열 참조.

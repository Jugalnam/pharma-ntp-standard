# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

제약(GxP) 환경에서 **NTP 시간 동기화 표준을 수립·모니터링·검증**하는 웹 앱이다. 기준 시간 소스는 한국표준과학연구원의 **UTC(KRISS)** (`time.kriss.re.kr`)이며, GMP 데이터 무결성(ALCOA+) / CSV 요구사항을 전제로 **GAMP 5 V 모델**에 따라 설계한다. 시스템 영향도는 **직접 영향 시스템(Direct Impact System)** 으로 분류한다(VP §3.2, 2026-06-21) — 단 장비 시계를 *제어*하지 않는 **감시·읽기 전용** 경계를 가지며, 직접 영향의 대상은 데이터 무결성(감시·보고 기록)이다(RISK-001/011). 모니터링 엔진·자동 폴링 스케줄러·영속 저장소(SQLite)·전체화면 시계(FS-042)까지 **구현 완료** 단계이며, 전체 감사 추적은 범위 제외(한계 초과 로그로 대체) 결정이다.

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
`pytest.ini`/`pyproject.toml`은 없다 — 기본 discovery에 의존하므로 **`backend/`에서** 실행해야 import가 풀린다. `tests/conftest.py`는 테스트 전용 임시 SQLite(`test_ntp.sqlite3`)를 쓰도록 `NTP_DATABASE_URL`을 설정한다(개발/운영 DB와 분리). `requirements.txt`도 `backend/`에 있다.

### Frontend (`frontend/`)
```bash
npm install
npm run dev        # Vite. /api 요청은 localhost:8000(백엔드)로 프록시
npm run build      # tsc -b && vite build
npm run lint       # eslint .
```
백엔드를 먼저 띄워야 대시보드/health가 동작한다. `/api` 프록시는 `vite.config.ts`, CORS는 `http://localhost:5173`만 허용(`app/main.py`).

### 검증 문서 HTML 패키징 (`docs/`)
```bash
pip install markdown
python docs/build_html.py    # docs/*.md → 단일 자체완결 validation-package.html (외부 CDN 없음)
```
`docs/` 산출물(00–11 + 운영 매뉴얼)을 사이드바 목차가 있는 인쇄 친화적 HTML 한 파일로 묶는다. 산출물 추가·순서 변경 시 `build_html.py`의 파일 목록도 함께 갱신한다.

## 아키텍처

3계층 구조 — `docs/`(설계 산출물) → `backend/`(FastAPI) → `frontend/`(React).
> 루트의 `UTCk/`·`UTCk.zip`은 KRISS 공식 동기화 프로그램(타사 바이너리) 참조본으로, `.gitignore`로 제외된 **코드베이스 외부** 자료다(분석은 `docs/05-utck-reference-analysis.md`).

**Backend 레이어** (`backend/app/`):
- `main.py` — FastAPI 진입점, CORS, 라우터 등록. `lifespan`에서 DB 초기화(`init_db`)·경고 로그 복원(`hydrate_from_db`) 후 폴링 스케줄러 기동(`scheduler_enabled`로 토글)
- `config.py` — `Settings`(pydantic-settings). 환경변수 접두사 `NTP_`. 기준 호스트·기본 오프셋 한계 등
- `api/routes.py` — 모든 REST 엔드포인트(`/api` prefix). **SQLAlchemy 영속 저장소**(표준/장비/산출물/한계초과 로그)를 `get_db` 세션으로 접근. 한계초과 로그는 폴링 후 DB write-through, 기동 시 `hydrate_from_db`로 복원
- `db.py` / `models/orm.py` — SQLAlchemy 엔진·세션·Base / ORM 모델(StandardORM·StandardHistoryORM·AssetORM·DeliverableORM·AlertORM)
- `services/ntp.py` — `measure_offset()`: 다중 샘플 **중앙값**으로 오프셋 측정(RISK-004 완화). `is_plausible_offset()`: 비현실적으로 큰 오프셋을 스푸핑/이상치로 보고 미신뢰(FS-052/RISK-009, 한계는 `ntp_sanity_bound_ms`)
- `services/alerts.py` — `is_offset_breach()`: 오프셋 한계 초과 판정. **경계 규칙: 한계와 같으면 합격, 초과해야 경고.** 이 프로젝트에서 가장 위험도 높은 로직(RISK-001)
- `services/monitor.py` — `Monitor`: 측정(ntp)과 경고 판정(alerts)을 연결하는 모니터링 엔진. 오프셋 샘플 기록, 경고 OPEN↔CLOSED 전이(FS-022/023), 대시보드 상태 `UNKNOWN/UNREACHABLE/STALE/BREACH/OK` 산정. `STALE`은 last_sync 노후(=poll_interval×`STALE_FACTOR` 초과) 감지로 RISK-003 완화. `routes.py`가 전역 `monitor` 인스턴스 보유
- `models/schemas.py` — Pydantic 도메인 모델. `*In` 입력 모델을 상속해 `id`/`version` 추가하는 패턴

**Frontend** (`frontend/src/`): 라우터·컴포넌트 분리 없이 단일 `App.tsx` 골격이다. 마운트 시 `/api/health`(상태·기준 소스)와 `/api/dashboard`(장비별 오프셋/상태 행)를 fetch해 표시. 새 화면은 여기서 확장한다 — 별도 컴포넌트 디렉터리는 아직 없다.

**핵심 도메인 규칙:**
- 표준(`TimeStandard`)은 PUT 시 `version`이 증가하고, 매 변경이 `standard_history` 테이블에 스냅샷+사유로 기록된다(`_record_standard_history`). 이력은 `GET /api/standards/{sid}/history`로 조회(FS-002, OQ-002).
- 산출물(`Deliverable`) 상태는 `Draft → Reviewed → Approved → Effective` 순서로만 전이 가능. 건너뛰기·역방향은 409. 규칙은 `routes.py`의 `_TRANSITIONS` 딕셔너리에 정의(RISK-005).
- `GET /api/time`은 KRISS 기준 시각을 1회 측정해 반환한다(FS-041, 프론트 대형 시계용). server UTC에 KRISS 오프셋을 보정한 '신뢰 시간'을 주며, NTP 도달 실패나 sanity 한계 초과 시 `synced=false`로 server 시각을 폴백한다(로컬 시계 미신뢰 원칙).

## V 모델 추적성 규약 (이 저장소에서 가장 중요)

코드와 테스트는 **`docs/`의 검증 산출물 ID와 양방향으로 연결**되어 있다. 코드 주석/docstring/테스트에 박힌 `URS-xxx`, `FS-xxx`, `DS-xxx`, `RISK-xxx`, `IQ/OQ/PQ-xxx` 태그는 장식이 아니라 추적성 매트릭스(`docs/06-traceability-matrix.md`)의 실제 항목이다.

- 좌측 가지(분해): URS(요구) → FS(기능) → DS(설계) → 구현
- 우측 가지(검증): IQ(설치) ↔ DS, OQ(운영) ↔ FS, PQ(성능) ↔ URS
- **기능·위험을 추가/변경하면 대응하는 `docs/` 산출물과 RTM도 함께 갱신**해야 추적성이 깨지지 않는다. 새 테스트는 검증하는 OQ/PQ ID를 주석에 명시하는 관례를 따른다(`test_alerts.py`가 OQ-022a/b를 검증하는 식).
- High 위험(RISK-001 등)은 반드시 경계값 단위 테스트로 입증한다.

설계가 코드보다 먼저다 — 새 기능 작업 전 `docs/README.md`(산출물 00–11 인덱스가 권위 있는 지도)와 해당 산출물을 먼저 읽는다. 분석/근거 문서도 RTM 항목이다: `05`(UTCk 참조, REF) · `10`(KRISS 정합성 요약, VSR-001) · `11`(규제·산업 모범사례, REG).

## 후속 반복 예정 (현재 미구현)

모니터링 엔진은 구현됐다 — 폴링은 장비 자신(`asset.hostname`)을 질의하고 오프셋을 KRISS 기준으로 보정(장비vsKRISS=(장비vsPC)−(KRISSvsPC), 로컬 시계 미신뢰)하며, 무응답은 `UNREACHABLE`로 구분한다(FS-020). 수동 `POST /api/assets/{id}/poll`과 **자동 백그라운드 스케줄러(FS-024, 병렬 폴링)** 둘 다 동작하고, 프론트 대시보드는 주기적으로 자동 갱신한다. 장비 등록은 NTP 응답 검증 후만 허용(FS-010), 폴링 주기·허용 한계는 화면에서 수정 가능(FS-001), 한계 초과는 **로그(FS-023, `/api/alerts` + 화면 표)** 로 기록한다. 배포는 자세 A(인터넷 ON) + 보안 하드닝(FS-050~052, DS-040): egress는 KRISS UDP 123만 화이트리스트, 앱은 localhost 바인딩, 장비엔 읽기 전용. **감사 추적(FS-040/URS-040)은 범위 제외 결정(2026-06-20)** — 한계 초과 로그로 핵심 이벤트 기록 대체. **영속 저장소(SQLAlchemy/SQLite)는 구현 완료** — 표준·장비·산출물·한계초과 로그·**표준 변경 이력**이 재시작 후에도 유지(OQ-028). 표준 변경 이력(OQ-002)도 구현 완료(`standard_history`). 남은 예정 작업: PostgreSQL 운영 전환, 보안 OQ-050~052 현장 실행. 검증 진행 현황은 `docs/07-iq-protocol.md`·`docs/08-oq-protocol.md`의 결과 열 참조.

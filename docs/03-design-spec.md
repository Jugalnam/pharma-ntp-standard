# 설계 명세 (Design Specification, DS)

| 항목 | 내용 |
|------|------|
| 문서 ID | DS-001 |
| 버전 | 0.1 (Draft) |
| V 모델 대응 | 설치 적격성(IQ) |

## 1. 개요

본 문서는 [FS](02-functional-spec.md)를 구현하기 위한 아키텍처·데이터 모델·인터페이스 설계를 정의한다. 각 DS는 [IQ](07-iq-protocol.md)에서 설치/구성이 검증된다.

## 2. 아키텍처 (DS-001)

```
[브라우저] ──HTTP──> [React/Vite SPA] ──REST/JSON──> [FastAPI] ──> [DB: SQLite/PostgreSQL]
                                                         │
                                                  [폴링 워커] ──NTP──> [장비 / 시간 소스]
```

- **Frontend**: React + Vite + TypeScript. 라우팅, 대시보드, 표준/장비/검증 관리 화면.
- **Backend**: FastAPI. 계층 — `api`(라우터) / `services`(도메인 로직) / `models`(ORM·스키마).
- **폴링 워커**: 백그라운드 태스크가 장비별 NTP 오프셋을 측정(초기: `ntplib`).
- **DB**: 개발 SQLite, 운영 PostgreSQL. SQLAlchemy ORM으로 추상화.

## 3. 데이터 모델 (DS-010)

| 엔터티 | 주요 필드 | 비고 |
|--------|----------|------|
| `TimeStandard` | id, name, source_host(기본 `time.kriss.re.kr`), max_offset_ms, poll_interval_s, version | FS-001/002, KRISS UTC(k) 기준 |
| `Asset` | id, name, hostname, gxp_critical, standard_id | FS-010~012 |
| `OffsetSample` | id, asset_id, measured_at, offset_ms, stratum | FS-020/021 |
| `Alert` | id, asset_id, opened_at, closed_at, offset_ms, status | FS-022/023 |
| `Deliverable` | id, type(IQ/OQ/PQ), title, status, requirement_tags | FS-030~032 |
| `AuditEntry` | id, entity, entity_id, action, actor, reason, at | append-only, FS-040 |

## 4. API 설계 (DS-020)

| 메서드 | 경로 | 기능 | FS |
|--------|------|------|----|
| GET/POST | `/api/standards` | 표준 목록/생성 | FS-001 |
| GET/PUT | `/api/standards/{id}` | 표준 조회/수정(버전 증가) | FS-001/002 |
| GET/POST | `/api/assets` | 장비 목록/등록 | FS-010 |
| GET | `/api/dashboard` | 장비별 최신 오프셋·상태 | FS-021 |
| GET | `/api/alerts` | 경고 이력 | FS-023 |
| GET/POST | `/api/deliverables` | 검증 산출물 | FS-030 |
| GET | `/api/health` | 헬스체크 | IQ |

## 5. 상태 전이 (DS-030)

- 산출물: `Draft → Reviewed → Approved → Effective` (역방향/건너뛰기 불가) — FS-031
- 경고: `OPEN → CLOSED` (오프셋이 한계 내로 복귀 시) — FS-022

## 6. 기술/구성 항목 (IQ 대상)

| 구성 항목 | 값/버전 | 검증 |
|----------|--------|------|
| Python | ≥ 3.11 | IQ |
| FastAPI / uvicorn | requirements.txt 고정 | IQ |
| Node.js | ≥ 20 | IQ |
| DB 연결 문자열 | 환경변수 `DATABASE_URL` | IQ |
| NTP 소스 도달성 | 구성된 source_host | IQ |

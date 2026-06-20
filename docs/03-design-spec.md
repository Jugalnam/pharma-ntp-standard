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
- **DB**: SQLAlchemy ORM. 개발 SQLite(`pharma_ntp.sqlite3`), 운영 PostgreSQL(`NTP_DATABASE_URL`만 변경). **영속 대상: 표준·장비·산출물·한계초과 로그.** 실시간 측정값(오프셋·도달성·last_attempt)은 폴링으로 재생성되므로 모니터링 엔진 인메모리에 두고, 한계초과 로그는 DB와 write-through하며 기동 시 복원한다.

## 3. 데이터 모델 (DS-010)

| 엔터티 | 주요 필드 | 비고 |
|--------|----------|------|
| `TimeStandard` | id, name, source_host(기본 `time.kriss.re.kr`), max_offset_ms, poll_interval_s, version | FS-001/002, KRISS UTC(k) 기준 |
| `Asset` | id, name, hostname, gxp_critical, standard_id | FS-010~012 |
| `OffsetSample` | asset_id, measured_at, offset_ms, stratum | FS-020/021, **인메모리**(폴링 재생성) |
| `Alert` | id, asset_id, asset_name, opened_at, closed_at, offset_ms, limit_ms, status | FS-022/023, **영속**(한계초과 로그) |
| `Deliverable` | id, type(IQ/OQ/PQ), title, status, requirement_tags | FS-030~032, 영속 |
| ~~`AuditEntry`~~ | — | **범위 제외(2026-06-20)** — Alert(한계초과 로그)로 핵심 이벤트 기록 대체 |

> 영속 테이블(`standards`/`assets`/`deliverables`/`alerts`)은 SQLAlchemy ORM([backend/app/models/orm.py])으로 정의되며, Pydantic 도메인 모델과 `from_attributes`로 변환된다.

## 4. API 설계 (DS-020)

| 메서드 | 경로 | 기능 | FS |
|--------|------|------|----|
| GET/POST | `/api/standards` | 표준 목록/생성 | FS-001 |
| GET/PUT | `/api/standards/{id}` | 표준 조회/수정(버전 증가) | FS-001/002 |
| GET/POST | `/api/assets` | 장비 목록/등록(POST `?validate=true`면 NTP 응답 확인 후 등록) | FS-010 |
| DELETE | `/api/assets/{id}` | 장비 등록 해제(모니터링 상태 정리) | FS-010 |
| POST | `/api/assets/{id}/poll` | 장비 1회 수동 폴링(reachable/reference_synced 반환) | FS-020 |
| GET | `/api/dashboard` | 장비별 IP·최신 오프셋·상태 | FS-021 |
| GET | `/api/alerts` | 경고 이력 | FS-023 |
| GET/POST | `/api/deliverables` | 검증 산출물 | FS-030 |
| GET | `/api/health` | 헬스체크 | IQ |

## 5. 상태 전이 (DS-030)

- 산출물: `Draft → Reviewed → Approved → Effective` (역방향/건너뛰기 불가) — FS-031
- 경고: `OPEN → CLOSED` (오프셋이 한계 내로 복귀 시) — FS-022

## 5a. 배포·보안 아키텍처 (DS-040)

자세 A(인터넷 ON) 배포 형상과 그 보안 통제를 정의한다(FS-050~052, URS-050~052).

```
                 ┌─ 인터넷 ── KRISS(time.kriss.re.kr)
                 │   ▲  아웃바운드 UDP 123 ONLY (egress 화이트리스트)
[모니터링 PC] ───┤
 (전용 호스트)   │   내부망(단일 L3, ping 가능)
 앱=localhost    └─ NTP 질의(mode3, 읽기) ──> 인터넷서버 / AD서버 / 장비1~5
   바인딩            (출발지=모니터링 PC IP, 목적지 123, 단방향)
```

| 통제 항목 | 설계 | 근거 위험 |
|----------|------|----------|
| Egress 제한 | 아웃바운드 방화벽: `time.kriss.re.kr:123/udp`만 허용, 그 외 인터넷 차단. 인바운드 인터넷 차단 | RISK-007 |
| 앱 바인딩 | uvicorn `--host 127.0.0.1`(기본) 또는 내부 IP, 노출 시 인증 게이트 | RISK-008 |
| 읽기 전용 | `ntplib` 클라이언트 요청(mode 3)만 사용. 시각 설정·mode 6/7 미구현 | RISK-011 |
| 방화벽 규칙 최소화 | 대역 간 규칙은 출발지=모니터링 PC IP, 목적지 포트=123 단방향으로 한정 | RISK-010 |
| 기준 무결성 | 다중 샘플 중앙값 + 범위 검증, stratum 확인 | RISK-009 |
| 호스트 격리 | 감시 전용 호스트(겸용 금지), 최소 권한, 패치/백신 | RISK-007 |

> 감시자(모니터링 PC)와 피감시자(장비·시간서버)를 분리한다. 시스템은 장비에 쓰기를 하지 않으므로 장비 검증상태·GxP 데이터에 영향을 주지 않는다.

## 6. 기술/구성 항목 (IQ 대상)

| 구성 항목 | 값/버전 | 검증 |
|----------|--------|------|
| Python | ≥ 3.11 | IQ |
| FastAPI / uvicorn | requirements.txt 고정 | IQ |
| Node.js | ≥ 20 | IQ |
| DB 연결 문자열 | 환경변수 `DATABASE_URL` | IQ |
| NTP 소스 도달성 | 구성된 source_host | IQ |

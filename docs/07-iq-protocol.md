# 설치 적격성 (Installation Qualification, IQ)

| 항목 | 내용 |
|------|------|
| 문서 ID | IQ-001 |
| 버전 | 0.1 (Draft) |
| V 모델 대응 | 설계 명세(DS) |
| 전제 | [DS](03-design-spec.md) §6 구성 항목 |

## 1. 목적

시스템이 명세된 환경에 올바르게 설치·구성되었음을 입증한다.

## 2. 테스트 케이스

| ID | 검증 항목 | 절차 | 기대 결과 | 결과 |
|----|----------|------|----------|------|
| IQ-001 | Python 버전 | `python --version` | ≥ 3.11 | ✅ PASS — Python 3.11.2 |
| IQ-002 | 백엔드 의존성 설치 | `pip install -r requirements.txt` | 오류 없이 완료 | ✅ PASS — fastapi 0.137.2 등 import 성공 |
| IQ-003 | Node 버전 | `node --version` | ≥ 20 | ✅ PASS — v24.15.0 |
| IQ-004 | 프런트 의존성 설치 | `npm install` | 오류 없이 완료 | ✅ PASS — node_modules 존재 |
| IQ-005 | 백엔드 기동 | `uvicorn app.main:app` 후 `GET /api/health` | `200 {"status":"ok"}` | ✅ PASS — `test_health` 통과(200, status=ok) |
| IQ-006 | DB 연결 | 기동 시 마이그레이션/테이블 생성 | 테이블 생성 확인 | ✅ PASS — 기동 시 `init_db()`가 SQLAlchemy 테이블 생성, SQLite 영속(`pharma_ntp.sqlite3`); 재시작 후 데이터 유지(OQ-028 연계) |
| IQ-007 | NTP 소스 도달성 | 구성된 `source_host`로 NTP 질의 | 응답 수신 | ✅ PASS — `time.kriss.re.kr` 응답, stratum 3, offset ≈ −3.07ms |

> 실행 기록: 2026-06-20 / 실행자: 개발(자동화) / 백엔드 테스트 스위트 `pytest` 27건 전체 통과.

## 3. 합격 기준

모든 IQ 케이스 통과. 일탈 발생 시 [일탈 기록](#4-일탈) 및 품질 검토.
→ **결과: 전 항목 PASS. IQ-006(DB 연결)은 SQLAlchemy/SQLite 영속 저장소 구현으로 검증 완료(일탈 #1 종료).**

## 4. 일탈

| 일탈 # | 케이스 | 내용 | 조치 | 상태 |
|--------|--------|------|------|------|
| 1 | IQ-006 | (해소됨) 초기 증분은 인메모리 골격이라 DB 연결 검증 대상이 없었음 | SQLAlchemy(SQLite) 전환 완료 후 IQ-006 재실행 → PASS | **Closed(2026-06-21)** |

## 5. 승인

| 역할 | 이름 | 서명 | 일자 |
|------|------|------|------|
| 실행 | (자동화) | — | 2026-06-20 |
| 검토(QA) | | | |

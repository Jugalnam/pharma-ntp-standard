# 운영 적격성 (Operational Qualification, OQ)

| 항목 | 내용 |
|------|------|
| 문서 ID | OQ-001 |
| 버전 | 0.1 (Draft) |
| V 모델 대응 | 기능 명세(FS) |
| 전제 | IQ 통과 |

## 1. 목적

시스템이 [FS](02-functional-spec.md)에 명세된 기능을 의도대로 수행함을 입증한다. High 위험([RA](04-risk-assessment.md)) 기능은 경계값을 포함해 집중 검증한다.

## 2. 테스트 케이스

| ID | 검증 기능(FS) | 절차 | 기대 결과 | 결과 |
|----|--------------|------|----------|------|
| OQ-001 | 표준 생성/조회 (FS-001) | 표준 생성(`time.kriss.re.kr`, 한계 1000ms) 후 조회 | 입력대로 저장·조회됨 | ✅ PASS — 라이브 생성·조회 |
| OQ-002 | 표준 버전 증가 (FS-002) | 표준 수정 | version +1, 변경 이력 1건 생성 | ⚠️ PARTIAL — version +1 PASS(`test_standard_create_and_version_bump`); 변경 이력은 미구현(일탈 #2) |
| OQ-010 | 장비 등록/분류 (FS-010/011) | 장비 등록, gxp_critical=true | 목록에 표시, 분류 저장 | ✅ PASS — 라이브 등록, gxp_critical=true 저장 |
| OQ-011 | 정책 할당 (FS-012) | 장비에 표준 연결 | 연결 반영 | ✅ PASS — standard_id 연결, 폴링에 사용 |
| OQ-020 | 오프셋 수집 (FS-020) | 폴링 1회 실행(`POST /api/assets/{id}/poll`) | OffsetSample 생성, 값 합리적 범위 | ✅ PASS — KRISS 라이브 offset −0.49ms, stratum 3 |
| OQ-021 | 대시보드 (FS-021) | `/api/dashboard` 호출 | 장비별 최신 오프셋·stratum·last_sync 반환 | ✅ PASS — offset/stratum/last_sync/status=OK 반환 |
| **OQ-022a** | 한계 **이내** (FS-022, RISK-001) | 오프셋 = 한계−1ms 주입 | 경고 **미발생**, 상태 OK | ✅ PASS — `test_oq022a_within_limit_no_alert` |
| **OQ-022b** | 한계 **초과** (FS-022, RISK-001) | 오프셋 = 한계+1ms 주입 | 경고 **발생**, 상태 BREACH | ✅ PASS — `test_oq022b_over_limit_breach` |
| OQ-023 | 경고 해제·이력 (FS-023) | 오프셋 복귀 | 경고 CLOSED, 이력 보존 | ✅ PASS — `test_oq023_alert_close_and_history` |
| OQ-030 | 산출물 생성 (FS-030) | 산출물 생성 | 저장·조회됨 | ✅ PASS — `test_deliverable_*` |
| OQ-031 | 상태 전이 규칙 (FS-031, RISK-005) | Draft→Approved 직접 전이 시도 | 거부(Reviewed 거쳐야 함) | ✅ PASS — `test_deliverable_invalid_transition_rejected`(409) |
| OQ-040 | 감사 추적 (FS-040, RISK-006) | 표준 변경 | AuditEntry append, 수정 불가 | ❌ DEFERRED — 감사 추적 미구현(일탈 #3, 후속 증분) |
| OQ-041 | 기준 시각 표시 (FS-041) | `GET /api/time` 호출, 대시보드 대형 시계 확인 | `synced=true`·`reference_utc`·stratum 유효(편차 ≤ 표준 한계). NTP 불가 시 `synced=false` 폴백 표시 | ✅ PASS — 라이브 stratum 3, offset +0.19ms, `reference_utc` 반환; 단일 샘플 실패 시 `synced=false` 폴백 동작 확인 |

> 추가 검증: RISK-003(폴링 중단) 완화로 last_sync 노후 시 상태 `STALE` 반환 — `test_risk003_stale_detection` PASS. 백엔드 스위트 `pytest` 17건 전체 통과.

## 3. UTCk 교차 점검(참고)

OQ-020/021에서 수집된 시스템 기준 시각을 **UTCk가 표시하는 KRISS 시각과 비교**하여, 본 시스템의 기준 측정이 KRISS UTC(k)에 정합함을 보조 확인한다(차이 ≤ 표준 허용 한계).

## 4. 합격 기준

모든 OQ 케이스 통과(High 위험 케이스 OQ-022a/b는 필수). 일탈은 기록·평가.
→ **결과: High 위험 OQ-022a/b·OQ-023(RISK-001) 전부 PASS. 기능 케이스 10/13 PASS, 1 PARTIAL(OQ-002), 2 미충족(OQ-040 및 OQ-002 이력)은 감사 추적 미구현에 따른 계획된 유보. 핵심 모니터링 기능 및 기준 시각 표시(OQ-041)는 합격.**

## 5. 일탈

| 일탈 # | 케이스 | 내용 | 조치 | 상태 |
|--------|--------|------|------|------|
| 2 | OQ-002 | 표준 수정 시 version은 증가하나 변경 이력(사유/승인) 레코드 미생성 | 감사 추적(FS-040) 구현 시 변경 이력 연동 | Open(계획됨) |
| 3 | OQ-040 | AuditEntry(append-only 감사 추적) 미구현 → 변경 추적·무결성 검증 불가 | 후속 증분에서 FS-040 구현 후 OQ-040 실행 | Open(계획됨) |

> 두 일탈 모두 [URS](01-user-requirements.md) §7 주석 및 [DS](03-design-spec.md) 설계에서 "후속 반복"으로 명시된 범위로, 본 증분의 합격을 막지 않는다(중대 일탈 아님).

## 6. 실행 기록 / 승인

| 역할 | 이름 | 서명 | 일자 |
|------|------|------|------|
| 실행(검증) | (자동화) | — | 2026-06-20 |
| 검토(QA) | | | |

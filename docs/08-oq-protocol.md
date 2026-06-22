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
| OQ-002 | 표준 버전 증가·변경 이력 (FS-002) | 표준 수정(사유 포함) 후 이력 조회 | version +1, 버전별 변경 이력(값 스냅샷·사유) 기록 | ✅ PASS — `test_oq002_standard_change_history`: v1(최초 생성)→v2(사유 "한계 강화") 기록, `GET /standards/{id}/history`·화면 표 동작. 행위자는 인증 부재로 `system`(한계) |
| OQ-010 | 장비 등록/분류 (FS-010/011) | 장비 등록, gxp_critical=true | 목록에 표시, 분류 저장 | ✅ PASS — 라이브 등록, gxp_critical=true 저장 |
| OQ-026 | 응답 검증 등록 (FS-010) | `validate=true`로 응답/무응답 호스트 각각 등록 시도 | 응답 호스트만 201, 무응답은 422 거부 | ✅ PASS — 라이브: 공개 NTP 20개 시도 → 16 등록/4 거부; `test_asset_create_no_validate_and_delete`(validate=false 우회) |
| OQ-027 | 장비 삭제 (FS-010) | 등록 장비 DELETE 후 재삭제 | 1차 204, 모니터링 상태 정리, 2차 404 | ✅ PASS — `test_asset_create_no_validate_and_delete` |
| OQ-011 | 정책 할당 (FS-012) | 장비에 표준 연결 | 연결 반영 | ✅ PASS — standard_id 연결, 폴링에 사용 |
| OQ-020 | 오프셋 수집·KRISS 보정 (FS-020) | 응답 장비 폴링(`POST /api/assets/{id}/poll`) | 장비 vs KRISS 보정 오프셋 생성, `reachable=true` | ✅ PASS — `test_oq020_poll_per_device_corrected`; 라이브: time.windows.com 보정 offset +0.33ms(원시 KRISS 7673ms 상쇄), stratum 3 |
| OQ-024 | 장비 무응답 감지 (FS-020, RISK-003) | 무응답 호스트(예 192.0.2.1) 폴링 | `reachable=false`·상태 `UNREACHABLE`, 거짓 측정값 없음 | ✅ PASS — `test_oq020_unreachable_*`; 라이브: 192.0.2.1 → UNREACHABLE, offset null |
| OQ-025 | 자동 폴링 스케줄러 (FS-024, RISK-003) | 장비 등록만 하고 수동 폴링 없이 대기 | `poll_interval_s` 경과 시 스케줄러가 자동 측정, 대시보드 자동 갱신 | ✅ PASS — `test_fs024_*`(due 판정·last_attempt); 라이브: tick 2s·주기 5s, 등록 직후 UNKNOWN → 무측정 대기 후 자동 OK 갱신 |
| OQ-028 | 영속 저장 (DS-010 SQLite) | 표준·장비 등록 및 한계 초과 발생 후 백엔드 재시작 | 표준·장비·한계초과 로그가 재시작 후에도 유지(DB 복원) | ✅ PASS — `test_persistence_standard_survives_new_session`; 라이브: 재시작 후 표준·장비 2대·로그 1건 그대로 복원 |
| OQ-021 | 대시보드 (FS-021) | `/api/dashboard` 호출 | 장비별 최신 오프셋·stratum·last_sync 반환 | ✅ PASS — offset/stratum/last_sync/status=OK 반환 |
| **OQ-022a** | 한계 **이내** (FS-022, RISK-001) | 오프셋 = 한계−1ms 주입 | 경고 **미발생**, 상태 OK | ✅ PASS — `test_oq022a_within_limit_no_alert` |
| **OQ-022b** | 한계 **초과** (FS-022, RISK-001) | 오프셋 = 한계+1ms 주입 | 경고 **발생**, 상태 BREACH | ✅ PASS — `test_oq022b_over_limit_breach` |
| OQ-023 | 한계 초과 로그·해제 (FS-023) | 오프셋 초과→복귀 | 로그에 장비명·오프셋·한계 기록, OPEN→CLOSED 전이, 이력 보존 | ✅ PASS — `test_oq023_*`·`test_breach_log_has_name_and_limit`; 라이브: 한계 5ms에서 3건 기록(OPEN 2·CLOSED 1), 화면 로그 표시 |
| OQ-030 | 산출물 생성 (FS-030) | 산출물 생성 | 저장·조회됨 | ✅ PASS — `test_deliverable_*` |
| OQ-031 | 상태 전이 규칙 (FS-031, RISK-005) | Draft→Approved 직접 전이 시도 | 거부(Reviewed 거쳐야 함) | ✅ PASS — `test_deliverable_invalid_transition_rejected`(409) |
| OQ-040 | 감사 추적 (FS-040, RISK-006) | — | — | ⛔ 범위 제외(2026-06-20) — 전체 감사 추적 미채택, [FS-023] 한계 초과 로그(OQ-023)로 핵심 이벤트 기록 대체 |
| OQ-041 | 기준 시각 표시 (FS-041) | `GET /api/time` 호출, 대시보드 대형 시계 확인 | `synced=true`·`reference_utc`·stratum 유효(편차 ≤ 표준 한계). NTP 불가 시 `synced=false` 폴백 표시 | ✅ PASS — 라이브 stratum 3, offset +0.19ms, `reference_utc` 반환; 단일 샘플 실패 시 `synced=false` 폴백 동작 확인 |
| OQ-042 | 전체화면 시계 (FS-042) | 전체화면 진입(버튼)·해제(ESC/✕), 장시간 표시 시 화면 절전 여부, 미검증 시 상태 표시 확인 | 전체화면 전환 동작, Wake Lock으로 화면 유지, `synced=false`면 미검증(주황) 표시 | ✅ PASS — 수동 UI 확인: 진입/해제·Wake Lock 동작, 동기화 상태(양호/미검증) 상시 표시(`clock--stale` 재사용) |
| OQ-050 | Egress 제한 (FS-050, RISK-007) | 모니터링 PC에서 KRISS 외 임의 외부 주소로 통신 시도(예: 웹/타 포트) 및 KRISS UDP 123 질의 | KRISS:123/udp만 성공, 그 외 외부 통신·인바운드 차단 | ⏳ 현장 범위(참조 구현 외) — 현장 방화벽 구성 후 실행. **운영 승인 전 필수** |
| OQ-051 | 읽기 전용 동작 (FS-051, RISK-011) | 폴링 실행 전후 대상 장비의 시각·NTP 설정 비교 | 장비 시각·설정 무변경(질의만 발생) | ⏳ 현장 범위(참조 구현 외) — 현장 장비 대상 실행 |
| OQ-052 | 접근 통제 (FS-050/052, RISK-008) | 외부 인터페이스에서 API 접근 시도, 내부 바인딩·인증 확인 | 외부 노출 없음, 미인증 접근 거부 | ⏳ 현장 범위(참조 구현 외) — 배포 형상 확정 후 실행 |

> 추가 검증: RISK-003(폴링 중단) 완화로 last_sync 노후 시 상태 `STALE` 반환 — `test_risk003_stale_detection` PASS. 백엔드 스위트 `pytest` 27건 전체 통과.
>
> 재실행(이 PC, 2026-06-22): `pytest` **29건 전체 통과**. 실장비(Label PC, 192.0.6.144) 대상 OQ-020/021/022b/023/025/041 라이브 재확인, OQ-052(127.0.0.1 단독 바인딩·외부 거부) 라이브 통과, OQ-051은 부분(코드 mode3 근거). 상세 증빙: [현장 검증 런북 §8](field-validation-runbook.md).

## 3. UTCk 교차 점검(참고)

OQ-020/021에서 수집된 시스템 기준 시각을 **UTCk가 표시하는 KRISS 시각과 비교**하여, 본 시스템의 기준 측정이 KRISS UTC(k)에 정합함을 보조 확인한다(차이 ≤ 표준 허용 한계).

## 4. 합격 기준

모든 OQ 케이스 통과(High 위험 케이스 OQ-022a/b는 필수). 일탈은 기록·평가.
→ **결과: High 위험 OQ-022a/b·OQ-023(RISK-001) 전부 PASS. 기능 케이스 전부 PASS(OQ-002 변경 이력 포함). OQ-040(전 엔터티 전체 감사 추적)만 범위 제외 결정(한계 초과 로그로 대체). 핵심 모니터링·기준 시각 표시(OQ-041)·영속 저장(OQ-028) 합격. 보안 OQ-050~052는 현장 배포 범위.**

> 보안 케이스 OQ-050~052는 **배포 네트워크 환경(방화벽·내부망)에 의존**하므로 현장 설치 시 실행한다. 그중 High 위험 RISK-007을 검증하는 **OQ-050은 운영 승인 전 필수**다. 본(개발) 증분에서는 설계·통제 정의(DS-040)까지 완료, 실행은 현장으로 계획됨.

## 5. 일탈

| 일탈 # | 케이스 | 내용 | 조치 | 상태 |
|--------|--------|------|------|------|
| 2 | OQ-002 | (해소됨) 표준 변경 이력(값 스냅샷·사유) 미생성 | 변경 이력 테이블·API(`/standards/{id}/history`)·화면 표 구현(2026-06-21), `test_oq002_standard_change_history` PASS | **Closed(구현 완료)** |
| 3 | OQ-040 | 전 엔터티 전체 감사 추적 미구현 | **범위 제외 결정(2026-06-20)** — 한계 초과 로그(FS-023/OQ-023)로 핵심 이벤트 기록 대체. 실 규제 적용 시 Part 11 별도 검토 | Closed(범위 제외) |

> 일탈 #2는 변경 이력 구현으로 Closed, #3(전 엔터티 감사 추적)은 범위 제외로 Closed. 본 검증의 합격을 막는 중대 일탈은 없다.

## 6. 실행 기록 / 승인

| 역할 | 이름 | 서명 | 일자 |
|------|------|------|------|
| 실행(검증) | (자동화) | — | 2026-06-20 |
| 검토(QA) | | | |

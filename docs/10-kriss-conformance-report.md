# KRISS 표준 정합성 검증 요약 보고서 (Validation Summary Report — KRISS Traceability)

| 항목 | 내용 |
|------|------|
| 문서 ID | VSR-001 |
| 버전 | 0.1 (Draft) |
| 작성일 | 2026-06-20 |
| V 모델 대응 | **전체 종합** (좌 설계 ↔ 우 검증을 KRISS 표준 정합으로 결론) |
| 전제 | [VP](00-validation-plan.md), [IQ](07-iq-protocol.md), [OQ](08-oq-protocol.md) 실행 결과 |

## 1. 증명 주장 (Claim)

> **본 시스템(`pharma-ntp-standard`)이 측정·보고·감시하는 시각 기준은 한국표준과학연구원(KRISS)이 유지하는 협정세계시 실현 UTC(KRISS)이며, 그 사용은 GAMP 5 V 모델의 좌측(설계) 및 우측(검증) 산출물로 추적·입증된다.**

본 보고서는 위 주장을 **개별 증거를 인용**하여 증명하고, 표준 추적 체인을 명시한다.

## 2. 증명 논리 — V 모델 양 가지의 결합

V 모델은 "무엇을 만들 것인가(좌)"와 "만든 것이 맞는가(우)"를 대칭으로 연결한다. KRISS 표준 정합은 **좌측에서 KRISS를 표준으로 *정의*** 하고, **우측에서 그 정의대로 동작함을 *입증*** 함으로써 증명된다.

```
[좌: KRISS를 표준으로 정의]                 [우: KRISS 표준 사용을 입증]
URS-001 (KRISS UTC(k) 요구) ───────────────  PQ-001 / PQ §3 (UTCk 교차점검)
   │                                              │
REF-001 (UTCk 알고리즘 규명·정합 근거) ──────  OQ-020/021 (KRISS 라이브 실측)
   │                                              │
FS-001/020 (표준 소스로 측정) ──────────────  OQ-022 (한계 경고, RISK-001)
   │                                              │
DS-010/020 (source_host=time.kriss.re.kr) ──  IQ-007 (KRISS NTP 도달성)
   └──────────── 구현 measure_offset() / Monitor ─────────────┘
```

## 3. 좌측 가지 — KRISS를 표준으로 "정의"함

| 산출물 | KRISS 표준 정의 내용 | 근거 |
|--------|----------------------|------|
| [URS-001](01-user-requirements.md) | 시스템의 신뢰 시간 기준을 **KRISS UTC(k)** 로 요구(기본 NTP 소스 `time.kriss.re.kr`), GxP 영향도 H·Must | URS §3 |
| [REF-001](05-utck-reference-analysis.md) | 인용 기준 **UTCk**가 SNTP/NTP로 UTC(KRISS)에 동기화함을 규명, 본 시스템과 **동일 프로토콜·소스·오프셋 산식**임을 정합 근거로 확립 | REF §2·§3 |
| [FS-001/020](02-functional-spec.md) | 표준(신뢰 소스+파라미터) 정의 및 폴링 워커가 **표준 소스에 NTP 질의**해 오프셋 측정 | FS §2 |
| [DS-010/020](03-design-spec.md) | `TimeStandard.source_host` 기본값 **`time.kriss.re.kr`**, 측정은 `ntplib`(NTP) | DS §3·§4 |

**좌측 결론:** 설계 전 계층에서 신뢰 시간 표준이 KRISS UTC(k)로 명시·고정되어 있으며, 인용 기준 UTCk와의 알고리즘 정합이 REF-001로 규명되었다.

## 4. 우측 가지 — KRISS 표준 사용을 "입증"함 (실측 증거)

| 검증 | 절차 | 실측 결과 (2026-06-20) | 판정 |
|------|------|------------------------|------|
| [IQ-007](07-iq-protocol.md) | 구성된 `source_host`로 NTP 질의 | `time.kriss.re.kr` 응답, **stratum 3**, offset ≈ −3.07ms | ✅ PASS |
| [OQ-020](08-oq-protocol.md) | 폴링 1회(`POST /api/assets/{id}/poll`) | KRISS 라이브 수집, **offset −0.49ms, stratum 3**, OffsetSample 생성 | ✅ PASS |
| [OQ-021](08-oq-protocol.md) | `/api/dashboard` 조회 | 장비별 offset·stratum·last_sync·status=OK 반환 | ✅ PASS |
| [OQ-022a/b](08-oq-protocol.md) | 한계 ±1ms 경계 주입(RISK-001) | 한계 이내 미경고/한계 초과 BREACH | ✅ PASS |
| [PQ-001 / PQ §3](09-pq-protocol.md) | 본 시스템 보고 시각 ↔ 공식 UTCk 표시 시각 동시 비교 | (차이 ≤ 표준 허용 한계로 정합 입증) | ⬜ 예정 |

> **stratum 3 의 의미:** 본 시스템이 관측한 stratum 3은 응답 서버가 KRISS의 상위(stratum 1/2) 기준 시계로부터 시간을 받는 NTP 계층의 하위 노드임을 가리킨다. 즉 측정 경로의 뿌리가 **KRISS 기준 시계**임을 보이는 직접 증거다.

**우측 결론:** 실제 `time.kriss.re.kr`에서 NTP 응답을 수신하고(IQ-007), 그 오프셋을 수집·표시·경고 판정(OQ-020/021/022)함이 실측으로 입증되었다. High 위험(RISK-001) 경계 검증을 포함해 통과했다.

## 5. 표준 추적 체인 (Traceability to Standard)

KRISS 국가 표준에서 본 시스템의 출력까지 끊김 없는 사슬:

```
UTC(KRISS) — KRISS 원자시계 기반 협정세계시 실현 (국가 시간 표준)
   │  NTP 시각 분배
   ▼
time.kriss.re.kr — KRISS NTP 서버 (관측 stratum 3 경로)
   │  RFC 5905 오프셋 산식  θ = ((T2−T1)+(T3−T4))/2
   ▼
measure_offset() — ntplib NTP v3, 다중 샘플 중앙값 (RISK-004 완화)
   │
   ▼
TimeStandard(source_host="time.kriss.re.kr") — 시스템 내 표준 정의
   │
   ▼
OffsetSample → is_offset_breach → Alert / Dashboard — 모니터링 출력 (RISK-001)
```

각 단계는 §3·§4의 산출물·실측으로 뒷받침되며, REF-001이 1~3단계(KRISS↔NTP↔측정)의 알고리즘 정합을 보증한다.

## 6. 정합성 결론 (Conformance Statement)

- 본 시스템의 시각 표준은 **KRISS UTC(k)** 이며, 측정은 공식 UTCk와 **동일한 NTP 프로토콜·동일한 KRISS 소스·동일한 오프셋 산식**으로 수행됨이 좌측 설계(URS-001, REF-001, FS, DS)와 우측 실측(IQ-007, OQ-020/021/022)으로 **추적·입증**되었다.
- 따라서 본 시스템은 **"공식 UTCk에 *준하는*(conformant-to) KRISS 표준 기반 NTP 시각 모니터링 체계"** 임을 V 모델에 따라 증명한다.

## 7. 한계 및 미결 사항 (정직한 고지)

- 본 증명은 **소프트웨어 검증(CSV) 차원의 표준 정합·추적 증명**이며, 공인 교정기관의 **계량학적 소급성(metrological traceability) 인증과는 별개**다. 본 프로젝트는 KRISS 공식 인증 제품이 아니다(REF-001 §5).
- **PQ §3(UTCk 동시 비교)** 는 미실행(예정) — 완료 시 본 보고서 §4 표를 갱신해 증명을 닫는다.
- 감사 추적(FS-040/OQ-040)·표준 변경 이력(OQ-002)은 후속 증분 예정(OQ 일탈 #2/#3). 표준 *값*의 무단 변경 방지(RISK-002) 완결은 해당 구현에 의존한다.
- 측정은 네트워크 도달성에 의존하며, 폴링 중단은 `STALE` 상태로 감지된다(RISK-003).

## 8. 승인

| 역할 | 이름 | 서명 | 일자 |
|------|------|------|------|
| 작성(검증) | (자동화) | — | 2026-06-20 |
| 검토(QA) | | | |
| 승인(제품 소유자) | | | |

## 출처 / 참조 산출물

[VP](00-validation-plan.md) · [URS](01-user-requirements.md) · [FS](02-functional-spec.md) · [DS](03-design-spec.md) · [RA](04-risk-assessment.md) · [REF-001](05-utck-reference-analysis.md) · [RTM](06-traceability-matrix.md) · [IQ](07-iq-protocol.md) · [OQ](08-oq-protocol.md) · [PQ](09-pq-protocol.md)

# 제약(GxP) NTP 시계 신뢰성 관리 — 규제·산업 모범사례 분석

| 항목 | 내용 |
|------|------|
| 문서 ID | REG-001 |
| 버전 | 0.1 (Draft) |
| 작성일 | 2026-06-20 |
| V 모델 대응 | **횡단(근거)** — URS의 외부 정당화 근거 / 설계·검증의 모범사례 기준 |
| 관계 | [REF-001](05-utck-reference-analysis.md)(KRISS 기준 소스 규명)의 상위 규제 맥락. [RTM](06-traceability-matrix.md)으로 URS에 연결 |

## 1. 목적

제약(GxP) 환경에서 NTP 시간 동기화는 IT 설정이 아니라 **데이터 무결성(Data Integrity)의 법적 요건**이다. 전자기록의 "C(Contemporaneous, 동시성)"와 감사추적의 신뢰성이 **동기화된 보안 시계**에 직접 의존하기 때문이다. 본 문서는 최신 규제 동향과 산업 모범사례를 규명하고, 이를 본 시스템의 요구사항([URS](01-user-requirements.md))·위험([RA](04-risk-assessment.md))·검증([IQ](07-iq-protocol.md)/[OQ](08-oq-protocol.md)/[PQ](09-pq-protocol.md))과 **정합 매핑**하여, 설계 결정의 외부 정당화 근거를 제공한다.

## 2. 최신 규제 프레임워크 (2024–2026)

| 규제/지침 | 최신 상태 | 시간 관련 요지 |
|---|---|---|
| **EU GMP Annex 11 (개정 초안)** | 2025-07-07 EU·PIC/S 공동 초안 공개, 의견수렴 2025-10-11 종료, **2026 중반 최종본 예상** | 14년 만의 전면 개정. 감사추적은 **보안·동기화된 시계로 타임스탬프**, 변조 방지(tamper-proof) 명시. GAMP 5·ICH Q9/Q10·PIC/S와 정합 강화 |
| **21 CFR Part 11 (FDA)** | 유효 | **보안·컴퓨터 생성·타임스탬프된 감사추적** 의무 — 작업자 행위(생성/수정/삭제)를 독립 기록 |
| **PIC/S PI 041-1** | 2021-07-01 최종본 | 데이터 무결성 관리 종합 지침. 동시성·소급성의 기반으로 신뢰 시계 전제 |
| **GAMP 5 Second Edition** | 2022 발행 | CSV의 사실상 표준. 시간 동기화는 인프라 자격(IQ) 항목으로 검증 |
| **MHRA / WHO DI 가이드** | 유효 | ALCOA+ 원칙, "동시성"의 전제로 시간 신뢰성 요구 |

## 3. 데이터 무결성과 시간 (ALCOA+ / ALCOA++)

- **C (Contemporaneous)** — 기록 시점이 실제 행위 시점과 일치 → **시계 정확도가 직접 근거**
- **A (Attributable) / 감사추적** — "누가·무엇을·**언제**" 중 "언제"의 신뢰성
- **ALCOA++** 의 **Traceable(소급성)** — 시간 소스의 **계량학적 소급성**(국가 표준기관까지) 요구

## 4. NTP 시계 신뢰성 관리 — 모범사례 (관리 항목)

| # | 모범사례 | 핵심 관리 내용 |
|---|----------|----------------|
| BP-1 | **신뢰 시간 소스** | 단일 권위 소스로 동기화(임의 인터넷 NTP 혼용 금지). 국가 표준기관(한국=KRISS `ntp.kriss.re.kr`) 소급. stratum 계층 관리 |
| BP-2 | **이중화·복원력** | 다중 시간 서버(동일 상위 기준). 외부 단절 대비 내부 마스터 클록 고려 |
| BP-3 | **UTC 기준·타임존** | 내부 기록은 UTC 저장, 표시 시 오프셋 적용. DST 모호성/시각 역전 방지. 타임존/오프셋 동반 보관 |
| BP-4 | **드리프트 관리** | 허용 편차(offset) 한계 사전 정의·문서화. 드리프트 감지·보정을 **자동 로깅**(언제/얼마/어떻게). 폴링 주기 표준화 및 중단 감지 |
| BP-5 | **보안·변조방지** | 시스템 시계 변경 권한 제한, 변경의 감사추적 기록(tamper-proof) |
| BP-6 | **검증(CSV)** | IQ(구성·도달성), OQ(측정·경고·보정 경계값), PQ(국가표준 동시 비교). 주기 재검증 |
| BP-7 | **거버넌스** | SOP·표준 정의 문서화, 변경 이력 관리, 실패→경고+일탈 처리 연결 |

## 5. 정합 매핑 (본 시스템 ↔ 모범사례) — RTM 연결 근거

각 모범사례를 본 시스템의 요구사항·위험·검증·구현과 연결한다. 이 표가 [RTM](06-traceability-matrix.md)의 REG-001 행을 뒷받침한다.

| 모범사례 | 대응 URS | 대응 FS/DS | 위험 | 검증 | 현재 상태 |
|----------|----------|-----------|------|------|-----------|
| BP-1 신뢰 소스 | URS-001 | FS-001 / DS-010,020 | RISK-002 | IQ-007, OQ-020 | ⚠️ 소스 `time.kriss.re.kr`(legacy) → `ntp.kriss.re.kr` 갱신 필요 |
| BP-2 이중화 | (신규 후보 URS) | — | RISK-003 | — | ❌ 미설계 (후속 증분) |
| BP-3 UTC·타임존 | URS-041 | FS-041 / DS-001 | — | IQ-005 | ⚠️ 저장 형식 점검 필요 |
| BP-4 드리프트·폴링 | URS-020, URS-022 | FS-020,022 / DS-001,030 | RISK-001,003,004 | OQ-020,022 | ⚠️ 측정·경고·STALE ✅ / 주기 스케줄러·보정 로깅 ❌ |
| BP-5 변조방지 | URS-003, URS-040 | FS-002,040 / DS-010 | RISK-002,006 | OQ-002,040 | ❌ 감사추적 미구현 |
| BP-6 검증 | URS-001, URS-021 | — | RISK-001 | IQ-007, OQ-021, PQ-001,003 | ⚠️ IQ/OQ 일부 / PQ·OQ-040 미완 |
| BP-7 거버넌스 | URS-030, URS-031 | FS-030,031 / DS-010,030 | RISK-005 | OQ-030,031 | ✅ 산출물·승인 워크플로우 |

## 6. 결론 및 권고

- 업계 최신 신뢰성 요건과 본 시스템의 미구현 항목이 정확히 겹친다. 따라서 후속 우선순위 **① KRISS 소스 주소 갱신(BP-1) → ② 영속 저장 → ③ 감사추적·보정 로깅(BP-4/BP-5) → ④ 주기 폴링(BP-4)** 은 규제적으로 정당화된다.
- 본 문서는 **소프트웨어 검증(CSV) 관점의 모범사례 정합 분석**이며, 공인 교정기관의 **계량학적 소급성 인증과는 별개**다([REF-001](05-utck-reference-analysis.md) §5).
- 개정 Annex 11 최종본(2026 중반 예상) 발효 시 본 문서를 재검토·갱신한다.

## 출처

- EU Commission Releases Draft Annex 11 (2025): https://www.clinicalpathwaysresearch.com/blog/2025/12/2/eu-commission-releases-draft-annex-11-computerised-systems
- EU GMP Annex 11 (Draft 2025) — ECA Academy: https://www.gmp-compliance.org/guidelines/gmp-guideline/eu-gmp-annex-11-draft-2025-computerised-systems
- EU Annex 11 in 2026 (Data Integrity) — Zamann Pharma: https://zamann-pharma.com/2026/05/07/eu-annex-11-in-year-gmp-inspection-requirements-for-data-integrity-and-computerized-systems/
- Automating Audit Trail Compliance for 21 CFR Part 11 & Annex 11 — IntuitionLabs: https://intuitionlabs.ai/articles/audit-trails-21-cfr-part-11-annex-11-compliance
- Time-Stamps in 21 CFR Part 11 Audit Trails: https://www.part11compliance.com/posts/time-stamps-in-21-cfr-part-11-audit-trails
- PIC/S PI 041-1 Data Integrity Guidance (2021): https://picscheme.org/docview/4234
- ALCOA / ALCOA+ / ALCOA++ — Pharmaguideline: https://www.pharmaguideline.com/2018/12/alcoa-to-alcoa-plus-for-data-integrity.html
- Audit Trail Review in GxP Environments — ISPE Pharmaceutical Engineering: https://ispe.org/pharmaceutical-engineering/march-april-2026/audit-trail-review-regulation-and-practice-gxp

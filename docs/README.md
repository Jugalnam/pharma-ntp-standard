# 검증 문서 (V 모델 산출물)

본 디렉터리는 GAMP 5 기반 **V 모델**에 따른 컴퓨터 시스템 검증(CSV) 산출물을 담습니다.
각 산출물은 고유 ID로 항목을 식별하며, [추적성 매트릭스](06-traceability-matrix.md)로 좌·우 가지가 연결됩니다.

## V 모델 개요

```
검증 계획(VP) ─────────────────────────────────────────┐
                                                        │
  URS  사용자 요구사항 ─────────────────────────────  PQ  성능 적격성
   │                                                    │
   FS  기능 명세 ───────────────────────────────────  OQ  운영 적격성
    │                                                   │
    DS  설계 명세 ──────────────────────────────────  IQ  설치 적격성
     │                                                  │
      └────────── 구현 / 단위 테스트 ──────────────────┘
```

- **왼쪽 가지(분해)**: 요구사항을 점점 구체화 — URS → FS → DS → 구현
- **오른쪽 가지(통합/검증)**: 만든 것을 거꾸로 검증 — IQ → OQ → PQ
- **수평 연결(검증 대응)**: DS↔IQ, FS↔OQ, URS↔PQ — 각 설계 산출물은 대응하는 검증 단계에서 입증됨

## 산출물 인덱스

| # | 문서 | ID 접두 | V 모델 위치 | 상태 |
|---|------|--------|------------|------|
| 00 | [검증 계획](00-validation-plan.md) | VP | 전체 관장 | Draft |
| 01 | [사용자 요구사항 명세 (URS)](01-user-requirements.md) | URS | 좌 최상단 | Draft |
| 02 | [기능 명세 (FS)](02-functional-spec.md) | FS | 좌 중간 | Draft |
| 03 | [설계 명세 (DS)](03-design-spec.md) | DS | 좌 최하단 | Draft |
| 04 | [위험 평가 (RA)](04-risk-assessment.md) | RISK | 횡단 | Draft |
| 05 | [UTCk 기준 표준 분석](05-utck-reference-analysis.md) | REF | URS-001 근거 / 교차점검 전제 | Draft |
| 06 | [추적성 매트릭스 (RTM)](06-traceability-matrix.md) | — | 좌↔우 연결 | Draft |
| 06 | [IQ 프로토콜](07-iq-protocol.md) | IQ | 우 최하단 | Draft |
| 07 | [OQ 프로토콜](08-oq-protocol.md) | OQ | 우 중간 | Draft |
| 08 | [PQ 프로토콜](09-pq-protocol.md) | PQ | 우 최상단 | Draft |
| 09 | [KRISS 표준 정합성 검증 요약 보고서](10-kriss-conformance-report.md) | VSR | 전체 종합 (KRISS 표준 증명) | Draft |

## 문서 상태 정의

`Draft`(작성중) → `Reviewed`(검토완료) → `Approved`(승인) → `Effective`(발효)

## 변경 관리

모든 산출물 변경은 버전과 사유를 기록합니다. 승인된(`Approved`) 산출물의 변경은 영향 평가와 재승인이 필요합니다.

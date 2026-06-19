"""모니터링 엔진 OQ 테스트.

대응: OQ-020(수집), OQ-022a/b(경계·RISK-001), OQ-023(경고 해제·이력),
RISK-003(STALE 감지). 경계값과 상태 전이를 명시적으로 검증한다.
"""
from datetime import datetime, timedelta, timezone

from app.models.schemas import Asset, TimeStandard, AlertStatus
from app.services.monitor import Monitor, NtpResult, STALE_FACTOR


def _std(max_ms=1000.0, poll=60):
    return TimeStandard(id=1, name="KRISS", source_host="time.kriss.re.kr",
                        max_offset_ms=max_ms, poll_interval_s=poll, version=1)


def _asset():
    return Asset(id=1, name="srv-01", hostname="srv-01", gxp_critical=True, standard_id=1)


def test_oq020_poll_records_sample():
    """OQ-020: 폴링 1회 → OffsetSample 생성(측정 함수 주입으로 네트워크 분리)."""
    m, a, s = Monitor(), _asset(), _std()
    sample = m.poll(a, s, measure=lambda host: NtpResult(offset_ms=12.5, stratum=3))
    assert sample.offset_ms == 12.5 and sample.stratum == 3
    assert m.latest[a.id].offset_ms == 12.5


def test_oq022a_within_limit_no_alert():
    """OQ-022a: 오프셋 = 한계−1ms → 경고 미발생, 상태 OK."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    m.record_sample(a, s, offset_ms=999.0)
    assert m.status_of(a, s) == "OK"
    assert m.alerts == []


def test_oq022b_over_limit_breach():
    """OQ-022b: 오프셋 = 한계+1ms → 경고 발생(OPEN), 상태 BREACH."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    m.record_sample(a, s, offset_ms=1001.0)
    assert m.status_of(a, s) == "BREACH"
    assert len(m.alerts) == 1 and m.alerts[0].status == AlertStatus.OPEN


def test_oq022_exact_limit_passes():
    """경계: 정확히 한계 → 합격(경고 아님). is_offset_breach 규칙과 일치."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    m.record_sample(a, s, offset_ms=1000.0)
    assert m.status_of(a, s) == "OK" and m.alerts == []


def test_oq023_alert_close_and_history():
    """OQ-023: 초과로 경고 발생 후 복귀 → 경고 CLOSED, 이력 보존."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    t0 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    m.record_sample(a, s, offset_ms=1500.0, at=t0)                 # BREACH → OPEN
    m.record_sample(a, s, offset_ms=200.0, at=t0 + timedelta(seconds=60))  # 복귀 → CLOSE
    assert m.status_of(a, s, now=t0 + timedelta(seconds=61)) == "OK"
    assert len(m.alerts) == 1                                      # 이력 1건 보존
    alert = m.alerts[0]
    assert alert.status == AlertStatus.CLOSED and alert.closed_at == t0 + timedelta(seconds=60)


def test_oq023_no_duplicate_alert_while_open():
    """연속 초과 동안 중복 경고를 만들지 않는다(미해제 1건 유지)."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    m.record_sample(a, s, offset_ms=1500.0)
    m.record_sample(a, s, offset_ms=2000.0)
    assert len(m.alerts) == 1


def test_risk003_stale_detection():
    """RISK-003: 마지막 동기가 poll_interval*FACTOR 초과 → STALE."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0, poll=60)
    t0 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    m.record_sample(a, s, offset_ms=10.0, at=t0)
    fresh = t0 + timedelta(seconds=60 * STALE_FACTOR)        # 경계 내
    stale = t0 + timedelta(seconds=60 * STALE_FACTOR + 1)    # 경계 초과
    assert m.status_of(a, s, now=fresh) == "OK"
    assert m.status_of(a, s, now=stale) == "STALE"

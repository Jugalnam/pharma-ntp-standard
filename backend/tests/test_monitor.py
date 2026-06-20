"""모니터링 엔진 OQ 테스트.

대응: OQ-020(수집), OQ-022a/b(경계·RISK-001), OQ-023(경고 해제·이력),
RISK-003(STALE 감지). 경계값과 상태 전이를 명시적으로 검증한다.
"""
from datetime import datetime, timedelta, timezone

from app.models.schemas import Asset, TimeStandard, AlertStatus
from app.services.monitor import Monitor, NtpResult, STALE_FACTOR, is_due
from app.services.ntp import is_plausible_offset


def _std(max_ms=1000.0, poll=60):
    return TimeStandard(id=1, name="KRISS", source_host="time.kriss.re.kr",
                        max_offset_ms=max_ms, poll_interval_s=poll, version=1)


def _asset():
    return Asset(id=1, name="srv-01", hostname="srv-01", gxp_critical=True, standard_id=1)


def test_oq020_poll_per_device_corrected():
    """OQ-020: 폴링 시 장비(hostname)를 질의하고 KRISS 기준으로 보정해 기록한다.

    장비 vs KRISS = (장비 vs PC) − (KRISS vs PC) = 12.5 − 2.0 = 10.5.
    로컬 시계 미신뢰(URS-041): PC 자체 오차가 상쇄됨.
    """
    m, a, s = Monitor(), _asset(), _std()

    def fake(host):
        return (NtpResult(offset_ms=12.5, stratum=3) if host == a.hostname
                else NtpResult(offset_ms=2.0, stratum=2))

    res = m.poll(a, s, measure=fake)
    assert res.reachable and res.reference_synced
    assert res.sample.offset_ms == 10.5 and res.sample.stratum == 3
    assert m.latest[a.id].offset_ms == 10.5


def test_oq020_unreachable_when_device_no_response():
    """장비가 NTP에 무응답 → reachable=False, 샘플 없음, 상태 UNREACHABLE."""
    m, a, s = Monitor(), _asset(), _std()

    def fake(host):
        if host == a.hostname:
            raise TimeoutError("no response")
        return NtpResult(offset_ms=2.0, stratum=2)

    res = m.poll(a, s, measure=fake)
    assert res.reachable is False and res.sample is None
    assert m.status_of(a, s) == "UNREACHABLE"


def test_oq020_reference_unreachable_marks_unsynced():
    """기준(KRISS) 도달 실패 → 미보정 PC 대비값으로 폴백, reference_synced=False."""
    m, a, s = Monitor(), _asset(), _std()

    def fake(host):
        if host == a.hostname:
            return NtpResult(offset_ms=12.5, stratum=3)
        raise TimeoutError("kriss unreachable")

    res = m.poll(a, s, measure=fake)
    assert res.reachable and res.reference_synced is False
    assert res.sample.offset_ms == 12.5  # 미보정 값


def test_unreachable_then_recovered():
    """무응답 후 응답 복귀 → UNREACHABLE 해제, 정상 상태로 복귀."""
    m, a, s = Monitor(), _asset(), _std()
    state = {"down": True}

    def fake(host):
        if host == a.hostname:
            if state["down"]:
                raise TimeoutError("no response")
            return NtpResult(offset_ms=10.0, stratum=3)
        return NtpResult(offset_ms=2.0, stratum=2)

    m.poll(a, s, measure=fake)
    assert m.status_of(a, s) == "UNREACHABLE"
    state["down"] = False
    res = m.poll(a, s, measure=fake)
    assert res.reachable and m.status_of(a, s) == "OK"
    assert a.id not in m.unreachable


def test_fs024_scheduler_due():
    """FS-024: 미측정이거나 poll_interval 경과 시 폴링 대상(due)."""
    t0 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    assert is_due(None, 60, t0) is True                          # 미측정 → due
    assert is_due(t0, 60, t0 + timedelta(seconds=59)) is False   # 주기 내 → 아님
    assert is_due(t0, 60, t0 + timedelta(seconds=60)) is True     # 경계 → due


def test_fs024_poll_records_last_attempt():
    """폴링 시 응답/무응답 모두 last_attempt가 기록되어 스케줄러가 중복 폴링하지 않는다."""
    m, a, s = Monitor(), _asset(), _std()
    t0 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    m.poll(a, s, measure=lambda h: NtpResult(offset_ms=5.0, stratum=3), at=t0)
    assert m.last_attempt[a.id] == t0


def test_breach_log_has_name_and_limit():
    """한계초과 로그(Alert)에 장비명·한계값이 기록된다(FS-022/023)."""
    m, a, s = Monitor(), _asset(), _std(max_ms=1000.0)
    m.record_sample(a, s, offset_ms=1500.0)
    assert len(m.alerts) == 1
    al = m.alerts[0]
    assert al.asset_name == a.name and al.limit_ms == 1000.0


def test_dashboard_row_includes_hostname():
    """대시보드 행에 장비 IP/호스트가 포함된다(프론트 IP 열)."""
    m, a, s = Monitor(), _asset(), _std()
    row = m.dashboard_row(a, s, 1000.0)
    assert row["hostname"] == a.hostname


def test_fs052_offset_sanity_bound():
    """FS-052/RISK-009: 비현실적으로 큰 오프셋은 미신뢰(스푸핑 완화)."""
    assert is_plausible_offset(120.0, 3_600_000.0) is True
    assert is_plausible_offset(3_600_000.0, 3_600_000.0) is True   # 경계 = 합격
    assert is_plausible_offset(-5_000_000.0, 3_600_000.0) is False


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

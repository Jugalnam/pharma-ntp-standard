"""API 스모크 테스트 — IQ-005(health) 및 핵심 흐름.

상태 전이 규칙(FS-031 / RISK-005)의 거부 동작을 포함한다.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_standard_create_and_version_bump():
    r = client.post("/api/standards", json={"name": "KRISS 기준", "source_host": "time.kriss.re.kr"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert r.json()["version"] == 1

    r2 = client.put(f"/api/standards/{sid}", json={"name": "KRISS 기준", "max_offset_ms": 500})
    assert r2.status_code == 200
    assert r2.json()["version"] == 2  # FS-002


def test_oq002_standard_change_history():
    """OQ-002: 표준 수정 시 버전별 변경 이력(값 스냅샷+사유)이 기록된다(URS-003/FS-002)."""
    r = client.post("/api/standards", json={"name": "HIST", "source_host": "x", "max_offset_ms": 1000})
    sid = r.json()["id"]

    # 최초 생성 시 v1 이력 1건
    h0 = client.get(f"/api/standards/{sid}/history").json()
    assert [e["version"] for e in h0] == [1]
    assert h0[0]["reason"] == "최초 생성"

    # 사유와 함께 수정 → v2 이력에 사유·새 값 기록
    client.put(
        f"/api/standards/{sid}",
        json={"name": "HIST", "max_offset_ms": 500, "reason": "한계 강화"},
    )
    h1 = client.get(f"/api/standards/{sid}/history").json()
    assert [e["version"] for e in h1] == [1, 2]
    assert h1[1]["reason"] == "한계 강화"
    assert h1[1]["max_offset_ms"] == 500  # 변경된 값 스냅샷

    # 없는 표준의 이력 조회는 404
    assert client.get("/api/standards/999999/history").status_code == 404


def test_asset_create_no_validate_and_delete():
    # validate=false 로 네트워크 없이 등록(FS-010), 이후 삭제
    r = client.post(
        "/api/assets?validate=false",
        json={"name": "X-PC", "hostname": "10.0.0.9", "standard_id": None},
    )
    assert r.status_code == 201
    aid = r.json()["id"]
    assert r.json()["hostname"] == "10.0.0.9"

    d = client.delete(f"/api/assets/{aid}")
    assert d.status_code == 204
    # 이미 삭제됨 → 404
    assert client.delete(f"/api/assets/{aid}").status_code == 404


def test_persistence_standard_survives_new_session():
    """영속 저장: 생성한 표준이 새 DB 세션(=재시작 모사)에서도 조회된다."""
    r = client.post("/api/standards", json={"name": "PERSIST", "source_host": "x"})
    sid = r.json()["id"]
    from app.db import SessionLocal
    from app.models.orm import StandardORM

    with SessionLocal() as db:
        o = db.get(StandardORM, sid)
        assert o is not None and o.name == "PERSIST"


def test_alerts_recent_and_date_range():
    """FS-023: 기본은 최근 7일+OPEN, since/until 지정 시 해당 기간(opened_at) 조회."""
    from datetime import datetime, timezone, timedelta
    from app.api.routes import monitor
    from app.models.schemas import Alert, AlertStatus

    now = datetime.now(timezone.utc)
    saved = list(monitor.alerts)
    monitor.alerts.clear()
    monitor.alerts.append(Alert(id=9001, asset_id=1, asset_name="OLD",
                                opened_at=now - timedelta(days=30),
                                closed_at=now - timedelta(days=29),
                                offset_ms=10, limit_ms=5, status=AlertStatus.CLOSED))
    monitor.alerts.append(Alert(id=9002, asset_id=2, asset_name="RECENT",
                                opened_at=now - timedelta(days=1),
                                offset_ms=20, limit_ms=5, status=AlertStatus.OPEN))
    try:
        # 기본(최근 7일): RECENT만, OLD 제외
        names = [a["asset_name"] for a in client.get("/api/alerts").json()]
        assert "RECENT" in names and "OLD" not in names
        # 기간 지정: 30일 전 포함 → OLD만 (params=로 안전 인코딩)
        params = {
            "since": (now - timedelta(days=31)).isoformat(),
            "until": (now - timedelta(days=28)).isoformat(),
        }
        pnames = [a["asset_name"] for a in client.get("/api/alerts", params=params).json()]
        assert "OLD" in pnames and "RECENT" not in pnames
    finally:
        monitor.alerts.clear()
        monitor.alerts.extend(saved)


def test_deliverable_invalid_transition_rejected():
    r = client.post("/api/deliverables", json={"type": "OQ", "title": "OQ 프로토콜"})
    did = r.json()["id"]
    # Draft -> Approved 직접 전이는 금지 (RISK-005)
    bad = client.post(f"/api/deliverables/{did}/transition", params={"target": "Approved"})
    assert bad.status_code == 409
    # Draft -> Reviewed 는 허용
    ok = client.post(f"/api/deliverables/{did}/transition", params={"target": "Reviewed"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "Reviewed"

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

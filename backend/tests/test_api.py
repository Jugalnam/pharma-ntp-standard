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

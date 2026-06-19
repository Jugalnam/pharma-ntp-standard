"""REST 라우터 (DS-020).

초기 골격: 인메모리 저장소 기반. 표준/장비/대시보드/산출물 CRUD 스텁을 제공한다.
후속 반복에서 영속 저장소(SQLAlchemy)와 감사 추적(FS-040)을 연결한다.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import (
    Asset, AssetIn,
    TimeStandard, TimeStandardIn,
    Deliverable, DeliverableIn, DeliverableStatus,
)
from app.services.alerts import is_offset_breach

router = APIRouter(prefix="/api")

# --- 인메모리 저장소 (개발 골격) ---
_standards: dict[int, TimeStandard] = {}
_assets: dict[int, Asset] = {}
_deliverables: dict[int, Deliverable] = {}
_seq = {"standard": 0, "asset": 0, "deliverable": 0}


def _next(key: str) -> int:
    _seq[key] += 1
    return _seq[key]


@router.get("/health")
def health():
    """IQ-005: 헬스체크."""
    return {"status": "ok", "reference_source": settings.default_ntp_host}


# --- 표준 (FS-001/002) ---
@router.get("/standards", response_model=list[TimeStandard])
def list_standards():
    return list(_standards.values())


@router.post("/standards", response_model=TimeStandard, status_code=201)
def create_standard(body: TimeStandardIn):
    sid = _next("standard")
    std = TimeStandard(id=sid, version=1, **body.model_dump())
    _standards[sid] = std
    return std


@router.put("/standards/{sid}", response_model=TimeStandard)
def update_standard(sid: int, body: TimeStandardIn):
    if sid not in _standards:
        raise HTTPException(404, "standard not found")
    prev = _standards[sid]
    std = TimeStandard(id=sid, version=prev.version + 1, **body.model_dump())
    _standards[sid] = std  # FS-002: 버전 증가 (변경 이력은 후속 반복)
    return std


# --- 장비 (FS-010~012) ---
@router.get("/assets", response_model=list[Asset])
def list_assets():
    return list(_assets.values())


@router.post("/assets", response_model=Asset, status_code=201)
def create_asset(body: AssetIn):
    aid = _next("asset")
    asset = Asset(id=aid, **body.model_dump())
    _assets[aid] = asset
    return asset


# --- 대시보드 (FS-021) ---
@router.get("/dashboard")
def dashboard():
    """장비별 최신 상태 요약. (오프셋 수집 워커 연동은 후속 반복)"""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for a in _assets.values():
        std = _standards.get(a.standard_id) if a.standard_id else None
        limit = std.max_offset_ms if std else settings.default_max_offset_ms
        rows.append({
            "asset_id": a.id,
            "name": a.name,
            "gxp_critical": a.gxp_critical,
            "offset_ms": None,        # 워커 연동 전 placeholder
            "max_offset_ms": limit,
            "status": "UNKNOWN",
            "last_sync": None,
        })
    return {"generated_at": now, "assets": rows}


# --- 검증 산출물 (FS-030/031) ---
_TRANSITIONS = {
    DeliverableStatus.DRAFT: {DeliverableStatus.REVIEWED},
    DeliverableStatus.REVIEWED: {DeliverableStatus.APPROVED},
    DeliverableStatus.APPROVED: {DeliverableStatus.EFFECTIVE},
    DeliverableStatus.EFFECTIVE: set(),
}


@router.get("/deliverables", response_model=list[Deliverable])
def list_deliverables():
    return list(_deliverables.values())


@router.post("/deliverables", response_model=Deliverable, status_code=201)
def create_deliverable(body: DeliverableIn):
    did = _next("deliverable")
    d = Deliverable(id=did, status=DeliverableStatus.DRAFT, **body.model_dump())
    _deliverables[did] = d
    return d


@router.post("/deliverables/{did}/transition", response_model=Deliverable)
def transition_deliverable(did: int, target: DeliverableStatus):
    """FS-031 / RISK-005: 상태 전이 규칙 강제(건너뛰기·역방향 불가)."""
    if did not in _deliverables:
        raise HTTPException(404, "deliverable not found")
    d = _deliverables[did]
    if target not in _TRANSITIONS[d.status]:
        raise HTTPException(409, f"invalid transition: {d.status} -> {target}")
    d.status = target
    return d

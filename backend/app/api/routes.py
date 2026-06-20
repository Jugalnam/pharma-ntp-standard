"""REST 라우터 (DS-020).

초기 골격: 인메모리 저장소 기반. 표준/장비/대시보드/산출물 CRUD 스텁을 제공한다.
후속 반복에서 영속 저장소(SQLAlchemy)와 감사 추적(FS-040)을 연결한다.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import (
    Asset, AssetIn,
    TimeStandard, TimeStandardIn,
    Deliverable, DeliverableIn, DeliverableStatus,
    OffsetSample, Alert,
)
from app.services.monitor import Monitor, is_due
from app.services.ntp import measure_offset, is_plausible_offset

logger = logging.getLogger("ntp.scheduler")

router = APIRouter(prefix="/api")

# --- 인메모리 저장소 (개발 골격) ---
_standards: dict[int, TimeStandard] = {}
_assets: dict[int, Asset] = {}
_deliverables: dict[int, Deliverable] = {}
_seq = {"standard": 0, "asset": 0, "deliverable": 0}

# 모니터링 엔진(FS-020~023). 인메모리 상태 보유.
monitor = Monitor()


def _next(key: str) -> int:
    _seq[key] += 1
    return _seq[key]


async def run_scheduler() -> None:
    """주기적 백그라운드 폴링 스케줄러(FS-024, RISK-003 완화).

    scheduler_tick_s마다 깨어나, 각 장비를 표준의 poll_interval_s 주기로 측정한다.
    블로킹 NTP 측정은 스레드로 분리해 이벤트 루프를 막지 않는다. 개별 폴링 실패는
    로깅 후 계속하여 한 장비의 무응답이 전체 스케줄러를 멈추지 않게 한다.
    """
    logger.info("scheduler started (tick=%ss)", settings.scheduler_tick_s)
    try:
        while True:
            await asyncio.sleep(settings.scheduler_tick_s)
            now = datetime.now(timezone.utc)
            for asset in list(_assets.values()):
                std = _standards.get(asset.standard_id) if asset.standard_id else None
                if std is None:
                    continue
                if is_due(monitor.last_attempt.get(asset.id), std.poll_interval_s, now):
                    try:
                        await asyncio.to_thread(monitor.poll, asset, std)
                    except Exception as e:  # 개별 장비 실패는 격리
                        logger.warning("scheduled poll failed for asset %s: %s", asset.id, e)
    except asyncio.CancelledError:
        logger.info("scheduler stopped")
        raise


@router.get("/health")
def health():
    """IQ-005: 헬스체크."""
    return {"status": "ok", "reference_source": settings.default_ntp_host}


@router.get("/time")
def reference_time():
    """KRISS 기준 시각(표준시) 1회 측정 — 프론트 대형 시계용(FS-041).

    server UTC에 KRISS 오프셋을 보정해 '신뢰 시간'을 반환한다(로컬 시계 미신뢰 원칙).
    NTP 도달 실패 시 synced=false로 server 시각을 폴백 제공한다(RISK-003 가시화).
    프론트는 이 값을 앵커로 매초 로컬 틱하고 주기적으로 재동기한다.
    """
    now = datetime.now(timezone.utc)
    host = settings.default_ntp_host
    try:
        # 폴링과 동일한 다중 샘플로 단발 UDP 유실에 견고하게(RISK-004).
        res = measure_offset(host, samples=3)
        # 비현실적으로 큰 오프셋은 스푸핑/이상치로 보고 미신뢰(FS-052, RISK-009).
        if not is_plausible_offset(res.offset_ms, settings.ntp_sanity_bound_ms):
            return {
                "reference_utc": now.isoformat(),
                "offset_ms": res.offset_ms,
                "stratum": res.stratum,
                "source_host": host,
                "synced": False,
                "detail": "offset exceeds sanity bound (FS-052)",
            }
        ref = now + timedelta(milliseconds=res.offset_ms)
        return {
            "reference_utc": ref.isoformat(),
            "offset_ms": res.offset_ms,
            "stratum": res.stratum,
            "source_host": host,
            "synced": True,
        }
    except Exception as e:  # NTP 도달 실패 — server 시각 폴백
        return {
            "reference_utc": now.isoformat(),
            "offset_ms": None,
            "stratum": None,
            "source_host": host,
            "synced": False,
            "detail": str(e),
        }


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


# --- 모니터링 (FS-020/021/022/023) ---
@router.post("/assets/{aid}/poll")
def poll_asset(aid: int):
    """장비 자신(asset.hostname)에 NTP 질의해 KRISS 기준 오차를 1회 수집한다(FS-020).

    장비 무응답 시 예외 대신 `reachable=false`(UNREACHABLE)로 반환한다.
    """
    if aid not in _assets:
        raise HTTPException(404, "asset not found")
    asset = _assets[aid]
    std = _standards.get(asset.standard_id) if asset.standard_id else None
    if std is None:
        raise HTTPException(409, "asset has no time standard assigned")
    result = monitor.poll(asset, std)
    return {
        "asset_id": result.asset_id,
        "reachable": result.reachable,
        "reference_synced": result.reference_synced,
        "sample": result.sample,
        "detail": result.detail,
    }


@router.get("/dashboard")
def dashboard():
    """장비별 최신 오프셋·상태 요약(FS-021). 상태는 UNKNOWN/STALE/BREACH/OK."""
    now = datetime.now(timezone.utc)
    rows = [
        monitor.dashboard_row(
            a, _standards.get(a.standard_id) if a.standard_id else None,
            settings.default_max_offset_ms, now,
        )
        for a in _assets.values()
    ]
    return {"generated_at": now.isoformat(), "assets": rows}


@router.get("/alerts", response_model=list[Alert])
def list_alerts():
    """경고 발생/해제 이력(FS-023)."""
    return monitor.alerts


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

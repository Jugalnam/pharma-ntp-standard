"""REST 라우터 (DS-020).

영속 저장소(SQLAlchemy/SQLite): 표준·장비·산출물·한계초과 로그를 DB에 저장한다.
실시간 측정값(오프셋·도달성)은 폴링으로 재생성되므로 모니터링 엔진(인메모리)에 둔다.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.orm import (
    StandardORM, StandardHistoryORM, AssetORM, DeliverableORM, AlertORM,
)
from app.models.schemas import (
    Asset, AssetIn,
    TimeStandard, TimeStandardIn, TimeStandardUpdate, StandardHistory,
    Deliverable, DeliverableIn, DeliverableStatus,
    Alert,
)
from app.services.monitor import Monitor, is_due
from app.services.ntp import measure_offset, is_plausible_offset

logger = logging.getLogger("ntp.scheduler")

router = APIRouter(prefix="/api")

# 모니터링 엔진(FS-020~023). 실시간 상태는 인메모리, 경고 로그는 DB와 write-through.
monitor = Monitor()


def get_db():
    """요청 단위 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- ORM ↔ Pydantic / 영속 헬퍼 ---
def _alert_from_orm(o: AlertORM) -> Alert:
    def _utc(dt):  # SQLite는 tz를 잃을 수 있어 UTC를 재부여
        return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt
    return Alert(
        id=o.id, asset_id=o.asset_id, asset_name=o.asset_name,
        opened_at=_utc(o.opened_at), closed_at=_utc(o.closed_at),
        offset_ms=o.offset_ms, limit_ms=o.limit_ms, status=o.status,
    )


def save_alerts(db: Session, alerts: list[Alert]) -> None:
    """모니터의 현재 한계초과 로그를 DB에 write-through(upsert by id)."""
    for a in alerts:
        db.merge(AlertORM(
            id=a.id, asset_id=a.asset_id, asset_name=a.asset_name,
            opened_at=a.opened_at, closed_at=a.closed_at,
            offset_ms=a.offset_ms, limit_ms=a.limit_ms, status=a.status.value,
        ))
    db.commit()


def hydrate_from_db() -> None:
    """기동 시 DB의 한계초과 로그로 모니터 경고 상태를 복원한다(FS-023)."""
    with SessionLocal() as db:
        rows = db.scalars(select(AlertORM)).all()
        monitor.hydrate([_alert_from_orm(o) for o in rows])


async def run_scheduler() -> None:
    """주기적 백그라운드 폴링 스케줄러(FS-024, RISK-003 완화).

    DB에서 장비·표준을 읽어, 각 장비를 표준의 poll_interval_s 주기로 측정한다.
    블로킹 NTP 측정은 스레드로 분리·동시 실행(상한 scheduler_concurrency)하고,
    개별 폴링 실패는 격리한다. 폴링 후 변동된 한계초과 로그를 DB에 저장한다.
    """
    logger.info("scheduler started (tick=%ss, concurrency=%s)",
                settings.scheduler_tick_s, settings.scheduler_concurrency)
    sem = asyncio.Semaphore(settings.scheduler_concurrency)

    async def _poll_one(asset: Asset, std: TimeStandard) -> None:
        async with sem:
            try:
                await asyncio.to_thread(monitor.poll, asset, std)
            except Exception as e:  # 개별 장비 실패는 격리
                logger.warning("scheduled poll failed for asset %s: %s", asset.id, e)

    try:
        while True:
            await asyncio.sleep(settings.scheduler_tick_s)
            now = datetime.now(timezone.utc)
            with SessionLocal() as db:
                assets = [Asset.model_validate(a) for a in db.scalars(select(AssetORM)).all()]
                stds = {s.id: TimeStandard.model_validate(s)
                        for s in db.scalars(select(StandardORM)).all()}
            due = []
            for asset in assets:
                std = stds.get(asset.standard_id) if asset.standard_id else None
                if std is None:
                    continue
                if is_due(monitor.last_attempt.get(asset.id), std.poll_interval_s, now):
                    due.append((asset, std))
            if due:
                await asyncio.gather(*(_poll_one(a, s) for a, s in due))
                with SessionLocal() as db:
                    save_alerts(db, monitor.alerts)
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
    """
    now = datetime.now(timezone.utc)
    host = settings.default_ntp_host
    try:
        res = measure_offset(host, samples=3)
        # 비현실적으로 큰 오프셋은 스푸핑/이상치로 보고 미신뢰(FS-052, RISK-009).
        if not is_plausible_offset(res.offset_ms, settings.ntp_sanity_bound_ms):
            return {
                "reference_utc": now.isoformat(), "offset_ms": res.offset_ms,
                "stratum": res.stratum, "source_host": host, "synced": False,
                "detail": "offset exceeds sanity bound (FS-052)",
            }
        ref = now + timedelta(milliseconds=res.offset_ms)
        return {
            "reference_utc": ref.isoformat(), "offset_ms": res.offset_ms,
            "stratum": res.stratum, "source_host": host, "synced": True,
        }
    except Exception as e:  # NTP 도달 실패 — server 시각 폴백
        return {
            "reference_utc": now.isoformat(), "offset_ms": None, "stratum": None,
            "source_host": host, "synced": False, "detail": str(e),
        }


# --- 표준 (FS-001/002) ---
def _record_standard_history(db: Session, o: StandardORM, reason: str) -> None:
    """표준의 현재 값 스냅샷을 변경 이력에 append한다(URS-003/FS-002)."""
    db.add(StandardHistoryORM(
        standard_id=o.id, version=o.version,
        name=o.name, source_host=o.source_host,
        max_offset_ms=o.max_offset_ms, poll_interval_s=o.poll_interval_s,
        reason=reason or "", actor="system",  # 인증 부재 — system 기록
        changed_at=datetime.now(timezone.utc),
    ))


def _history_from_orm(r: StandardHistoryORM) -> StandardHistory:
    changed = r.changed_at  # SQLite는 tz를 잃을 수 있어 UTC 재부여
    if changed is not None and changed.tzinfo is None:
        changed = changed.replace(tzinfo=timezone.utc)
    return StandardHistory(
        id=r.id, standard_id=r.standard_id, version=r.version,
        name=r.name, source_host=r.source_host, max_offset_ms=r.max_offset_ms,
        poll_interval_s=r.poll_interval_s, reason=r.reason, actor=r.actor,
        changed_at=changed,
    )


@router.get("/standards", response_model=list[TimeStandard])
def list_standards(db: Session = Depends(get_db)):
    return [TimeStandard.model_validate(s) for s in db.scalars(select(StandardORM)).all()]


@router.post("/standards", response_model=TimeStandard, status_code=201)
def create_standard(body: TimeStandardIn, db: Session = Depends(get_db)):
    o = StandardORM(version=1, **body.model_dump())
    db.add(o)
    db.commit()
    db.refresh(o)
    _record_standard_history(db, o, "최초 생성")  # FS-002: 이력 v1
    db.commit()
    return TimeStandard.model_validate(o)


@router.put("/standards/{sid}", response_model=TimeStandard)
def update_standard(sid: int, body: TimeStandardUpdate, db: Session = Depends(get_db)):
    o = db.get(StandardORM, sid)
    if o is None:
        raise HTTPException(404, "standard not found")
    for k, v in body.model_dump(exclude={"reason"}).items():
        setattr(o, k, v)
    o.version += 1  # FS-002: 버전 증가
    _record_standard_history(db, o, body.reason or "(사유 미기재)")  # 변경 이력 기록
    db.commit()
    db.refresh(o)
    return TimeStandard.model_validate(o)


@router.get("/standards/{sid}/history", response_model=list[StandardHistory])
def standard_history(sid: int, db: Session = Depends(get_db)):
    """표준 변경 이력(버전순). URS-003/FS-002 — 누가(system)·언제·무엇을·왜."""
    if db.get(StandardORM, sid) is None:
        raise HTTPException(404, "standard not found")
    rows = db.scalars(
        select(StandardHistoryORM)
        .where(StandardHistoryORM.standard_id == sid)
        .order_by(StandardHistoryORM.version)
    ).all()
    return [_history_from_orm(r) for r in rows]


# --- 장비 (FS-010~012) ---
@router.get("/assets", response_model=list[Asset])
def list_assets(db: Session = Depends(get_db)):
    return [Asset.model_validate(a) for a in db.scalars(select(AssetORM)).all()]


@router.post("/assets", response_model=Asset, status_code=201)
def create_asset(body: AssetIn, validate: bool = True, db: Session = Depends(get_db)):
    """장비 등록(FS-010). validate=true(기본)면 등록 전 NTP 응답을 확인한다.

    응답하지 않는 호스트는 422로 거부한다(데이터 무결성). 대량 시드/테스트는
    validate=false로 우회 가능.
    """
    if validate:
        try:
            measure_offset(body.hostname, samples=1, timeout=settings.ntp_timeout_s)
        except Exception as e:
            raise HTTPException(
                422,
                f"'{body.hostname}'이(가) NTP 응답을 하지 않아 등록할 수 없습니다. "
                f"(IP/방화벽/NTP 서버 활성화 확인) [{e}]",
            )
    o = AssetORM(**body.model_dump())
    db.add(o)
    db.commit()
    db.refresh(o)
    return Asset.model_validate(o)


@router.delete("/assets/{aid}", status_code=204)
def delete_asset(aid: int, db: Session = Depends(get_db)):
    """장비 등록 해제(FS-010). 모니터링 인메모리 상태도 함께 정리한다."""
    o = db.get(AssetORM, aid)
    if o is None:
        raise HTTPException(404, "asset not found")
    db.delete(o)
    db.commit()
    monitor.latest.pop(aid, None)
    monitor.unreachable.pop(aid, None)
    monitor.last_attempt.pop(aid, None)
    return None


# --- 모니터링 (FS-020/021/022/023) ---
@router.post("/assets/{aid}/poll")
def poll_asset(aid: int, db: Session = Depends(get_db)):
    """장비 자신(asset.hostname)에 NTP 질의해 KRISS 기준 오차를 1회 수집한다(FS-020)."""
    asset_o = db.get(AssetORM, aid)
    if asset_o is None:
        raise HTTPException(404, "asset not found")
    std_o = db.get(StandardORM, asset_o.standard_id) if asset_o.standard_id else None
    if std_o is None:
        raise HTTPException(409, "asset has no time standard assigned")
    result = monitor.poll(Asset.model_validate(asset_o), TimeStandard.model_validate(std_o))
    save_alerts(db, monitor.alerts)  # 한계초과 로그 영속화
    return {
        "asset_id": result.asset_id, "reachable": result.reachable,
        "reference_synced": result.reference_synced, "sample": result.sample,
        "detail": result.detail,
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """장비별 최신 오프셋·상태 요약(FS-021). 상태는 UNKNOWN/UNREACHABLE/STALE/BREACH/OK."""
    now = datetime.now(timezone.utc)
    stds = {s.id: TimeStandard.model_validate(s)
            for s in db.scalars(select(StandardORM)).all()}
    rows = []
    for a in db.scalars(select(AssetORM)).all():
        asset = Asset.model_validate(a)
        std = stds.get(asset.standard_id) if asset.standard_id else None
        rows.append(monitor.dashboard_row(asset, std, settings.default_max_offset_ms, now))
    return {"generated_at": now.isoformat(), "assets": rows}


@router.get("/alerts", response_model=list[Alert])
def list_alerts(
    since: datetime | None = None,
    until: datetime | None = None,
    days: int = 7,
):
    """한계초과 로그(FS-023). 인메모리(=DB와 동기) 상태를 최신순으로 반환.

    - 파라미터 없음: **최근 `days`일(기본 7일) + 진행 중(OPEN) 전부** — 오래된 미해제
      경고도 항상 보이게 한다.
    - `since`/`until`(ISO): 해당 기간(opened_at 기준) 조회 — '지난 이력' 탭용.
    """
    def _aware(dt):  # tz 미지정 입력은 UTC로 간주(인메모리 opened_at은 tz-aware UTC)
        return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt

    since, until = _aware(since), _aware(until)
    if since is not None or until is not None:
        sel = [
            a for a in monitor.alerts
            if (since is None or a.opened_at >= since)
            and (until is None or a.opened_at <= until)
        ]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        sel = [a for a in monitor.alerts if a.opened_at >= cutoff or a.status == "OPEN"]
    return sorted(sel, key=lambda a: a.opened_at, reverse=True)


# --- 검증 산출물 (FS-030/031) ---
_TRANSITIONS = {
    DeliverableStatus.DRAFT: {DeliverableStatus.REVIEWED},
    DeliverableStatus.REVIEWED: {DeliverableStatus.APPROVED},
    DeliverableStatus.APPROVED: {DeliverableStatus.EFFECTIVE},
    DeliverableStatus.EFFECTIVE: set(),
}


@router.get("/deliverables", response_model=list[Deliverable])
def list_deliverables(db: Session = Depends(get_db)):
    return [Deliverable.model_validate(d) for d in db.scalars(select(DeliverableORM)).all()]


@router.post("/deliverables", response_model=Deliverable, status_code=201)
def create_deliverable(body: DeliverableIn, db: Session = Depends(get_db)):
    o = DeliverableORM(
        type=body.type.value, title=body.title,
        status=DeliverableStatus.DRAFT.value, requirement_tags=body.requirement_tags,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return Deliverable.model_validate(o)


@router.post("/deliverables/{did}/transition", response_model=Deliverable)
def transition_deliverable(did: int, target: DeliverableStatus, db: Session = Depends(get_db)):
    """FS-031 / RISK-005: 상태 전이 규칙 강제(건너뛰기·역방향 불가)."""
    o = db.get(DeliverableORM, did)
    if o is None:
        raise HTTPException(404, "deliverable not found")
    current = DeliverableStatus(o.status)
    if target not in _TRANSITIONS[current]:
        raise HTTPException(409, f"invalid transition: {current} -> {target}")
    o.status = target.value
    db.commit()
    db.refresh(o)
    return Deliverable.model_validate(o)
